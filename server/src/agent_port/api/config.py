"""Public runtime config surface for the UI.

Exposes just the flags the UI needs to decide what to render (e.g. hide the
billing page on self-hosted installs). No auth — values are non-sensitive
deployment toggles.
"""

from fastapi import APIRouter
from pydantic import BaseModel

from agent_port.config import settings

router = APIRouter(prefix="/api/config", tags=["config"])


class PublicConfigResponse(BaseModel):
    is_self_hosted: bool
    billing_enabled: bool


@router.get("")
def get_public_config() -> PublicConfigResponse:
    return PublicConfigResponse(
        is_self_hosted=settings.is_self_hosted,
        billing_enabled=settings.billing_enabled(),
    )
