from agent_port.api_client import params_to_input_schema
from agent_port.integrations import registry
from agent_port.integrations.types import ApiTool, CustomIntegration, RemoteMcpIntegration


def test_list_all_returns_integrations():
    result = registry.list_all()
    assert len(result) >= 1
    ids = {i.id for i in result}
    # Sanity-check known integrations exist rather than enumerating all,
    # so this test doesn't break every time a new integration is added.
    assert "github" in ids
    assert "cloudflare" in ids
    assert "sentry" in ids
    assert "square" in ids
    assert "gmail" in ids
    assert "google_calendar" in ids


def test_get_existing():
    github = registry.get("github")
    assert github is not None
    assert github.id == "github"
    assert github.type == "remote_mcp"


def test_get_custom_integration():
    gmail = registry.get("gmail")
    assert gmail is not None
    assert gmail.id == "gmail"
    assert gmail.type == "custom"
    assert isinstance(gmail, CustomIntegration)
    assert gmail.base_url == "https://gmail.googleapis.com"
    assert len(gmail.tools) > 0


def test_get_nonexistent():
    assert registry.get("nonexistent") is None


def test_all_integrations_valid():
    for integration in registry.list_all():
        assert integration.id
        assert integration.name
        assert len(integration.auth) > 0

        if isinstance(integration, RemoteMcpIntegration):
            assert integration.type == "remote_mcp"
            assert integration.url
        elif isinstance(integration, CustomIntegration):
            assert integration.type == "custom"
            assert integration.base_url
            assert len(integration.tools) > 0
            for tool in integration.tools:
                assert tool.name
                assert tool.description
                assert params_to_input_schema(tool.params)
                # ApiTool tools have method and path; CustomTool have run
                if isinstance(tool, ApiTool):
                    assert tool.method in ("GET", "POST", "PUT", "PATCH", "DELETE")
                    assert tool.path
