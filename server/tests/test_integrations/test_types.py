from agent_port.integrations.types import (
    ApiTool,
    CustomIntegration,
    CustomTool,
    EnvVarAuth,
    OAuthAuth,
    RemoteMcpIntegration,
    TokenAuth,
)


def test_oauth_auth():
    auth = OAuthAuth(method="oauth")
    assert auth.method == "oauth"
    assert auth.note is None
    assert auth.provider is None


def test_oauth_auth_configured():
    auth = OAuthAuth(
        method="oauth",
        provider="google",
        authorization_url="https://accounts.google.com/o/oauth2/v2/auth",
        token_url="https://oauth2.googleapis.com/token",
        scopes=["https://www.googleapis.com/auth/gmail.modify"],
        extra_auth_params={"access_type": "offline", "prompt": "consent"},
    )
    assert auth.method == "oauth"
    assert auth.provider == "google"
    assert auth.authorization_url == "https://accounts.google.com/o/oauth2/v2/auth"
    assert "access_type" in auth.extra_auth_params


def test_token_auth():
    auth = TokenAuth(
        method="token", label="API Key", header="Authorization", format="Bearer {token}"
    )
    assert auth.label == "API Key"
    assert auth.format == "Bearer {token}"


def test_env_var_auth():
    auth = EnvVarAuth(method="env_var", env="MY_KEY", label="My Key")
    assert auth.env == "MY_KEY"
    assert auth.acquire_url is None


def test_remote_mcp_integration():
    integration = RemoteMcpIntegration(
        id="test",
        name="Test",
        url="https://example.com/mcp",
        auth=[OAuthAuth(method="oauth")],
    )
    assert integration.type == "remote_mcp"
    assert integration.url == "https://example.com/mcp"


def test_api_tool_def():
    tool = ApiTool(
        name="list_items",
        description="List items",
        input_schema={"type": "object", "properties": {"q": {"type": "string"}}},
        method="GET",
        path="/v1/items",
        query_params=["q"],
    )
    assert tool.name == "list_items"
    assert tool.method == "GET"


def test_custom_tool_def():
    async def _run(args: dict, auth_headers: dict) -> dict:
        return {"content": [{"type": "text", "text": "ok"}], "isError": False}

    tool = CustomTool(
        name="send_email",
        description="Send an email",
        input_schema={"type": "object"},
        run=_run,
    )
    assert tool.name == "send_email"
    assert tool.run is _run


def test_custom_tool_def_run_excluded_from_dump():
    async def _run(args: dict, auth_headers: dict) -> dict:
        return {"content": [], "isError": False}

    tool = CustomTool(name="foo", description="bar", input_schema={}, run=_run)
    dumped = tool.model_dump()
    assert "run" not in dumped
    assert dumped["name"] == "foo"


def test_custom_integration_with_mixed_tools():
    async def _run(args: dict, auth_headers: dict) -> dict:
        return {"content": [], "isError": False}

    integration = CustomIntegration(
        id="test_api",
        name="Test API",
        base_url="https://api.example.com",
        auth=[OAuthAuth(method="oauth", provider="test")],
        tools=[
            ApiTool(
                name="get_item",
                description="Get an item",
                input_schema={"type": "object"},
                method="GET",
                path="/v1/items/{id}",
            ),
            CustomTool(
                name="create_item",
                description="Create with custom logic",
                input_schema={"type": "object"},
                run=_run,
            ),
        ],
    )
    assert integration.type == "custom"
    assert integration.base_url == "https://api.example.com"
    assert len(integration.tools) == 2
    assert isinstance(integration.tools[0], ApiTool)
    assert isinstance(integration.tools[1], CustomTool)


def test_custom_integration_dump_excludes_run():
    async def _run(args: dict, auth_headers: dict) -> dict:
        return {"content": [], "isError": False}

    integration = CustomIntegration(
        id="test",
        name="Test",
        base_url="https://api.example.com",
        auth=[],
        tools=[CustomTool(name="foo", description="bar", input_schema={}, run=_run)],
    )
    dumped = integration.model_dump()
    assert "run" not in dumped["tools"][0]
