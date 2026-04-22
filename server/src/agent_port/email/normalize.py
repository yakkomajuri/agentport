"""Email address normalization.

Every place that stores or looks up a ``User.email`` (or a waitlist email)
must funnel through :func:`normalize_email` so that comparisons are
case-insensitive and whitespace-insensitive. The stored form is always
lowercase + stripped, and the DB carries a case-insensitive uniqueness
index so case-variant duplicates are impossible.
"""

from __future__ import annotations


def normalize_email(email: str) -> str:
    """Return the canonical storage/lookup form of ``email``.

    Lowercases and strips surrounding whitespace. We do not touch the local
    part beyond case — provider-specific rules (Gmail dot-ignoring, plus
    tags, etc.) are intentionally not applied here: two visually distinct
    addresses that happen to deliver to the same inbox are still two
    different accounts to us.
    """
    return email.strip().lower()


__all__ = ["normalize_email"]
