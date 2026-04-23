from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, func, select

from agent_port.analytics import posthog_client
from agent_port.config import settings
from agent_port.db import get_session
from agent_port.dependencies import get_current_user, get_impersonator
from agent_port.email import normalize_email, send_verification_email
from agent_port.email.verification import get_email_verification_challenge
from agent_port.models.instance_settings import InstanceSettings
from agent_port.models.org import Org
from agent_port.models.org_membership import OrgMembership
from agent_port.models.user import User
from agent_port.models.waitlist import Waitlist
from agent_port.security import hash_password

router = APIRouter(prefix="/api/users", tags=["users"])


class MeResponse(BaseModel):
    id: str
    email: str
    totp_enabled: bool
    totp_configured: bool
    is_admin: bool
    # When set, the UI should show a persistent "Impersonating as X" banner
    # so the admin always knows they are not acting as themselves.
    impersonator_email: str | None = None


@router.get("/me", response_model=MeResponse)
def get_me(
    current_user: User = Depends(get_current_user),
    impersonator: User | None = Depends(get_impersonator),
) -> MeResponse:
    return MeResponse(
        id=str(current_user.id),
        email=current_user.email,
        totp_enabled=current_user.totp_enabled,
        totp_configured=current_user.totp_confirmed_at is not None,
        is_admin=current_user.is_admin,
        impersonator_email=impersonator.email if impersonator else None,
    )


class RegisterRequest(BaseModel):
    email: str
    password: str
    org_name: str | None = None


class RegisterResponse(BaseModel):
    user_id: str
    org_id: str
    email: str
    email_verification_required: bool = False
    verification_token: str | None = None
    resend_available_at: datetime | None = None


@router.post("/register", status_code=201, response_model=RegisterResponse)
def register(body: RegisterRequest, session: Session = Depends(get_session)) -> RegisterResponse:
    email = normalize_email(body.email)

    instance = session.get(InstanceSettings, 1)
    if instance and instance.waitlist_enabled:
        approved = session.exec(select(Waitlist).where(Waitlist.email == email)).first()
        if not approved:
            raise HTTPException(status_code=403, detail="Email not on waitlist.")

    if settings.block_signups:
        raise HTTPException(status_code=403, detail="Signups are disabled")

    is_first_self_hosted_user = False
    if settings.is_self_hosted:
        org_count = session.exec(select(func.count()).select_from(Org)).one()
        if org_count >= 1:
            raise HTTPException(
                status_code=409,
                detail="Server already has an organization (IS_SELF_HOSTED=true)",
            )
        is_first_self_hosted_user = True

    existing = session.exec(select(User).where(User.email == email)).first()
    if existing:
        raise HTTPException(status_code=409, detail="Email already registered")

    user = User(
        email=email,
        hashed_password=hash_password(body.password),
        email_verified=settings.skip_email_verification,
        is_admin=is_first_self_hosted_user,
    )
    org_name = body.org_name or f"{email}'s organization"
    org = Org(name=org_name)
    session.add(user)
    session.add(org)
    session.flush()  # populate ids before membership insert

    membership = OrgMembership(user_id=user.id, org_id=org.id, role="owner")
    session.add(membership)
    session.commit()

    verification_token: str | None = None
    resend_available_at: datetime | None = None
    if not settings.skip_email_verification:
        send_verification_email(user, session)
        challenge = get_email_verification_challenge(user)
        verification_token = challenge.verification_token
        resend_available_at = challenge.resend_available_at

    posthog_client.capture(
        distinct_id=str(user.id),
        event="user_signed_up",
        properties={"email_verification_required": not settings.skip_email_verification},
    )

    return RegisterResponse(
        user_id=str(user.id),
        org_id=str(org.id),
        email=user.email,
        email_verification_required=not settings.skip_email_verification,
        verification_token=verification_token,
        resend_available_at=resend_available_at,
    )
