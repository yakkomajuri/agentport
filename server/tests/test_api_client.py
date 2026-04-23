import pytest

from agent_port.api_client import (
    _build_body,
    _build_query,
    _build_url,
    _extract_path_params,
    get_tool_def,
    list_tools,
    params_to_input_schema,
)
from agent_port.integrations.types import ApiTool, CustomIntegration, CustomTool, OAuthAuth, Param


@pytest.fixture
def sample_integration():
    return CustomIntegration(
        id="test_api",
        name="Test API",
        base_url="https://api.example.com",
        auth=[OAuthAuth(method="oauth")],
        tools=[
            ApiTool(
                name="list_items",
                description="List items",
                method="GET",
                path="/v1/items",
                params=[
                    Param(name="q", query=True, description="Search query"),
                    Param(name="limit", type="integer", query=True, description="Max results"),
                ],
            ),
            ApiTool(
                name="get_item",
                description="Get an item",
                method="GET",
                path="/v1/items/{id}",
                params=[
                    Param(name="id", required=True, description="Item ID"),
                ],
            ),
            ApiTool(
                name="create_item",
                description="Create an item",
                method="POST",
                path="/v1/items",
                params=[
                    Param(name="name", required=True, description="Item name"),
                ],
            ),
        ],
    )


# ── URL building ──────────────────────────────────────────────────────────


def test_extract_path_params():
    assert _extract_path_params("/v1/items/{id}") == ["id"]
    assert _extract_path_params("/v1/{org}/items/{id}") == ["org", "id"]
    assert _extract_path_params("/v1/items") == []


def test_build_url_no_params():
    url = _build_url("https://api.example.com", "/v1/items", {})
    assert url == "https://api.example.com/v1/items"


def test_build_url_with_path_params():
    url = _build_url(
        "https://api.example.com",
        "/v1/items/{id}",
        {"id": "abc123"},
    )
    assert url == "https://api.example.com/v1/items/abc123"


def test_build_url_encodes_path_params():
    url = _build_url(
        "https://api.example.com",
        "/v1/items/{id}",
        {"id": "folder/item?include=secret#fragment"},
    )
    assert url == "https://api.example.com/v1/items/folder%2Fitem%3Finclude%3Dsecret%23fragment"


def test_build_url_trailing_slash():
    url = _build_url("https://api.example.com/", "/v1/items", {})
    assert url == "https://api.example.com/v1/items"


# ── Query params ──────────────────────────────────────────────────────────


def _make_tool(path: str = "/v1/items", params: list[Param] | None = None) -> ApiTool:
    return ApiTool(
        name="t",
        description="test",
        method="GET",
        path=path,
        params=params or [],
    )


def test_build_query():
    tool = _make_tool(
        params=[
            Param(name="q", query=True),
            Param(name="limit", query=True),
        ]
    )
    result = _build_query(tool, {"q": "test", "limit": 10, "extra": "ignored"})
    assert result == {"q": "test", "limit": 10}


def test_build_query_skips_none():
    tool = _make_tool(
        params=[
            Param(name="q", query=True),
            Param(name="limit", query=True),
        ]
    )
    result = _build_query(tool, {"q": "test", "limit": None})
    assert result == {"q": "test"}


def test_build_query_skips_missing():
    tool = _make_tool(
        params=[
            Param(name="q", query=True),
            Param(name="limit", query=True),
        ]
    )
    result = _build_query(tool, {"q": "test"})
    assert result == {"q": "test"}


# ── Body building ─────────────────────────────────────────────────────────


def test_build_body_excludes_path_and_query():
    tool = _make_tool(
        path="/v1/items/{id}",
        params=[
            Param(name="id"),
            Param(name="q", query=True),
            Param(name="name"),
            Param(name="value"),
        ],
    )
    body = _build_body(tool, {"id": "123", "q": "search", "name": "Test", "value": 42})
    assert body == {"name": "Test", "value": 42}


def test_build_body_returns_none_when_empty():
    tool = _make_tool(path="/v1/items/{id}", params=[Param(name="id")])
    body = _build_body(tool, {"id": "123"})
    assert body is None


def test_build_body_skips_none_values():
    tool = _make_tool(params=[Param(name="name"), Param(name="optional")])
    body = _build_body(tool, {"name": "Test", "optional": None})
    assert body == {"name": "Test"}


# ── params_to_input_schema ────────────────────────────────────────────────


def test_params_to_input_schema_basic():
    params = [
        Param(name="q", description="Search query"),
        Param(name="limit", type="integer", required=True, default=10),
    ]
    schema = params_to_input_schema(params)
    assert schema["type"] == "object"
    assert schema["properties"]["q"] == {"type": "string", "description": "Search query"}
    assert schema["properties"]["limit"]["type"] == "integer"
    assert schema["properties"]["limit"]["default"] == 10
    assert schema["required"] == ["limit"]


def test_params_to_input_schema_with_enum():
    params = [Param(name="status", enum=["active", "inactive"])]
    schema = params_to_input_schema(params)
    assert schema["properties"]["status"]["enum"] == ["active", "inactive"]


def test_params_to_input_schema_with_override():
    override = {"type": "object", "properties": {"dateTime": {"type": "string"}}}
    params = [Param(name="start", required=True, schema_override=override)]
    schema = params_to_input_schema(params)
    assert schema["properties"]["start"] == override
    assert schema["required"] == ["start"]


# ── list_tools / get_tool_def ─────────────────────────────────────────────


def test_list_tools(sample_integration):
    tools = list_tools(sample_integration)
    assert len(tools) == 3
    names = {t["name"] for t in tools}
    assert names == {"list_items", "get_item", "create_item"}
    for t in tools:
        assert "description" in t
        assert "inputSchema" in t


def test_get_tool_def_found(sample_integration):
    tool = get_tool_def(sample_integration, "get_item")
    assert tool is not None
    assert tool.name == "get_item"
    assert isinstance(tool, ApiTool)
    assert tool.path == "/v1/items/{id}"


def test_get_tool_def_not_found(sample_integration):
    assert get_tool_def(sample_integration, "nonexistent") is None


# ── CustomTool dispatch ────────────────────────────────────────────────


def test_list_tools_includes_custom_tool_def():
    async def _run(args: dict, auth_headers: dict) -> dict:
        return {"content": [{"type": "text", "text": "ok"}], "isError": False}

    integration = CustomIntegration(
        id="test",
        name="Test",
        base_url="https://api.example.com",
        auth=[],
        tools=[
            ApiTool(
                name="declarative",
                description="A declarative tool",
                method="GET",
                path="/v1/items",
            ),
            CustomTool(
                name="custom",
                description="A custom tool",
                params=[Param(name="text", required=True)],
                run=_run,
            ),
        ],
    )

    tools = list_tools(integration)
    assert len(tools) == 2
    names = {t["name"] for t in tools}
    assert names == {"declarative", "custom"}


def test_get_tool_def_returns_custom_tool_def():
    async def _run(args: dict, auth_headers: dict) -> dict:
        return {"content": [{"type": "text", "text": "ok"}], "isError": False}

    integration = CustomIntegration(
        id="test",
        name="Test",
        base_url="https://api.example.com",
        auth=[],
        tools=[
            CustomTool(
                name="custom",
                description="Custom",
                params=[],
                run=_run,
            ),
        ],
    )

    tool = get_tool_def(integration, "custom")
    assert tool is not None
    assert isinstance(tool, CustomTool)
    assert tool.name == "custom"
