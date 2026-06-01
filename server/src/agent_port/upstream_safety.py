import ipaddress
import socket
from dataclasses import dataclass
from urllib.parse import SplitResult, urlsplit


class UnsafeUpstreamUrlError(ValueError):
    pass


@dataclass(frozen=True)
class SafeUpstreamURL:
    raw_url: str
    parsed: SplitResult
    hostname: str
    port: int
    path: str
    resolved_ips: tuple[str, ...]


def _blocked_ip(address: str) -> bool:
    ip = ipaddress.ip_address(address)
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        ip = ip.ipv4_mapped
    return (
        ip.is_loopback
        or ip.is_private
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    )


def _resolve_host(hostname: str, port: int) -> tuple[str, ...]:
    try:
        addrinfos = socket.getaddrinfo(hostname, port, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise UnsafeUpstreamUrlError("Host could not be resolved") from exc

    resolved = sorted({info[4][0] for info in addrinfos})
    if not resolved:
        raise UnsafeUpstreamUrlError("Host could not be resolved")
    blocked = [ip for ip in resolved if _blocked_ip(ip)]
    if blocked:
        raise UnsafeUpstreamUrlError("Host resolves to a blocked network range")
    return tuple(resolved)


def validate_safe_url(raw_url: str, *, allow_query: bool = True) -> SafeUpstreamURL:
    try:
        parsed = urlsplit(raw_url)
    except ValueError as exc:
        raise UnsafeUpstreamUrlError("URL is malformed") from exc

    if parsed.scheme not in {"http", "https"}:
        raise UnsafeUpstreamUrlError("URL scheme must be http or https")
    if parsed.username or parsed.password:
        raise UnsafeUpstreamUrlError("URL must not include credentials")
    if not parsed.hostname:
        raise UnsafeUpstreamUrlError("URL host is required")
    if parsed.fragment:
        raise UnsafeUpstreamUrlError("URL fragments are not allowed")
    if parsed.query and not allow_query:
        raise UnsafeUpstreamUrlError("URL queries are not allowed here")

    try:
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
    except ValueError as exc:
        raise UnsafeUpstreamUrlError("URL port is malformed") from exc

    if port <= 0 or port > 65535:
        raise UnsafeUpstreamUrlError("URL port is out of range")

    hostname = parsed.hostname.rstrip(".").lower()
    if not hostname:
        raise UnsafeUpstreamUrlError("URL host is required")

    return SafeUpstreamURL(
        raw_url=raw_url,
        parsed=parsed,
        hostname=hostname,
        port=port,
        path=parsed.path or "/",
        resolved_ips=_resolve_host(hostname, port),
    )
