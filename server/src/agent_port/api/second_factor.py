"""Shared TOTP gate for sensitive mutations.

Several endpoints (approval decisions, tool-setting escalations) treat the
same "user with TOTP enabled must present a fresh code" check as a hard
requirement. Keeping the helper here avoids cross-importing private
functions between API modules.

Recovery-code verification burns the code onto the user row, so callers
must ``session.add(user)`` and commit after a successful check.
"""

from fastapi import HTTPException

from agent_port.models.user import User
from agent_port.totp import verify_second_factor


def require_second_factor(user: User, code: str | None) -> None:
    if not user.totp_enabled:
        return
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
