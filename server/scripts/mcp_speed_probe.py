"""Measure AgentPort MCP latency by stage.

Run from server/:

    uv run python scripts/mcp_speed_probe.py --api-key ap_...

The probe is read-only unless --call-tool is passed.
"""

from __future__ import annotations

import argparse
import asyncio
import inspect
import json
import math
import os
import sys
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Awaitable, Callable

import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


@dataclass
class ProbeResult:
    name: str
    samples_ms: list[float] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    detail: str = ""

    @property
    def ok(self) -> bool:
        return bool(self.samples_ms)

    def percentile(self, pct: float) -> float | None:
        if not self.samples_ms:
            return None
        ordered = sorted(self.samples_ms)
        index = max(0, min(len(ordered) - 1, math.ceil((pct / 100) * len(ordered)) - 1))
        return ordered[index]

    def summary(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "count": len(self.samples_ms),
            "errors": self.errors,
            "detail": self.detail,
            "min_ms": min(self.samples_ms) if self.samples_ms else None,
            "p50_ms": self.percentile(50),
            "p95_ms": self.percentile(95),
            "max_ms": max(self.samples_ms) if self.samples_ms else None,
        }


@dataclass
class CacheRow:
    integration_id: str
    type: str
    auth_method: str
    connected: bool
    updating_tool_cache: bool
    cache_state: str
    cache_age_s: float | None
    tools_count: int | None
    cache_bytes: int | None


def _header_map(args: argparse.Namespace) -> dict[str, str]:
    if args.api_key:
        return {"X-API-Key": args.api_key}
    if args.bearer_token:
        return {"Authorization": f"Bearer {args.bearer_token}"}
    return {}


def _redacted_header_map(args: argparse.Namespace) -> dict[str, str]:
    if args.api_key:
        return {"X-API-Key": f"{args.api_key[:8]}..."}
    if args.bearer_token:
        return {"Authorization": "Bearer ..."}
    return {}


def _mcp_url(server_url: str) -> str:
    return f"{server_url.rstrip('/')}/mcp"


def _api_url(server_url: str, path: str) -> str:
    return f"{server_url.rstrip('/')}{path}"


def _short_error(exc: BaseException) -> str:
    if isinstance(exc, BaseExceptionGroup):
        return "; ".join(_short_error(sub) for sub in exc.exceptions)
    message = str(exc) or exc.__class__.__name__
    return message.replace("\n", " ")[:500]


async def _maybe_await(value: Any) -> Any:
    if inspect.isawaitable(value):
        return await value
    return value


async def _measure(
    name: str,
    action: Callable[[], Awaitable[Any] | Any],
    *,
    iterations: int,
    warmup: int,
    detail_fn: Callable[[Any], str] | None = None,
) -> ProbeResult:
    result = ProbeResult(name=name)
    total_runs = warmup + iterations

    for index in range(total_runs):
        started = time.perf_counter()
        try:
            value = await _maybe_await(action())
        except (Exception, BaseExceptionGroup) as exc:
            if index >= warmup:
                result.errors.append(_short_error(exc))
            continue

        elapsed_ms = (time.perf_counter() - started) * 1000
        if index < warmup:
            continue
        result.samples_ms.append(elapsed_ms)
        if detail_fn:
            try:
                detail = detail_fn(value)
            except Exception:
                detail = ""
            if detail:
                result.detail = detail

    return result


def _tool_list_detail(value: Any) -> str:
    tools = getattr(value, "tools", None)
    if tools is None and isinstance(value, list):
        tools = value
    if tools is None:
        return ""
    return f"tools={len(tools)}"


def _mcp_call_detail(value: Any) -> str:
    content = getattr(value, "content", []) or []
    is_error = getattr(value, "isError", None)
    text = "\n".join(getattr(item, "text", "") for item in content)
    text_bytes = len(text.encode("utf-8"))
    prefix = f"content_bytes={text_bytes}"
    if is_error is not None:
        prefix = f"{prefix} is_error={is_error}"

    try:
        payload = json.loads(text)
    except Exception:
        return prefix

    if isinstance(payload, list):
        return f"{prefix} items={len(payload)}"
    if isinstance(payload, dict):
        if "tools" in payload and isinstance(payload["tools"], list):
            return f"{prefix} tools={len(payload['tools'])}"
        if "integration_id" in payload:
            return f"{prefix} integration_id={payload['integration_id']}"
    return prefix


