from fastapi import APIRouter, Depends, HTTPException

from agent_port.dependencies import AgentAuth, get_agent_auth
from agent_port.integrations import registry

router = APIRouter(prefix="/api/integrations", tags=["integrations"])


def _serialize(integration) -> dict:
    available, reason = integration.is_available()
    return {**integration.model_dump(), "available": available, "available_reason": reason}


@router.get("")
def list_integrations(
    type: str | None = None,
    agent_auth: AgentAuth = Depends(get_agent_auth),
) -> list[dict]:
    integrations = registry.list_all(org_id=agent_auth.org.id)
    if type:
        integrations = [i for i in integrations if i.type == type]
    return [_serialize(i) for i in integrations]


@router.get("/{integration_id}")
def get_integration(
    integration_id: str,
    agent_auth: AgentAuth = Depends(get_agent_auth),
) -> dict:
    integration = registry.get(integration_id, org_id=agent_auth.org.id)
    if not integration:
        raise HTTPException(status_code=404, detail=f"Integration '{integration_id}' not found")
    return _serialize(integration)
