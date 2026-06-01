import re

_HEADER_NAME_RE = re.compile(r"^[!#$%&'*+.^_`|~0-9A-Za-z-]{1,128}$")


def is_no_auth(token_header: str, token_format: str) -> bool:
    """Both empty means "no authentication header is sent"."""
    return not token_header and not token_format


def validate_token_auth_config(token_header: str, token_format: str) -> None:
    if is_no_auth(token_header, token_format):
        return
    if not _HEADER_NAME_RE.fullmatch(token_header):
        raise ValueError("token_header must be a valid HTTP header name")
    if "{token}" not in token_format:
        raise ValueError("token_format must contain the literal substring '{token}'")
    if "\r" in token_format or "\n" in token_format:
        raise ValueError("token_format must not contain newlines")


def build_token_auth_headers(
    token_header: str,
    token_format: str,
    token: str,
) -> dict[str, str]:
    validate_token_auth_config(token_header, token_format)
    if is_no_auth(token_header, token_format):
        return {}
    if "\r" in token or "\n" in token:
        raise ValueError("token must not contain newlines")
    value = token_format.replace("{token}", token)
    if "\r" in value or "\n" in value:
        raise ValueError("token auth header value must not contain newlines")
    return {token_header: value}
