from typing import Annotated, Any, Awaitable, Callable, Literal, Union

from pydantic import BaseModel, ConfigDict, Field


class OAuthAuth(BaseModel):
    method: Literal["oauth"] = "oauth"
    note: str | None = None
    registration_url: str | None = None
    # Pre-configured OAuth fields (when AgentPort owns the OAuth app).
    # When `provider` is set, the auth flow uses these endpoints directly
    # instead of MCP discovery + Dynamic Client Registration.
    provider: str | None = None  # e.g. "google" — maps to env vars
    authorization_url: str | None = None
    token_url: str | None = None
    scopes: list[str] | None = None
    scope_param: str = "scope"  # Slack user OAuth uses "user_scope" instead of "scope"
    extra_auth_params: dict[str, str] = {}


class TokenAuth(BaseModel):
    method: Literal["token"] = "token"
    label: str
    header: str
    format: str  # e.g. "Bearer {token}"


class EnvVarAuth(BaseModel):
    method: Literal["env_var"] = "env_var"
    env: str
    label: str
    acquire_url: str | None = None


AuthMethod = Annotated[Union[OAuthAuth, TokenAuth, EnvVarAuth], Field(discriminator="method")]


class Param(BaseModel):
    """A single tool parameter, used by both ApiTool and CustomTool."""

    name: str
    type: str = "string"  # JSON Schema type: string, integer, number, boolean, array, object
    description: str | None = None
    required: bool = False
    default: Any = None
    enum: list[str] | None = None
    items: str | None = None  # for type="array": the type of each item (e.g. "string")
    query: bool = False  # True → query string param (ApiTool only; ignored by CustomTool)
    schema_override: dict | None = (
        None  # raw JSON Schema for this param (overrides all other fields)
    )


class ApiTool(BaseModel):
    """Declarative definition of a tool backed by a REST API call.

    Suitable for simple request/response patterns. Use CustomTool when
    you need arbitrary Python logic (e.g. MIME encoding, multi-step calls).
    """

    name: str
    description: str
    method: str  # HTTP method: GET, POST, PUT, PATCH, DELETE
    path: str  # URL path with {param} placeholders for path params
    params: list[Param] = []


class CustomTool(BaseModel):
    """Tool whose execution is handled by a Python callable.

    The `run` callable receives (args, auth_headers) and returns an
    MCP-compatible result dict: {"content": [...], "isError": bool}.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    name: str
    description: str
    params: list[Param] = []
    # Excluded from serialization — not sent to clients.
    run: Callable[[dict, dict], Awaitable[dict]] = Field(exclude=True)


class BundledIntegration(BaseModel):
    id: str
    name: str
    auth: list[AuthMethod]
    description: str | None = None
    docs_url: str | None = None
    # Optional: maps tool name → category label for grouping in the UI
    tool_categories: dict[str, str] = {}

    def is_available(self) -> tuple[bool, str | None]:
        """Return (available, reason). Override in integrations that require env-level setup."""
        return True, None


class RemoteMcpIntegration(BundledIntegration):
    type: Literal["remote_mcp"] = "remote_mcp"
    url: str


class CustomIntegration(BundledIntegration):
    """HTTP-backed integration supporting both declarative and code-backed tools.

    - ApiTool: fully declarative (method, path, params). No code needed.
      Safe for a future SaaS "build your own integration" UI.
    - CustomTool: arbitrary Python execution via the `run` callable. Used when
      the declarative interface isn't expressive enough (e.g. MIME encoding).
    """

    type: Literal["custom"] = "custom"
    base_url: str
    tools: list[Union[ApiTool, CustomTool]] = []

    async def validate_auth(self, token: str) -> None:
        """Called on install with token auth. Raise to reject.

        Default is a no-op so OAuth-only customs stay permissive. Subclasses
        that support token auth should override to hit a cheap authenticated
        endpoint and raise with a clear message on failure.
        """
        return


# Keep ApiIntegration as an alias so external code can migrate gradually.
# New integrations should use CustomIntegration directly.
ApiIntegration = CustomIntegration

Integration = RemoteMcpIntegration | CustomIntegration