def _http_detail(value: httpx.Response) -> str:
    content_type = value.headers.get("content-type", "")
    body = value.content
    detail = f"status={value.status_code} bytes={len(body)}"
    if "application/json" not in content_type:
        return detail
    try:
        payload = value.json()
    except Exception:
        return detail
    if isinstance(payload, list):
        return f"{detail} items={len(payload)}"
    if isinstance(payload, dict) and "tools" in payload and isinstance(payload["tools"], list):
        return f"{detail} tools={len(payload['tools'])}"
    return detail


def _parse_arguments(raw: str) -> dict[str, Any]:
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise argparse.ArgumentTypeError(f"arguments must be JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise argparse.ArgumentTypeError("arguments must decode to a JSON object")
    return value


def _resolve_org_id(args: argparse.Namespace) -> uuid.UUID | None:
    from sqlmodel import Session, select

    from agent_port.db import engine
    from agent_port.models.api_key import ApiKey
    from agent_port.models.org import Org

    if args.org_id:
        return uuid.UUID(args.org_id)

    with Session(engine) as db:
        if args.api_key:
            import hashlib

            key_hash = hashlib.sha256(args.api_key.encode()).hexdigest()
            api_key = db.exec(
                select(ApiKey).where(ApiKey.key_hash == key_hash).where(ApiKey.is_active == True)  # noqa: E712
            ).first()
            if api_key:
                return api_key.org_id

        orgs = db.exec(select(Org)).all()
        if len(orgs) == 1:
            return orgs[0].id

    return None


def _load_cache_rows(args: argparse.Namespace) -> list[CacheRow]:
    from sqlmodel import Session, select

    from agent_port.db import engine
    from agent_port.models.integration import InstalledIntegration
    from agent_port.models.tool_cache import ToolCache

    org_id = _resolve_org_id(args)
    if org_id is None:
        return []

    rows: list[CacheRow] = []
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    with Session(engine) as db:
        installed_rows = db.exec(
            select(InstalledIntegration).where(InstalledIntegration.org_id == org_id)
        ).all()
        caches = {
            row.integration_id: row
            for row in db.exec(select(ToolCache).where(ToolCache.org_id == org_id)).all()
        }

    for installed in installed_rows:
        cache = caches.get(installed.integration_id)
        cache_age_s: float | None = None
        tools_count: int | None = None
        cache_bytes: int | None = None
        cache_state = "missing"
        if cache:
            cache_age_s = (now - cache.fetched_at).total_seconds()
            cache_bytes = len(cache.tools_json.encode("utf-8"))
            cache_state = "present"
            try:
                tools = json.loads(cache.tools_json)
                tools_count = len(tools) if isinstance(tools, list) else None
            except Exception:
                cache_state = "invalid_json"

        rows.append(
            CacheRow(
                integration_id=installed.integration_id,
                type=installed.type,
                auth_method=installed.auth_method,
                connected=installed.connected,
                updating_tool_cache=installed.updating_tool_cache,
                cache_state=cache_state,
                cache_age_s=cache_age_s,
                tools_count=tools_count,
                cache_bytes=cache_bytes,
            )
        )
    return sorted(rows, key=lambda row: row.integration_id)


def _cache_detail(rows: list[CacheRow]) -> list[dict[str, Any]]:
    return [
        {
            "integration_id": row.integration_id,
            "type": row.type,
            "auth_method": row.auth_method,
            "connected": row.connected,
            "updating_tool_cache": row.updating_tool_cache,
            "cache_state": row.cache_state,
            "cache_age_s": row.cache_age_s,
            "tools_count": row.tools_count,
            "cache_bytes": row.cache_bytes,
        }
        for row in rows
    ]


def _load_installed_for_direct_probe(args: argparse.Namespace):
    from sqlmodel import Session, select

    from agent_port.db import engine
    from agent_port.models.integration import InstalledIntegration
    from agent_port.models.oauth import OAuthState

    org_id = _resolve_org_id(args)
    if org_id is None:
        raise RuntimeError(
            "could not resolve org_id from --org-id, --api-key, or a single local org"
        )
    if not args.integration_id:
        raise RuntimeError("--direct-upstream requires --integration-id")

    with Session(engine) as db:
        installed = db.exec(
            select(InstalledIntegration)
            .where(InstalledIntegration.org_id == org_id)
            .where(InstalledIntegration.integration_id == args.integration_id)
        ).first()
        if not installed:
            raise RuntimeError(f"installed integration not found: {args.integration_id}")
        oauth_state = db.exec(
            select(OAuthState)
            .where(OAuthState.org_id == org_id)
            .where(OAuthState.integration_id == args.integration_id)
        ).first()

        db.refresh(installed)
        db.expunge(installed)
        if oauth_state:
            db.refresh(oauth_state)
            db.expunge(oauth_state)

    return installed, oauth_state


async def _direct_upstream_list_tools(args: argparse.Namespace) -> list[dict[str, Any]]:
    from agent_port import api_client
    from agent_port.integrations import registry as integration_registry
    from agent_port.integrations.types import CustomIntegration
    from agent_port.mcp import client as mcp_client

    installed, oauth_state = _load_installed_for_direct_probe(args)
    bundled = integration_registry.get(installed.integration_id, org_id=installed.org_id)
    if isinstance(bundled, CustomIntegration):
        return api_client.list_tools(bundled)
    return await mcp_client.list_tools(installed, oauth_state)


async def _run_mcp_probes(args: argparse.Namespace) -> list[ProbeResult]:
    headers = _header_map(args)
    mcp_endpoint = _mcp_url(args.server_url)
    results: list[ProbeResult] = []

    async def cold_initialize() -> str:
        async with streamablehttp_client(
            mcp_endpoint,
            headers=headers,
            timeout=args.timeout,
            sse_read_timeout=args.sse_read_timeout,
        ) as (read_stream, write_stream, _):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
        return "initialized"

    results.append(
        await _measure(
            "mcp.cold.initialize",
            cold_initialize,
            iterations=args.iterations,
            warmup=args.warmup,
            detail_fn=lambda _: "new streamable-http session each sample",
        )
    )

    async def cold_tools_list() -> Any:
        async with streamablehttp_client(
            mcp_endpoint,
            headers=headers,
            timeout=args.timeout,
            sse_read_timeout=args.sse_read_timeout,
        ) as (read_stream, write_stream, _):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                return await session.list_tools()

    results.append(
        await _measure(
            "mcp.cold.tools/list",
            cold_tools_list,
            iterations=args.iterations,
            warmup=args.warmup,
            detail_fn=_tool_list_detail,
        )
    )

    try:
        async with streamablehttp_client(
            mcp_endpoint,
            headers=headers,
            timeout=args.timeout,
            sse_read_timeout=args.sse_read_timeout,
        ) as (read_stream, write_stream, _):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()

                results.append(
                    await _measure(
                        "mcp.warm.tools/list",
                        session.list_tools,
                        iterations=args.iterations,
                        warmup=args.warmup,
                        detail_fn=_tool_list_detail,
                    )
                )

                results.append(
                    await _measure(
                        "mcp.warm.call:list_installed_integrations",
                        lambda: session.call_tool("agentport__list_installed_integrations", {}),
                        iterations=args.iterations,
                        warmup=args.warmup,
                        detail_fn=_mcp_call_detail,
                    )
                )

                list_args = {}
                list_name = "mcp.warm.call:list_integration_tools(all)"
                if args.integration_id:
                    list_args["integration_id"] = args.integration_id
                    list_name = f"mcp.warm.call:list_integration_tools({args.integration_id})"
                results.append(
                    await _measure(
                        list_name,
                        lambda: session.call_tool("agentport__list_integration_tools", list_args),
                        iterations=args.iterations,
                        warmup=args.warmup,
                        detail_fn=_mcp_call_detail,
                    )
                )

                if args.integration_id and args.tool_name:
                    describe_args = {
                        "integration_id": args.integration_id,
                        "tool_name": args.tool_name,
                    }
                    results.append(
                        await _measure(
                            f"mcp.warm.call:describe_tool({args.integration_id}/{args.tool_name})",
                            lambda: session.call_tool("agentport__describe_tool", describe_args),
                            iterations=args.iterations,
                            warmup=args.warmup,
                            detail_fn=_mcp_call_detail,
                        )
                    )

                if args.call_tool:
                    if not args.integration_id or not args.tool_name:
                        raise RuntimeError("--call-tool requires --integration-id and --tool-name")
                    call_args = {
                        "integration_id": args.integration_id,
                        "tool_name": args.tool_name,
                        "arguments": args.arguments,
                        "additional_info": "Latency probe requested by a developer.",
                    }
                    results.append(
                        await _measure(
                            f"mcp.warm.call:call_tool({args.integration_id}/{args.tool_name})",
                            lambda: session.call_tool("agentport__call_tool", call_args),
                            iterations=args.iterations,
                            warmup=args.warmup,
                            detail_fn=_mcp_call_detail,
                        )
                    )
    except (Exception, BaseExceptionGroup) as exc:
        results.append(
            ProbeResult(
                name="mcp.warm.session",
                errors=[_short_error(exc)],
                detail="failed to create reusable MCP session",
            )
        )

    return results


async def _run_rest_probes(args: argparse.Namespace) -> list[ProbeResult]:
    headers = _header_map(args)
    results: list[ProbeResult] = []
    async with httpx.AsyncClient(headers=headers, timeout=args.timeout) as client:
        results.append(
            await _measure(
                "rest.GET /api/tools",
                lambda: client.get(_api_url(args.server_url, "/api/tools")),
                iterations=args.iterations,
                warmup=args.warmup,
                detail_fn=_http_detail,
            )
        )
        if args.integration_id:
            path = f"/api/tools/{args.integration_id}"
            results.append(
                await _measure(
                    f"rest.GET {path}",
                    lambda: client.get(_api_url(args.server_url, path)),
                    iterations=args.iterations,
                    warmup=args.warmup,
                    detail_fn=_http_detail,
                )
            )
    return results


async def _run_direct_upstream_probes(args: argparse.Namespace) -> list[ProbeResult]:
    return [
        await _measure(
            f"direct_upstream.list_tools({args.integration_id})",
            lambda: _direct_upstream_list_tools(args),
            iterations=args.iterations,
            warmup=args.warmup,
            detail_fn=_tool_list_detail,
        )
    ]


def _fmt_ms(value: float | None) -> str:
    if value is None:
        return "-"
    if value >= 1000:
        return f"{value:,.0f}"
    return f"{value:,.1f}"


def _print_results(results: list[ProbeResult]) -> None:
    print("\nLatency")
    header = f"{'stage':52} {'n':>3} {'min':>8} {'p50':>8} {'p95':>8} {'max':>8}  detail"
    print(header)
    print("-" * len(header))
    for result in results:
        summary = result.summary()
        error_suffix = f" errors={len(result.errors)}" if result.errors else ""
        detail = f"{result.detail}{error_suffix}".strip()
        print(
            f"{result.name[:52]:52} "
            f"{summary['count']:>3} "
            f"{_fmt_ms(summary['min_ms']):>8} "
            f"{_fmt_ms(summary['p50_ms']):>8} "
            f"{_fmt_ms(summary['p95_ms']):>8} "
            f"{_fmt_ms(summary['max_ms']):>8}  "
            f"{detail}"
        )
        if result.errors:
            print(f"{'':52} first_error={result.errors[0]}")


def _print_cache(rows: list[CacheRow]) -> None:
    if not rows:
        print("\nLocal cache state: unavailable")
        return

    print("\nLocal cache state")
    header = (
        f"{'integration':22} {'type':10} {'auth':6} {'conn':>5} {'refresh':>7} "
        f"{'cache':12} {'age_s':>9} {'tools':>7} {'bytes':>9}"
    )
    print(header)
    print("-" * len(header))
    for row in rows:
        age = "-" if row.cache_age_s is None else f"{row.cache_age_s:,.0f}"
        tools = "-" if row.tools_count is None else f"{row.tools_count:,}"
        cache_bytes = "-" if row.cache_bytes is None else f"{row.cache_bytes:,}"
        print(
            f"{row.integration_id[:22]:22} {row.type[:10]:10} {row.auth_method[:6]:6} "
            f"{str(row.connected):>5} {str(row.updating_tool_cache):>7} "
            f"{row.cache_state[:12]:12} {age:>9} {tools:>7} {cache_bytes:>9}"
        )


def _print_interpretation(results: list[ProbeResult]) -> None:
    successful = [result for result in results if result.ok]
    if not successful:
        return

    slowest = max(successful, key=lambda result: result.percentile(50) or 0)
    print("\nReadout")
    print(f"- Slowest p50 stage: {slowest.name} at {_fmt_ms(slowest.percentile(50))} ms.")

    by_name = {result.name: result for result in successful}
    cold_init = by_name.get("mcp.cold.initialize")
    warm_tools = by_name.get("mcp.warm.tools/list")
    if cold_init and warm_tools:
        cold = cold_init.percentile(50) or 0
        warm = warm_tools.percentile(50) or 0
        if cold > max(100, warm * 3):
            print("- Cold MCP session setup dominates. Reusing sessions should improve latency.")

    direct = [result for result in successful if result.name.startswith("direct_upstream.")]
    mcp_list = [
        result
        for result in successful
        if result.name.startswith("mcp.warm.call:list_integration_tools(")
    ]
    if direct and mcp_list:
        direct_ms = direct[0].percentile(50) or 0
        gateway_ms = mcp_list[0].percentile(50) or 0
        if direct_ms > gateway_ms * 2:
            print("- Upstream tool discovery is slower than the AgentPort cached path.")
        elif gateway_ms > direct_ms * 2:
            print("- AgentPort cache, policy, DB, or MCP wrapping is slower than direct upstream.")

    rest_all = by_name.get("rest.GET /api/tools")
    if rest_all and rest_all.percentile(50) and rest_all.percentile(50) > 1000:
        print(
            "- REST /api/tools is slow. Check for stale or missing tool caches "
            "causing refresh work."
        )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Profile AgentPort MCP latency across transport, cache, REST, and upstream stages."
        )
    )
    parser.add_argument(
        "--server-url",
        default=os.getenv("AGENTPORT_BASE_URL") or os.getenv("BASE_URL") or "http://localhost:4747",
        help="AgentPort base URL, without /mcp. Defaults to AGENTPORT_BASE_URL or localhost.",
    )
    parser.add_argument(
        "--api-key",
        default=os.getenv("AGENTPORT_API_KEY"),
        help="AgentPort API key. Defaults to AGENTPORT_API_KEY.",
    )
    parser.add_argument(
        "--bearer-token",
        default=os.getenv("AGENTPORT_BEARER_TOKEN"),
        help="Bearer token alternative to --api-key. Defaults to AGENTPORT_BEARER_TOKEN.",
    )
    parser.add_argument(
        "--org-id",
        help="Local org id for DB/cache and direct-upstream probes. Usually inferred from API key.",
    )
    parser.add_argument("--integration-id", help="Installed integration id to focus on.")
    parser.add_argument("--tool-name", help="Tool name to describe or call.")
    parser.add_argument(
        "--arguments",
        type=_parse_arguments,
        default={},
        help="JSON object used only with --call-tool. Default: {}.",
    )
    parser.add_argument(
        "--call-tool",
        action="store_true",
        help="Actually invoke --integration-id/--tool-name through agentport__call_tool.",
    )
    parser.add_argument(
        "--direct-upstream",
        action="store_true",
        help="Also time direct upstream list_tools using local DB credentials.",
    )
    parser.add_argument("--skip-mcp", action="store_true", help="Skip MCP endpoint probes.")
    parser.add_argument("--skip-rest", action="store_true", help="Skip REST comparison probes.")
    parser.add_argument("--skip-db", action="store_true", help="Skip local DB/cache inspection.")
    parser.add_argument("--iterations", type=int, default=5, help="Measured samples per stage.")
    parser.add_argument("--warmup", type=int, default=1, help="Warmup samples per stage.")
    parser.add_argument("--timeout", type=float, default=30.0, help="HTTP request timeout seconds.")
    parser.add_argument(
        "--sse-read-timeout",
        type=float,
        default=300.0,
        help="MCP SSE read timeout seconds.",
    )
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    return parser


