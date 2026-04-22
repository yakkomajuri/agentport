from pydantic import Field

from agent_port.integrations.types import (
    AuthMethod,
    RemoteMcpIntegration,
    TokenAuth,
)

_TOOL_CATEGORIES: dict[str, str] = {
    # Security scanning
    "security_check": "Security scanning",
    "semgrep_scan": "Security scanning",
    "semgrep_scan_with_custom_rule": "Security scanning",
    # Code analysis
    "get_abstract_syntax_tree": "Code analysis",
    # Platform
    "semgrep_findings": "Platform",
    # Reference
    "supported_languages": "Reference",
    "semgrep_rule_schema": "Reference",
}


class SemgrepIntegration(RemoteMcpIntegration):
    id: str = "semgrep"
    name: str = "Semgrep"
    description: str = (
        "Code security scanning and static analysis. Basic scanning works without authentication."
    )
    docs_url: str = "https://semgrep.dev/docs/mcp"
    url: str = "https://mcp.semgrep.ai/mcp"
    auth: list[AuthMethod] = Field(
        default=[
            TokenAuth(
                method="token",
                label="Semgrep App Token",
                header="Authorization",
                format="Bearer {token}",
            ),
        ]
    )
    tool_categories: dict[str, str] = Field(default=_TOOL_CATEGORIES)
