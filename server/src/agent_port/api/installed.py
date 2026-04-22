from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from agent_port.analytics import posthog_client
from agent_port.db import get_session
from agent_port.dependencies import AgentAuth, get_agent_auth
from agent_port.integrations import registry
from agent_port.mcp.client import validate_token
from agent_port.mcp.notifications import notify_tools_changed
from agent_port.mcp.refresh import refresh_one
from agent_port.models.integration import InstalledIntegration
from agent_port.models.oauth import OAuthState
from agent_port.secrets.records import delete_secret, upsert_secret

router = APIRouter(prefix="/api/installed", tags=["installed"])


def _serialize_installed(session: Session, installed: InstalledIntegration) -> dict:
    data = installed.model_dump(exclude={"token_secret_id"})
    data["has_token"] = installed.token_secret_id is not None
    return data


class InstallRequest(BaseModel):
    integration_id: str
    auth_method: str  # oauth | token
    token: str | None = None


class UpdateInstallRequest(BaseModel):
    token: str


@router.get("")
def list_installed(
    session: Session = Depends(get_session),
    agent_auth: AgentAuth = Depends(get_agent_auth),
) -> list[dict]:
    installed = session.exec(
        select(InstalledIntegration).where(InstalledIntegration.org_id == agent_auth.org.id)
    ).all()
    return [_serialize_installed(session, i) for i in installed]


@router.post("", status_code=201)
async def install_integration(
    body: InstallRequest,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
    agent_auth: AgentAuth = Depends(get_agent_auth),
) -> dict:
    bundled = registry.get(body.integration_id)
    if not bundled:
        raise HTTPException(
            status_code=404, detail=f"Integration '{body.integration_id}' not found"
        )

    existing = session.exec(
        select(InstalledIntegration)
        .where(InstalledIntegration.org_id == agent_auth.org.id)
        .where(InstalledIntegration.integration_id == body.integration_id)
    ).first()
    if existing:
        if existing.connected:
            raise HTTPException(
                status_code=409,
                detail=f"Integration '{body.integration_id}' already installed",
            )
        # Stale unconnected record (e.g. a previous OAuth attempt failed) — replace it.
        session.delete(existing)
        session.flush()

    if body.auth_method == "token" and not body.token:
        raise HTTPException(status_code=400, detail="Token required for token auth")

    valid_methods = {a.method for a in bundled.auth}
    if body.auth_method not in valid_methods:
        raise HTTPException(
            status_code=400,
            detail=f"Auth method '{body.auth_method}' not supported. Options: {valid_methods}",
        )

    # For remote MCP integrations with token auth, verify the token works before storing.
    if body.auth_method == "token" and body.token and bundled.type == "remote_mcp":
        try:
            await validate_token(bundled.url, body.token)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Token validation failed: {e}")

    # Custom integrations implement their own cheap auth probe.
    if body.auth_method == "token" and body.token and bundled.type == "custom":
        try:
            await bundled.validate_auth(body.token)
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Token validation failed: {e}")

    # Token auth is connected the moment a token is provided (and validated above).
    # OAuth auth is not connected until the OAuth callback succeeds and tokens are persisted.
    # Any other auth method starts as disconnected.
    connected = body.auth_method == "token" and bool(body.token)

    # Determine the connection URL based on integration type.
    if bundled.type == "remote_mcp":
        url = bundled.url
    elif bundled.type == "custom":
        url = bundled.base_url
    else:
        url = ""

    installed = InstalledIntegration(
        org_id=agent_auth.org.id,
        integration_id=body.integration_id,
        type=bundled.type,
        url=url,
        auth_method=body.auth_method,
        connected=connected,
    )
    session.add(installed)
    session.flush()
    if body.token:
        secret = upsert_secret(
            session,
            org_id=agent_auth.org.id,
            kind="integration_token",
            ref=f"integrations/{agent_auth.org.id}/{body.integration_id}/token",
            value=body.token,
            secret_id=installed.token_secret_id,
        )
        installed.token_secret_id = secret.id
        session.add(installed)
    session.commit()
    session.refresh(installed)
    if connected:
        background_tasks.add_task(refresh_one, installed.org_id, installed.integration_id)
    posthog_client.capture(
        distinct_id=str(agent_auth.org.id),
        event="integration_installed",
        properties={
            "integration_id": body.integration_id,
            "integration_type": bundled.type,
            "auth_method": body.auth_method,
            "connected": connected,
        },
    )
    return _serialize_installed(session, installed)


@router.patch("/{integration_id}")
async def update_installed(
    integration_id: str,
    body: UpdateInstallRequest,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
    agent_auth: AgentAuth = Depends(get_agent_auth),
) -> dict:
    installed = session.exec(
        select(InstalledIntegration)
        .where(InstalledIntegration.org_id == agent_auth.org.id)
        .where(InstalledIntegration.integration_id == integration_id)
    ).first()
    if not installed:
        raise HTTPException(
            status_code=404,
            detail=f"Installed integration '{integration_id}' not found",
        )
    if installed.auth_method != "token":
        raise HTTPException(
            status_code=400,
            detail="Token updates are only supported for token-auth integrations",
        )
    if not body.token:
        raise HTTPException(status_code=400, detail="Token must not be empty")
    if installed.type == "remote_mcp":
        try:
            await validate_token(installed.url, body.token)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Token validation failed: {e}")
    secret = upsert_secret(
        session,
        org_id=installed.org_id,
        kind="integration_token",
        ref=f"integrations/{installed.org_id}/{installed.integration_id}/token",
        value=body.token,
        secret_id=installed.token_secret_id,
    )
    installed.token_secret_id = secret.id
    installed.connected = True
    session.add(installed)
    session.commit()
    session.refresh(installed)
    background_tasks.add_task(refresh_one, installed.org_id, installed.integration_id)
    return _serialize_installed(session, installed)


@router.delete("/{integration_id}", status_code=204)
def remove_installed(
    integration_id: str,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
    agent_auth: AgentAuth = Depends(get_agent_auth),
) -> None:
    installed = session.exec(
        select(InstalledIntegration)
        .where(InstalledIntegration.org_id == agent_auth.org.id)
        .where(InstalledIntegration.integration_id == integration_id)
    ).first()
    if not installed:
        raise HTTPException(
            status_code=404,
            detail=f"Installed integration '{integration_id}' not found",
        )
    integration_type = installed.type

    # Collect secret IDs we need to delete, then delete the rows that reference
    # them before deleting the secrets themselves. Parent-before-child ordering
    # is required so PostgreSQL's FK checks don't reject the Secret DELETE.
    secret_ids: list = []
    if installed.auth_method == "token":
        secret_ids.append(installed.token_secret_id)

    oauth_state = session.exec(
        select(OAuthState)
        .where(OAuthState.org_id == agent_auth.org.id)
        .where(OAuthState.integration_id == integration_id)
    ).first()
    if oauth_state:
        secret_ids.extend(
            [
                oauth_state.client_secret_secret_id,
                oauth_state.access_token_secret_id,
                oauth_state.refresh_token_secret_id,
            ]
        )
        session.delete(oauth_state)

    session.delete(installed)
    session.flush()

    for sid in secret_ids:
        delete_secret(session, sid)
    session.commit()
    posthog_client.capture(
        distinct_id=str(agent_auth.org.id),
        event="integration_removed",
        properties={"integration_id": integration_id, "integration_type": integration_type},
    )
    background_tasks.add_task(notify_tools_changed, agent_auth.org.id)
