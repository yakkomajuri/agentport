import pytest

from agent_port.models.log import LogEntry


@pytest.mark.anyio
async def test_list_logs_empty(client):
    resp = await client.get("/api/logs")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.anyio
async def test_list_logs(client, session, test_org):
    session.add(
        LogEntry(
            org_id=test_org.id,
            integration_id="posthog",
            tool_name="create_annotation",
            args_json='{"content": "test"}',
            result_json='{"ok": true}',
            duration_ms=42,
        )
    )
    session.commit()

    resp = await client.get("/api/logs")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["tool_name"] == "create_annotation"
    assert data[0]["duration_ms"] == 42


@pytest.mark.anyio
async def test_list_logs_filter_integration(client, session, test_org):
    session.add(LogEntry(org_id=test_org.id, integration_id="posthog", tool_name="tool1"))
    session.add(LogEntry(org_id=test_org.id, integration_id="github", tool_name="tool2"))
    session.commit()

    resp = await client.get("/api/logs?integration=posthog")
    data = resp.json()
    assert len(data) == 1
    assert data[0]["integration_id"] == "posthog"


@pytest.mark.anyio
async def test_list_logs_filter_tool(client, session, test_org):
    session.add(LogEntry(org_id=test_org.id, integration_id="posthog", tool_name="tool1"))
    session.add(LogEntry(org_id=test_org.id, integration_id="posthog", tool_name="tool2"))
    session.commit()

    resp = await client.get("/api/logs?tool=tool1")
    data = resp.json()
    assert len(data) == 1
    assert data[0]["tool_name"] == "tool1"


@pytest.mark.anyio
async def test_list_logs_pagination(client, session, test_org):
    for i in range(10):
        session.add(LogEntry(org_id=test_org.id, integration_id="posthog", tool_name=f"tool_{i}"))
    session.commit()

    resp = await client.get("/api/logs?limit=3&offset=0")
    data = resp.json()
    assert len(data) == 3

    resp = await client.get("/api/logs?limit=3&offset=7")
    data = resp.json()
    assert len(data) == 3
