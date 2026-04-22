import hashlib
import time

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlmodel import Session, select

from agent_port.analytics import posthog_client
from agent_port.db import get_session
from agent_port.dependencies import get_current_user
from agent_port.mcp.oauth_provider import oauth_provider
from agent_port.models.oauth_auth_request import OAuthAuthRequest
from agent_port.models.oauth_client import OAuthClient
from agent_port.models.user import User

router = APIRouter(prefix="/api/oauth/authorize", tags=["oauth-server"])


class SessionInfoResponse(BaseModel):
    client_id: str
    client_name: str | None
    redirect_uri: str
    scope: str | None
    resource: str | None
    expires_at: int


class AuthDecisionRequest(BaseModel):
    session_token: str


class RedirectResponse(BaseModel):
    redirect_url: str


@router.get("/session", response_model=SessionInfoResponse)
def get_session_info(
    session: str = Query(..., alias="session"),
    db: Session = Depends(get_session),
) -> SessionInfoResponse:
    session_hash = hashlib.sha256(session.encode()).hexdigest()
    req = db.get(OAuthAuthRequest, session_hash)
    if not req:
        raise HTTPException(status_code=404, detail="Authorization session not found")
    if req.expires_at < int(time.time()):
        raise HTTPException(status_code=410, detail="Authorization session expired")

    # Look up client name
    client_name: str | None = None
    client_row = db.exec(select(OAuthClient).where(OAuthClient.client_id == req.client_id)).first()
    if client_row:
        client_name = client_row.client_name

    return SessionInfoResponse(
        client_id=req.client_id,
        client_name=client_name,
        redirect_uri=req.redirect_uri,
        scope=req.scope,
        resource=req.resource,
        expires_at=req.expires_at,
    )


@router.post("/approve", response_model=RedirectResponse)
async def approve(
    body: AuthDecisionRequest,
    user: User = Depends(get_current_user),
) -> RedirectResponse:
    redirect_url = await oauth_provider.complete_authorization(body.session_token, user.id)
    posthog_client.capture(distinct_id=str(user.id), event="oauth_client_authorized")
    return RedirectResponse(redirect_url=redirect_url)


@router.post("/deny", response_model=RedirectResponse)
async def deny(
    body: AuthDecisionRequest,
    user: User = Depends(get_current_user),
) -> RedirectResponse:
    redirect_url = await oauth_provider.deny_authorization(body.session_token)
    return RedirectResponse(redirect_url=redirect_url)
