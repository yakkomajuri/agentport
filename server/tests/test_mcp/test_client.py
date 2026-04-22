import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent_port.mcp.client import _auth_headers, call_tool, list_tools
from agent_port.models.integration import InstalledIntegration
from agent_port.models.oauth import OAuthState


def _make_installed(auth_method="token", token_secret_id=None):
    return InstalledIntegration(
        org_id=uuid.uuid4(),
        integration_id="posthog",
        type="remote_mcp",
        url="https://mcp.posthog.com/mcp",
        auth_method=auth_method,
        token_secret_id=token_secret_id,
    )


def test_auth_headers_token():
    secret_id = uuid.uuid4()
    installed = _make_installed(auth_method="token", token_secret_id=secret_id)
    with patch("agent_port.mcp.client.get_secret_value", return_value="my_token"):
        headers = _auth_headers(installed)
    assert headers == {"Authorization": "Bearer my_token"}


def test_auth_headers_oauth():
    secret_id = uuid.uuid4()
    installed = _make_installed(auth_method="oauth")
    oauth_state = OAuthState(
        org_id=uuid.uuid4(),
        integration_id="test",
        access_token_secret_id=secret_id,
    )
    with patch("agent_port.mcp.client.get_secret_value", return_value="oauth_token"):
        headers = _auth_headers(installed, oauth_state)
    assert headers == {"Authorization": "Bearer oauth_token"}


def test_auth_headers_no_credentials():
    installed = _make_installed(auth_method="oauth")
    headers = _auth_headers(installed)
    assert headers == {}


@pytest.mark.anyio
async def test_list_tools_calls_mcp():
    installed = _make_installed()

    mock_tool = MagicMock()
    mock_tool.model_dump.return_value = {"name": "test_tool", "description": "A tool"}

    mock_result = MagicMock()
    mock_result.tools = [mock_tool]

    mock_session = AsyncMock()
    mock_session.initialize = AsyncMock()
    mock_session.list_tools = AsyncMock(return_value=mock_result)

    with (
        patch("agent_port.mcp.client.streamablehttp_client") as mock_client,
        patch("agent_port.mcp.client.ClientSession") as mock_session_cls,
        patch("agent_port.mcp.client.get_secret_value", return_value="tok"),
    ):
        mock_client.return_value.__aenter__ = AsyncMock(
            return_value=(MagicMock(), MagicMock(), MagicMock())
        )
        mock_client.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_session_cls.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        result = await list_tools(installed)

    assert len(result) == 1
    assert result[0]["name"] == "test_tool"


@pytest.mark.anyio
async def test_call_tool_calls_mcp():
    installed = _make_installed()

    mock_content = MagicMock()
    mock_content.model_dump.return_value = {"type": "text", "text": "result"}

    mock_result = MagicMock()
    mock_result.content = [mock_content]
    mock_result.isError = False

    mock_session = AsyncMock()
    mock_session.initialize = AsyncMock()
    mock_session.call_tool = AsyncMock(return_value=mock_result)

    with (
        patch("agent_port.mcp.client.streamablehttp_client") as mock_client,
        patch("agent_port.mcp.client.ClientSession") as mock_session_cls,
        patch("agent_port.mcp.client.get_secret_value", return_value="tok"),
    ):
        mock_client.return_value.__aenter__ = AsyncMock(
            return_value=(MagicMock(), MagicMock(), MagicMock())
        )
        mock_client.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_session_cls.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        result = await call_tool(installed, "test_tool", {"arg": "value"})

    assert result["isError"] is False
    assert result["content"][0]["text"] == "result"