async def _main_async(args: argparse.Namespace) -> int:
    needs_endpoint_auth = not args.skip_mcp or not args.skip_rest
    if needs_endpoint_auth and not args.api_key and not args.bearer_token:
        print(
            "No auth provided. Pass --api-key, --bearer-token, or set AGENTPORT_API_KEY.",
            file=sys.stderr,
        )
        return 2
    if args.call_tool and (not args.integration_id or not args.tool_name):
        print("--call-tool requires --integration-id and --tool-name.", file=sys.stderr)
        return 2

    cache_rows: list[CacheRow] = []
    if not args.skip_db:
        try:
            cache_rows = _load_cache_rows(args)
        except Exception as exc:
            if args.json:
                cache_rows = []
            else:
                print(f"Local cache state unavailable: {_short_error(exc)}", file=sys.stderr)

    results: list[ProbeResult] = []
    if not args.skip_mcp:
        results.extend(await _run_mcp_probes(args))
    if not args.skip_rest:
        results.extend(await _run_rest_probes(args))
    if args.direct_upstream:
        results.extend(await _run_direct_upstream_probes(args))

    if args.json:
        print(
            json.dumps(
                {
                    "server_url": args.server_url,
                    "headers": _redacted_header_map(args),
                    "cache": _cache_detail(cache_rows),
                    "results": [result.summary() for result in results],
                },
                indent=2,
            )
        )
        return 0

    print("AgentPort MCP speed probe")
    print(f"server_url={args.server_url}")
    print(f"mcp_url={_mcp_url(args.server_url)}")
    print(f"headers={_redacted_header_map(args)}")
    print(f"iterations={args.iterations} warmup={args.warmup}")
    if not args.skip_db:
        _print_cache(cache_rows)
    _print_results(results)
    _print_interpretation(results)
    return 0


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()
    return asyncio.run(_main_async(args))


if __name__ == "__main__":
    raise SystemExit(main())
