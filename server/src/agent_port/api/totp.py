"""TOTP second-factor endpoints.

State machine on the User row:
  unset (no secret, not enabled)
    → setup (secret + recovery codes written; not confirmed)
    → enabled (confirmed_at set, totp_enabled=true)
    ↔ disabled (totp_enabled=false, secret retained)
Re-enabling a previously confirmed account skips the setup flow entirely.
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session

from agent_port.analytics import posthog_client
from agent_port.api.schemas import MessageResponse
from agent_port.db import get_session
from agent_port.dependencies import get_current_user, get_impersonator
from agent_port.models.user import User
from agent_port.totp import (
    generate_recovery_codes,
    generate_secret,
    hash_recovery_codes,
    otpauth_uri,
    qr_data_url,
    verify_second_factor,
    verify_totp_code,
)

router = APIRouter(prefix="/api/users/me/totp", tags=["totp"])


class TotpStatusResponse(BaseModel):
    enabled: bool
    configured: bool


class TotpSetupResponse(BaseModel):
    secret: str
    otpauth_uri: str
    qr_data_url: str
    recovery_codes: list[str]


class TotpEnableRequest(BaseModel):
    code: str


class TotpCodeRequest(BaseModel):
    code: str


def _require_existing_second_factor(user: User, code: str | None) -> None:
    """Require a valid authenticator or recovery code for sensitive changes."""
    if not code:
        raise HTTPException(
            status_code=403,
            detail={
                "error": "totp_required",
                "message": "A one-time code is required to confirm this action.",
            },
        )
    if not verify_second_factor(user, code):
        raise HTTPException(
            status_code=403,
            detail={
                "error": "totp_invalid",
                "message": "That code didn't match — try again with a fresh one.",
            },
        )


def _reject_if_impersonating(impersonator: User | None) -> None:
    """Block TOTP mutations when the caller is an admin acting as someone else.

    Without this gate an impersonator could call /totp/setup followed by
    /totp/enable to permanently hijack a target's 2FA with an admin-held
    secret — see finding 6e. Impersonation is intended for read-mostly
    support, not account takeover."""
    if impersonator is not None:
        raise HTTPException(
            status_code=403,
            detail={
                "error": "impersonation_not_allowed",
                "message": (
                    "Two-factor settings cannot be changed while impersonating. "
                    "Stop impersonating and have the user perform this action themselves."
                ),
            },
        )


@router.get("/status", response_model=TotpStatusResponse)
def get_status(current_user: User = Depends(get_current_user)) -> TotpStatusResponse:
    return TotpStatusResponse(
        enabled=current_user.totp_enabled,
        configured=current_user.totp_confirmed_at is not None,
    )


@router.post("/setup", response_model=TotpSetupResponse)
def setup(
    current_user: User = Depends(get_current_user),
    impersonator: User | None = Depends(get_impersonator),
    session: Session = Depends(get_session),
) -> TotpSetupResponse:
    """Generate a fresh secret + recovery codes for a first-time setup.

    Rejected if TOTP is already confirmed — callers should use /re-enable in
    that case, or /reset after verifying the existing code (future scope)."""
    _reject_if_impersonating(impersonator)
    if current_user.totp_confirmed_at is not None:
        raise HTTPException(
            status_code=409,
            detail="Two-factor authentication is already set up on this account",
        )

    secret = generate_secret()
    recovery_codes = generate_recovery_codes()
    current_user.totp_secret = secret
    current_user.totp_recovery_codes_hash_json = hash_recovery_codes(recovery_codes)
    current_user.totp_enabled = False
    current_user.totp_confirmed_at = None
    session.add(current_user)
    session.commit()

    uri = otpauth_uri(secret, current_user.email)
    return TotpSetupResponse(
        secret=secret,
        otpauth_uri=uri,
        qr_data_url=qr_data_url(uri),
        recovery_codes=recovery_codes,
    )


@router.post("/enable", response_model=TotpStatusResponse)
def enable(
    body: TotpEnableRequest,
    current_user: User = Depends(get_current_user),
    impersonator: User | None = Depends(get_impersonator),
    session: Session = Depends(get_session),
) -> TotpStatusResponse:
    """Confirm the setup by verifying a first code from the authenticator."""
    _reject_if_impersonating(impersonator)
    if not current_user.totp_secret:
        raise HTTPException(status_code=400, detail="No pending TOTP setup — call /setup first")

    if not verify_totp_code(current_user.totp_secret, body.code):
        raise HTTPException(status_code=400, detail="Invalid code — try again")

    is_first_confirmation = current_user.totp_confirmed_at is None
    current_user.totp_enabled = True
    if is_first_confirmation:
        current_user.totp_confirmed_at = datetime.now(timezone.utc).replace(tzinfo=None)
    session.add(current_user)
    session.commit()

    posthog_client.capture(
        distinct_id=str(current_user.id),
        event="totp_enabled",
        properties={"first_time": is_first_confirmation},
    )
    return TotpStatusResponse(enabled=True, configured=True)


@router.post("/re-enable", response_model=TotpStatusResponse)
def re_enable(
    body: TotpCodeRequest,
    current_user: User = Depends(get_current_user),
    impersonator: User | None = Depends(get_impersonator),
    session: Session = Depends(get_session),
) -> TotpStatusResponse:
    """Turn TOTP back on after a previous disable.

    Re-enabling still requires proof of possession of the current authenticator
    or an unused recovery code."""
    _reject_if_impersonating(impersonator)
    if current_user.totp_confirmed_at is None or not current_user.totp_secret:
        raise HTTPException(
            status_code=409,
            detail="No previously configured authenticator — call /setup instead",
        )

    _require_existing_second_factor(current_user, body.code)
    current_user.totp_enabled = True
    session.add(current_user)
    session.commit()
    posthog_client.capture(
        distinct_id=str(current_user.id),
        event="totp_enabled",
        properties={"first_time": False},
    )
    return TotpStatusResponse(enabled=True, configured=True)


@router.post("/disable", response_model=MessageResponse)
def disable(
    body: TotpCodeRequest,
    current_user: User = Depends(get_current_user),
    impersonator: User | None = Depends(get_impersonator),
    session: Session = Depends(get_session),
) -> MessageResponse:
    """Stop asking for codes on approvals.

    Keeps the secret so re-enabling does not require rescanning the QR code."""
    _reject_if_impersonating(impersonator)
    if not current_user.totp_enabled:
        return MessageResponse(message="Two-factor authentication is already disabled")
    _require_existing_second_factor(current_user, body.code)
    current_user.totp_enabled = False
    session.add(current_user)
    session.commit()
    posthog_client.capture(
        distinct_id=str(current_user.id),
        event="totp_disabled",
    )
    return MessageResponse(message="Two-factor authentication disabled")
