"""CRUD for user-defined remote MCP integrations.

Users paste an MCP server URL; we materialise a per-org row that the registry
surfaces alongside bundled integrations. Install/uninstall continues to go through
the existing /api/installed endpoints.
"""

import re
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, HttpUrl
from sqlmodel import Session, select

from agent_port.db import get_session
from agent_port.dependencies import AgentAuth, get_agent_auth
from agent_port.integrations.registry import CUSTOM_PREFIX
from agent_port.models.custom_mcp_integration import CustomMcpIntegration
from agent_port.models.integration import InstalledIntegration

router = APIRouter(prefix="/api/integrations/custom", tags=["custom-integrations"])

_SLUG_RE = re.compile(r"[^a-z0-9]+")
_SLUG_MAX = 40


def _slugify(name: str) -> str:
    base = _SLUG_RE.sub("_", name.lower()).strip("_")
    if not base:
        base = "mcp"
    return base[:_SLUG_MAX]


def _allocate_integration_id(session: Session, org_id, name: str) -> str:
    """Pick a unique integration_id of the form custom_<slug>[_<n>] for this org."""
    slug = _slugify(name)
    candidate = f"{CUSTOM_PREFIX}{slug}"
    suffix = 2
    while True:
        existing = session.exec(
            select(CustomMcpIntegration)
            .where(CustomMcpIntegration.org_id == org_id)
            .where(CustomMcpIntegration.integration_id == candidate)
        ).first()
        if not existing:
            return candidate
        candidate = f"{CUSTOM_PREFIX}{slug}_{suffix}"
        suffix += 1


class CreateCustomMcpRequest(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    url: HttpUrl
    description: str | None = Field(default=None, max_length=500)
    auth_method: str  # "none" | "token"
    token_header: str = "Authorization"
    token_format: str = "Bearer {token}"


class UpdateCustomMcpRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    url: HttpUrl | None = None
    description: str | None = Field(default=None, max_length=500)
    token_header: str | None = None
    token_format: str | None = None


def _serialize(row: CustomMcpIntegration) -> dict:
    return {
        "id": str(row.id),
        "integration_id": row.integration_id,
        "name": row.name,
        "url": row.url,
        "description": row.description,
        "auth_method": row.auth_method,
        "token_header": row.token_header,
        "token_format": row.token_format,
        "created_at": row.created_at.isoformat(),
    }


@router.get("")
def list_custom(
    session: Session = Depends(get_session),
    agent_auth: AgentAuth = Depends(get_agent_auth),
) -> list[dict]:
    rows = session.exec(
        select(CustomMcpIntegration).where(CustomMcpIntegration.org_id == agent_auth.org.id)
    ).all()
    return [_serialize(r) for r in rows]


@router.post("", status_code=201)
def create_custom(
    body: CreateCustomMcpRequest,
    session: Session = Depends(get_session),
    agent_auth: AgentAuth = Depends(get_agent_auth),
) -> dict:
    if body.auth_method not in {"none", "token", "oauth"}:
        raise HTTPException(
            status_code=400,
            detail="auth_method must be 'none', 'token', or 'oauth'",
        )
    if body.auth_method == "token" and "{token}" not in body.token_format:
        raise HTTPException(
            status_code=400,
            detail="token_format must contain the literal substring '{token}'",
        )

    integration_id = _allocate_integration_id(session, agent_auth.org.id, body.name)
    row = CustomMcpIntegration(
        org_id=agent_auth.org.id,
        integration_id=integration_id,
        name=body.name,
        url=str(body.url),
        description=body.description,
        auth_method=body.auth_method,
        token_header=body.token_header,
        token_format=body.token_format,
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return _serialize(row)


@router.patch("/{custom_id}")
def update_custom(
    custom_id: uuid.UUID,
    body: UpdateCustomMcpRequest,
    session: Session = Depends(get_session),
    agent_auth: AgentAuth = Depends(get_agent_auth),
) -> dict:
    row = session.exec(
        select(CustomMcpIntegration)
        .where(CustomMcpIntegration.id == custom_id)
        .where(CustomMcpIntegration.org_id == agent_auth.org.id)
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail="Custom integration not found")

    if body.name is not None:
        row.name = body.name
    if body.url is not None:
        row.url = str(body.url)
    if body.description is not None:
        row.description = body.description
    if body.token_header is not None:
        row.token_header = body.token_header
    if body.token_format is not None:
        if "{token}" not in body.token_format:
            raise HTTPException(
                status_code=400,
                detail="token_format must contain the literal substring '{token}'",
            )
        row.token_format = body.token_format

    session.add(row)
    session.commit()
    session.refresh(row)
    return _serialize(row)


@router.delete("/{custom_id}", status_code=204)
def delete_custom(
    custom_id: uuid.UUID,
    session: Session = Depends(get_session),
    agent_auth: AgentAuth = Depends(get_agent_auth),
) -> None:
    row = session.exec(
        select(CustomMcpIntegration)
        .where(CustomMcpIntegration.id == custom_id)
        .where(CustomMcpIntegration.org_id == agent_auth.org.id)
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail="Custom integration not found")

    # Require uninstall first so the existing /api/installed delete path owns
    # secret + OAuth-state cleanup.
    installed = session.exec(
        select(InstalledIntegration)
        .where(InstalledIntegration.org_id == agent_auth.org.id)
        .where(InstalledIntegration.integration_id == row.integration_id)
    ).first()
    if installed:
        raise HTTPException(
            status_code=409,
            detail="Uninstall this integration before deleting its definition",
        )

    session.delete(row)
    session.commit()
