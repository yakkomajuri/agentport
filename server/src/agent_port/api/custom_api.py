"""CRUD and live testing for user-defined REST API integrations."""

import json
import logging
import re
import time
import uuid
from datetime import datetime
from typing import Any

import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from agent_port import api_client
from agent_port.db import get_session
from agent_port.dependencies import AgentAuth, get_agent_auth
from agent_port.integrations.registry import CUSTOM_API_PREFIX
from agent_port.integrations.types import ApiTool
from agent_port.mcp.notifications import notify_tools_changed
from agent_port.mcp.refresh import refresh_one
from agent_port.models.custom_api_integration import CustomApiIntegration
from agent_port.models.integration import InstalledIntegration
from agent_port.models.tool_cache import ToolCache
from agent_port.token_auth import build_token_auth_headers, validate_token_auth_config
from agent_port.upstream_safety import UnsafeUpstreamUrlError, validate_safe_url

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/integrations/custom-api", tags=["custom-api-integrations"])

_SLUG_RE = re.compile(r"[^a-z0-9]+")
_SLUG_MAX = 40
_TOOL_NAME_RE = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
_PARAM_NAME_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")
_PATH_PARAM_RE = re.compile(r"\{([a-zA-Z_][a-zA-Z0-9_]*)\}")
_METHODS = {"GET", "POST", "PUT", "PATCH", "DELETE"}
_MAX_TEST_REQUEST_BODY_BYTES = 64 * 1024
_MAX_TEST_RESPONSE_BYTES = 1024 * 1024
_TEST_TIMEOUT = httpx.Timeout(connect=3.0, read=8.0, write=3.0, pool=3.0)


