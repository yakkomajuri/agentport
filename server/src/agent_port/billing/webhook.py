import logging
import uuid
from datetime import datetime, timezone

import stripe
from sqlmodel import Session, select

from agent_port.models.subscription import Subscription

ACTIVE_STATUSES = {"active", "trialing", "past_due", "incomplete"}

logger = logging.getLogger(__name__)


def _safe_get(obj, key, default=None):
    """Access a field on a dict, stripe.StripeObject, or SimpleNamespace uniformly.

    Why: stripe.Webhook.construct_event returns StripeObjects whose .get() is
    not reliably present across SDK versions; use [] with membership check, and
    fall back to attribute access for non-dict-like objects.
    """
    if obj is None:
        return default
    try:
        if key in obj:
            return obj[key]
    except TypeError:
        pass
    return getattr(obj, key, default)


def _upsert(session: Session, org_id: uuid.UUID, **fields) -> Subscription:
    sub = session.get(Subscription, org_id)
    if sub is None:
        sub = Subscription(org_id=org_id, **fields)
    else:
        for key, value in fields.items():
            setattr(sub, key, value)
    sub.updated_at = datetime.utcnow()
    session.add(sub)
    return sub


def _period_end(sub) -> datetime | None:
    """Resolve the subscription's effective end timestamp.

    Why: Stripe's newer API no longer exposes current_period_end on the
    subscription root — it lives on subscription items. And when a cancel is
    scheduled via the Customer Portal, cancel_at is set (not cancel_at_period_end).
    Prefer cancel_at when present because it's the actual termination time.
    """
    cancel_at = _safe_get(sub, "cancel_at")
    if cancel_at:
        return datetime.fromtimestamp(cancel_at, tz=timezone.utc).replace(tzinfo=None)

    ts = _safe_get(sub, "current_period_end")
    if ts:
        return datetime.fromtimestamp(ts, tz=timezone.utc).replace(tzinfo=None)

    items = _safe_get(sub, "items")
    items_data = _safe_get(items, "data") if items else None
    if items_data:
        try:
            item_ts = _safe_get(items_data[0], "current_period_end")
        except (IndexError, TypeError):
            item_ts = None
        if item_ts:
            return datetime.fromtimestamp(item_ts, tz=timezone.utc).replace(tzinfo=None)
    return None


def _is_cancel_scheduled(sub) -> bool:
    """True if the sub is set to terminate at period end (legacy flag or newer cancel_at)."""
    return bool(_safe_get(sub, "cancel_at_period_end")) or bool(_safe_get(sub, "cancel_at"))


def _org_id_from_metadata(metadata) -> uuid.UUID | None:
    if not metadata:
        return None
    raw = _safe_get(metadata, "org_id")
    if not raw:
        return None
    try:
        return uuid.UUID(str(raw))
    except ValueError:
        return None


def _resolve_org_id(obj, session: Session) -> uuid.UUID | None:
    """Find the org a Stripe event belongs to.

    Why: Stripe Portal-initiated events (cancel, update payment) carry the
    subscription metadata we set at checkout — but fall back to a DB lookup
    by stripe_subscription_id in case metadata was stripped or never set.
    """
    org_id = _org_id_from_metadata(_safe_get(obj, "metadata"))
    if org_id is not None:
        return org_id
    stripe_sub_id = _safe_get(obj, "id")
    if not stripe_sub_id:
        return None
    existing = session.exec(
        select(Subscription).where(Subscription.stripe_subscription_id == stripe_sub_id)
    ).first()
    return existing.org_id if existing else None


def handle_event(event, session: Session) -> None:
    """Dispatch a verified Stripe event. Idempotent: each handler upserts by org_id."""
    event_type = event["type"]
    obj = event["data"]["object"]

    if event_type == "checkout.session.completed":
        _handle_checkout_completed(obj, session)
    elif event_type in ("customer.subscription.created", "customer.subscription.updated"):
        _handle_subscription_changed(obj, session)
    elif event_type == "customer.subscription.deleted":
        _handle_subscription_deleted(obj, session)
    elif event_type == "invoice.payment_failed":
        _handle_payment_failed(obj, session)
    elif event_type == "invoice.paid":
        pass  # no-op for V1
    else:
        logger.debug("Ignoring unhandled Stripe event: %s", event_type)
        return

    session.commit()


def _handle_checkout_completed(obj, session: Session) -> None:
    raw_org_id = _safe_get(obj, "client_reference_id")
    stripe_sub_id = _safe_get(obj, "subscription")
    customer_id = _safe_get(obj, "customer")
    if not raw_org_id or not stripe_sub_id:
        logger.warning("checkout.session.completed missing org or subscription id")
        return
    try:
        org_id = uuid.UUID(raw_org_id)
    except ValueError:
        logger.warning("checkout.session.completed has malformed client_reference_id")
        return

    stripe_sub = stripe.Subscription.retrieve(stripe_sub_id)
    _upsert(
        session,
        org_id,
        stripe_customer_id=customer_id,
        stripe_subscription_id=stripe_sub_id,
        tier="plus",
        status=_safe_get(stripe_sub, "status"),
        current_period_end=_period_end(stripe_sub),
        cancel_at_period_end=_is_cancel_scheduled(stripe_sub),
    )


def _handle_subscription_changed(obj, session: Session) -> None:
    org_id = _resolve_org_id(obj, session)
    if org_id is None:
        return
    status = _safe_get(obj, "status")
    tier = "plus" if status in ACTIVE_STATUSES else "free"
    _upsert(
        session,
        org_id,
        stripe_customer_id=_safe_get(obj, "customer"),
        stripe_subscription_id=_safe_get(obj, "id"),
        tier=tier,
        status=status,
        current_period_end=_period_end(obj),
        cancel_at_period_end=_is_cancel_scheduled(obj),
    )


def _handle_subscription_deleted(obj, session: Session) -> None:
    org_id = _resolve_org_id(obj, session)
    if org_id is None:
        return
    sub = session.get(Subscription, org_id)
    if sub is None:
        return
    sub.tier = "free"
    sub.status = "canceled"
    sub.stripe_subscription_id = None
    sub.cancel_at_period_end = False
    sub.updated_at = datetime.utcnow()
    session.add(sub)


def _handle_payment_failed(obj, session: Session) -> None:
    stripe_sub_id = _safe_get(obj, "subscription")
    if not stripe_sub_id:
        return
    stripe_sub = stripe.Subscription.retrieve(stripe_sub_id)
    org_id = _resolve_org_id(stripe_sub, session)
    if org_id is None:
        return
    sub = session.get(Subscription, org_id)
    if sub is None:
        return
    sub.status = "past_due"
    sub.updated_at = datetime.utcnow()
    session.add(sub)