class CreateCustomApiRequest(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    description: str | None = Field(default=None, max_length=500)
    base_url: str = Field(min_length=1, max_length=2000)
    token_header: str = "Authorization"
    token_format: str = "Bearer {token}"
    tools: list[ApiTool] = Field(default_factory=list)


class UpdateCustomApiRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    description: str | None = Field(default=None, max_length=500)
    base_url: str | None = Field(default=None, min_length=1, max_length=2000)
    token_header: str | None = None
    token_format: str | None = None
    tools: list[ApiTool] | None = None


class TestCustomApiRequest(BaseModel):
    base_url: str = Field(min_length=1, max_length=2000)
    token_header: str = "Authorization"
    token_format: str = "Bearer {token}"
    token: str = Field(default="", max_length=10000)
    tool: ApiTool
    args: dict[str, Any] = Field(default_factory=dict)


def _slugify(name: str) -> str:
    base = _SLUG_RE.sub("_", name.lower()).strip("_")
    if not base:
        base = "api"
    return base[:_SLUG_MAX]


def _allocate_integration_id(session: Session, org_id, name: str) -> str:
    slug = _slugify(name)
    candidate = f"{CUSTOM_API_PREFIX}{slug}"
    suffix = 2
    while True:
        existing = session.exec(
            select(CustomApiIntegration)
            .where(CustomApiIntegration.org_id == org_id)
            .where(CustomApiIntegration.integration_id == candidate)
        ).first()
        if not existing:
            return candidate
        candidate = f"{CUSTOM_API_PREFIX}{slug}_{suffix}"
        suffix += 1


def _http_400(message: str) -> HTTPException:
    return HTTPException(status_code=400, detail=message)


def _validate_base_url(base_url: str) -> None:
    try:
        validate_safe_url(base_url, allow_query=False)
    except UnsafeUpstreamUrlError as exc:
        raise _http_400(str(exc)) from exc


def _validate_auth(token_header: str, token_format: str) -> None:
    try:
        validate_token_auth_config(token_header, token_format)
    except ValueError as exc:
        raise _http_400(str(exc)) from exc


def _path_params(path: str) -> list[str]:
    return _PATH_PARAM_RE.findall(path)


def _validate_tool_definitions(tools: list[ApiTool]) -> list[ApiTool]:
    seen_tools: set[str] = set()
    normalized: list[ApiTool] = []
    for tool in tools:
        if not _TOOL_NAME_RE.fullmatch(tool.name):
            raise _http_400(f"Tool name '{tool.name}' must match /^[a-z][a-z0-9_]{{0,63}}$/")
        if tool.name in seen_tools:
            raise _http_400(f"Tool name '{tool.name}' is duplicated")
        seen_tools.add(tool.name)

        method = tool.method.upper()
        if method not in _METHODS:
            raise _http_400(f"Tool '{tool.name}' has unsupported method '{tool.method}'")
        if not tool.path.startswith("/"):
            raise _http_400(f"Tool '{tool.name}' path must start with '/'")

        param_names: set[str] = set()
        for param in tool.params:
            if not _PARAM_NAME_RE.fullmatch(param.name):
                raise _http_400(
                    f"Param name '{param.name}' in tool '{tool.name}' must match "
                    "/^[a-zA-Z_][a-zA-Z0-9_]*$/"
                )
            if param.name in param_names:
                raise _http_400(f"Param name '{param.name}' is duplicated in tool '{tool.name}'")
            param_names.add(param.name)

        for path_param in _path_params(tool.path):
            if path_param not in param_names:
                raise _http_400(
                    f"Path param '{{{path_param}}}' in tool '{tool.name}' has no matching param"
                )

        normalized.append(tool.model_copy(update={"method": method}))
    return normalized


def _tools_to_json(tools: list[ApiTool]) -> str:
    normalized = _validate_tool_definitions(tools)
    return json.dumps([tool.model_dump(mode="json") for tool in normalized])


def _tools_from_json(tools_json: str) -> list[dict]:
    parsed = json.loads(tools_json)
    if not isinstance(parsed, list):
        raise ValueError("tools_json must be a list")
    tools = _validate_tool_definitions([ApiTool(**item) for item in parsed])
    return [tool.model_dump(mode="json") for tool in tools]


def _serialize(row: CustomApiIntegration) -> dict:
    return {
        "id": str(row.id),
        "integration_id": row.integration_id,
        "name": row.name,
        "description": row.description,
        "base_url": row.base_url,
        "token_header": row.token_header,
        "token_format": row.token_format,
        "tools": _tools_from_json(row.tools_json),
        "created_at": row.created_at.isoformat(),
        "updated_at": row.updated_at.isoformat(),
    }


def _get_row(session: Session, org_id, custom_id: uuid.UUID) -> CustomApiIntegration:
    row = session.exec(
        select(CustomApiIntegration)
        .where(CustomApiIntegration.id == custom_id)
        .where(CustomApiIntegration.org_id == org_id)
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail="Custom API integration not found")
    return row


def _installed_row(session: Session, org_id, integration_id: str) -> InstalledIntegration | None:
    return session.exec(
        select(InstalledIntegration)
        .where(InstalledIntegration.org_id == org_id)
        .where(InstalledIntegration.integration_id == integration_id)
    ).first()


def _invalidate_tool_cache(session: Session, org_id, integration_id: str) -> None:
    cache = session.exec(
        select(ToolCache)
        .where(ToolCache.org_id == org_id)
        .where(ToolCache.integration_id == integration_id)
    ).first()
    if cache:
        session.delete(cache)


def _redact(text: str, token: str) -> str:
    if token:
        return text.replace(token, "[redacted]")
    return text


def _redact_result_token(result: dict, token: str) -> dict:
    if not token:
        return result
    redacted = {**result}
    content = []
    for item in result.get("content", []):
        if isinstance(item, dict) and isinstance(item.get("text"), str):
            content.append({**item, "text": _redact(item["text"], token)})
        else:
            content.append(item)
    redacted["content"] = content
    return redacted


def _audit_test_run(
    agent_auth: AgentAuth,
    *,
    target_host: str,
    tool_name: str,
    method: str,
    path_template: str,
    status_code: int | None,
    error_class: str | None,
    duration_ms: int,
) -> None:
    identity = (
        f"api_key:{agent_auth.api_key.key_prefix}"
        if agent_auth.api_key
        else f"user:{agent_auth.user.id if agent_auth.user else 'unknown'}"
    )
    logger.info(
        "custom_api_test org_id=%s identity=%s target_host=%s method=%s "
        "path_template=%s tool_name=%s status_code=%s error_class=%s duration_ms=%d",
        agent_auth.org.id,
        identity,
        target_host,
        method,
        path_template,
        tool_name,
        status_code,
        error_class,
        duration_ms,
    )


@router.get("")
def list_custom_api(
    session: Session = Depends(get_session),
    agent_auth: AgentAuth = Depends(get_agent_auth),
) -> list[dict]:
    rows = session.exec(
        select(CustomApiIntegration).where(CustomApiIntegration.org_id == agent_auth.org.id)
    ).all()
    return [_serialize(row) for row in rows]


@router.post("", status_code=201)
def create_custom_api(
    body: CreateCustomApiRequest,
    session: Session = Depends(get_session),
    agent_auth: AgentAuth = Depends(get_agent_auth),
) -> dict:
    _validate_base_url(body.base_url)
    _validate_auth(body.token_header, body.token_format)
    tools_json = _tools_to_json(body.tools)

    row = CustomApiIntegration(
        org_id=agent_auth.org.id,
        integration_id=_allocate_integration_id(session, agent_auth.org.id, body.name),
        name=body.name,
        description=body.description,
        base_url=body.base_url,
        token_header=body.token_header,
        token_format=body.token_format,
        tools_json=tools_json,
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return _serialize(row)


@router.get("/{custom_id}")
def get_custom_api(
    custom_id: uuid.UUID,
    session: Session = Depends(get_session),
    agent_auth: AgentAuth = Depends(get_agent_auth),
) -> dict:
    return _serialize(_get_row(session, agent_auth.org.id, custom_id))


@router.patch("/{custom_id}")
def update_custom_api(
    custom_id: uuid.UUID,
    body: UpdateCustomApiRequest,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
    agent_auth: AgentAuth = Depends(get_agent_auth),
) -> dict:
    row = _get_row(session, agent_auth.org.id, custom_id)

    runtime_changed = False
    base_url_changed = False

    if body.name is not None:
        row.name = body.name
    if body.description is not None:
        row.description = body.description
    if body.base_url is not None and body.base_url != row.base_url:
        _validate_base_url(body.base_url)
        row.base_url = body.base_url
        runtime_changed = True
        base_url_changed = True
    if body.token_header is not None and body.token_header != row.token_header:
        _validate_auth(body.token_header, row.token_format)
        row.token_header = body.token_header
        runtime_changed = True
    if body.token_format is not None and body.token_format != row.token_format:
        _validate_auth(row.token_header, body.token_format)
        row.token_format = body.token_format
        runtime_changed = True
    if body.tools is not None:
        tools_json = _tools_to_json(body.tools)
        if tools_json != row.tools_json:
            row.tools_json = tools_json
            runtime_changed = True

    row.updated_at = datetime.utcnow()

    installed = _installed_row(session, agent_auth.org.id, row.integration_id)
    if installed and base_url_changed:
        installed.url = row.base_url
        session.add(installed)
    if installed and runtime_changed:
        _invalidate_tool_cache(session, agent_auth.org.id, row.integration_id)

    session.add(row)
    session.commit()
    session.refresh(row)

    if installed and runtime_changed:
        if installed.connected:
            background_tasks.add_task(refresh_one, agent_auth.org.id, row.integration_id)
        else:
            background_tasks.add_task(notify_tools_changed, agent_auth.org.id)

    return _serialize(row)


@router.delete("/{custom_id}", status_code=204)
def delete_custom_api(
    custom_id: uuid.UUID,
    session: Session = Depends(get_session),
    agent_auth: AgentAuth = Depends(get_agent_auth),
) -> None:
    row = _get_row(session, agent_auth.org.id, custom_id)
    installed = _installed_row(session, agent_auth.org.id, row.integration_id)
    if installed:
        raise HTTPException(
            status_code=409,
            detail="Uninstall this integration before deleting its definition",
        )

    session.delete(row)
    session.commit()


@router.post("/test")
async def test_custom_api(
    body: TestCustomApiRequest,
    agent_auth: AgentAuth = Depends(get_agent_auth),
) -> dict:
    _validate_base_url(body.base_url)
    _validate_auth(body.token_header, body.token_format)
    tool = _validate_tool_definitions([body.tool])[0]

    try:
        target = validate_safe_url(
            api_client._build_url(body.base_url, tool.path, body.args),  # noqa: SLF001
            allow_query=True,
        )
        headers = build_token_auth_headers(body.token_header, body.token_format, body.token)
    except (UnsafeUpstreamUrlError, ValueError) as exc:
        raise _http_400(str(exc)) from exc

    start = time.perf_counter()
    error_class: str | None = None
    try:
        result = await api_client.dispatch_api_tool(
            base_url=body.base_url,
            tool_def=tool,
            args=body.args,
            headers=headers,
            timeout=_TEST_TIMEOUT,
            follow_redirects=False,
            max_request_body_bytes=_MAX_TEST_REQUEST_BODY_BYTES,
            max_response_bytes=_MAX_TEST_RESPONSE_BYTES,
        )
    except Exception as exc:
        error_class = exc.__class__.__name__
        duration_ms = int((time.perf_counter() - start) * 1000)
        result = {
            "content": [
                {"type": "text", "text": f"API test failed: {_redact(str(exc), body.token)}"}
            ],
            "isError": True,
            "status_code": None,
            "duration_ms": duration_ms,
        }
    else:
        duration_ms = int(result.get("duration_ms") or (time.perf_counter() - start) * 1000)
        if result.get("isError"):
            error_class = "UpstreamError"

    result = _redact_result_token(result, body.token)
    _audit_test_run(
        agent_auth,
        target_host=target.hostname,
        tool_name=tool.name,
        method=tool.method,
        path_template=tool.path,
        status_code=result.get("status_code"),
        error_class=error_class,
        duration_ms=duration_ms,
    )
    return result
