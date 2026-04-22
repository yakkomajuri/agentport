"""Tests for POST /api/billing/webhook."""

import json
import uuid
from types import SimpleNamespace

import pytest
from httpx import ASGITransport, AsyncClient

from agent_port.config import settings
from agent_port.main import app
from agent_port.models.subscription import Subscription


@pytest.fixture
def billing_on(monkeypatch):
    monkeypatch.setattr(settings, "is_cloud", True)
    monkeypatch.setattr(settings, "stripe_api_key", "sk_test_dummy")
    monkeypatch.setattr(settings, "stripe_price_plus", "price_plus_123")
    monkeypatch.setattr(settings, "stripe_webhook_secret", "whsec_test")


@pytest.fixture
def anon_client(session, billing_on):
    """Webhook endpoint has no auth overrides."""
    from agent_port.db import get_session

    def override_session():
        yield session

    app.dependency_overrides[get_session] = override_session
    transport = ASGITransport(app=app)

    async def _factory():
        return AsyncClient(transport=transport, base_url="http://test")

    yield _factory
    app.dependency_overrides.clear()


def _stub_construct_event(monkeypatch, event_payload):
    """Make stripe.Webhook.construct_event return our payload unchanged."""
    monkeypatch.setattr(
        "agent_port.api.billing.stripe.Webhook.construct_event",
        lambda payload, sig_header, secret: event_payload,
    )


class _StripeLike(dict):
    """Mimics stripe.StripeObject: dict-indexable + attribute access, but .get raises.

    Why: real StripeObject instances returned by the SDK don't expose a working
    .get() in all code paths — earlier versions of the webhook handlers called
    .get() and crashed in production. This fixture guards against regression.
    """

    def __getattr__(self, key):
        if key in self:
            return self[key]
        raise AttributeError(key)

    def get(self, *args, **kwargs):
        raise AttributeError("get")


@pytest.mark.asyncio
async def test_webhook_rejects_invalid_signature(anon_client, monkeypatch):
    import stripe as stripe_mod

    def _raise(payload, sig_header, secret):
        raise stripe_mod.SignatureVerificationError("bad sig", sig_header)

    monkeypatch.setattr("agent_port.api.billing.stripe.Webhook.construct_event", _raise)

    client = await anon_client()
    async with client:
        resp = await client.post(
            "/api/billing/webhook",
            content=b"{}",
            headers={"stripe-signature": "bad"},
        )
    assert resp.status_code == 400
    assert resp.json()["detail"] == "invalid_signature"


@pytest.mark.asyncio
async def test_webhook_checkout_completed_upserts_plus(anon_client, session, test_org, monkeypatch):
    stripe_sub_obj = SimpleNamespace(
        status="active",
        current_period_end=1800000000,
        cancel_at_period_end=False,
    )
    monkeypatch.setattr(
        "agent_port.billing.webhook.stripe.Subscription.retrieve",
        lambda sub_id: stripe_sub_obj,
    )

    event = {
        "id": "evt_1",
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "client_reference_id": str(test_org.id),
                "subscription": "sub_123",
                "customer": "cus_abc",
            }
        },
    }
    _stub_construct_event(monkeypatch, event)

    client = await anon_client()
    async with client:
        resp = await client.post(
            "/api/billing/webhook",
            content=json.dumps(event).encode(),
            headers={"stripe-signature": "ok"},
        )
    assert resp.status_code == 200

    row = session.get(Subscription, test_org.id)
    assert row is not None
    assert row.tier == "plus"
    assert row.status == "active"
    assert row.stripe_subscription_id == "sub_123"
    assert row.stripe_customer_id == "cus_abc"


@pytest.mark.asyncio
async def test_webhook_subscription_updated_flips_cancel_flag(
    anon_client, session, test_org, monkeypatch
):
    session.add(
        Subscription(
            org_id=test_org.id,
            stripe_customer_id="cus_abc",
            stripe_subscription_id="sub_123",
            tier="plus",
            status="active",
            cancel_at_period_end=False,
        )
    )
    session.commit()

    event = {
        "id": "evt_2",
        "type": "customer.subscription.updated",
        "data": {
            "object": {
                "id": "sub_123",
                "customer": "cus_abc",
                "status": "active",
                "current_period_end": 1800000000,
                "cancel_at_period_end": True,
                "metadata": {"org_id": str(test_org.id)},
            }
        },
    }
    _stub_construct_event(monkeypatch, event)

    client = await anon_client()
    async with client:
        resp = await client.post(
            "/api/billing/webhook",
            content=json.dumps(event).encode(),
            headers={"stripe-signature": "ok"},
        )
    assert resp.status_code == 200

    session.expire_all()
    row = session.get(Subscription, test_org.id)
    assert row is not None
    assert row.cancel_at_period_end is True


@pytest.mark.asyncio
async def test_webhook_subscription_deleted_downgrades(anon_client, session, test_org, monkeypatch):
    session.add(
        Subscription(
            org_id=test_org.id,
            stripe_customer_id="cus_abc",
            stripe_subscription_id="sub_123",
            tier="plus",
            status="active",
        )
    )
    session.commit()

    event = {
        "id": "evt_3",
        "type": "customer.subscription.deleted",
        "data": {
            "object": {
                "id": "sub_123",
                "customer": "cus_abc",
                "metadata": {"org_id": str(test_org.id)},
            }
        },
    }
    _stub_construct_event(monkeypatch, event)

    client = await anon_client()
    async with client:
        resp = await client.post(
            "/api/billing/webhook",
            content=json.dumps(event).encode(),
            headers={"stripe-signature": "ok"},
        )
    assert resp.status_code == 200

    session.expire_all()
    row = session.get(Subscription, test_org.id)
    assert row is not None
    assert row.tier == "free"
    assert row.status == "canceled"
    assert row.stripe_subscription_id is None


@pytest.mark.asyncio
async def test_webhook_deleted_without_metadata_falls_back_to_sub_id(
    anon_client, session, test_org, monkeypatch
):
    """Portal-initiated deletions may omit metadata — DB lookup by sub id still works."""
    session.add(
        Subscription(
            org_id=test_org.id,
            stripe_customer_id="cus_abc",
            stripe_subscription_id="sub_lookup",
            tier="plus",
            status="active",
        )
    )
    session.commit()

    event = {
        "id": "evt_del_nometa",
        "type": "customer.subscription.deleted",
        "data": {
            "object": {
                "id": "sub_lookup",
                "customer": "cus_abc",
                "metadata": {},
            }
        },
    }
    _stub_construct_event(monkeypatch, event)

    client = await anon_client()
    async with client:
        resp = await client.post(
            "/api/billing/webhook",
            content=json.dumps(event).encode(),
            headers={"stripe-signature": "ok"},
        )
    assert resp.status_code == 200

    session.expire_all()
    row = session.get(Subscription, test_org.id)
    assert row is not None
    assert row.tier == "free"
    assert row.status == "canceled"


@pytest.mark.asyncio
async def test_webhook_cancel_at_is_treated_as_cancel_at_period_end(
    anon_client, session, test_org, monkeypatch
):
    """Portal cancellations in Stripe's newer API set cancel_at (not cancel_at_period_end).

    The subscription stays active until the timestamp. current_period_end moved to
    subscription items — pull it from items.data[0] when the top-level field is absent.
    """
    session.add(
        Subscription(
            org_id=test_org.id,
            stripe_customer_id="cus_abc",
            stripe_subscription_id="sub_cxlat",
            tier="plus",
            status="active",
        )
    )
    session.commit()

    event = {
        "id": "evt_cxlat",
        "type": "customer.subscription.updated",
        "data": {
            "object": {
                "id": "sub_cxlat",
                "customer": "cus_abc",
                "status": "active",
                "cancel_at_period_end": False,
                "cancel_at": 1779393820,  # May 21, 2026
                "items": {
                    "data": [{"current_period_end": 1779393820}],
                },
                "metadata": {"org_id": str(test_org.id)},
            }
        },
    }
    _stub_construct_event(monkeypatch, event)

    client = await anon_client()
    async with client:
        resp = await client.post(
            "/api/billing/webhook",
            content=json.dumps(event).encode(),
            headers={"stripe-signature": "ok"},
        )
    assert resp.status_code == 200

    session.expire_all()
    row = session.get(Subscription, test_org.id)
    assert row is not None
    assert row.tier == "plus"
    assert row.status == "active"
    assert row.cancel_at_period_end is True
    assert row.current_period_end is not None


@pytest.mark.asyncio
async def test_webhook_updated_with_canceled_status_downgrades(
    anon_client, session, test_org, monkeypatch
):
    """If Stripe emits subscription.updated with status=canceled, drop to free immediately."""
    session.add(
        Subscription(
            org_id=test_org.id,
            stripe_customer_id="cus_abc",
            stripe_subscription_id="sub_cxl",
            tier="plus",
            status="active",
        )
    )
    session.commit()

    event = {
        "id": "evt_cxl",
        "type": "customer.subscription.updated",
        "data": {
            "object": {
                "id": "sub_cxl",
                "customer": "cus_abc",
                "status": "canceled",
                "cancel_at_period_end": False,
                "metadata": {"org_id": str(test_org.id)},
            }
        },
    }
    _stub_construct_event(monkeypatch, event)

    client = await anon_client()
    async with client:
        resp = await client.post(
            "/api/billing/webhook",
            content=json.dumps(event).encode(),
            headers={"stripe-signature": "ok"},
        )
    assert resp.status_code == 200

    session.expire_all()
    row = session.get(Subscription, test_org.id)
    assert row is not None
    assert row.tier == "free"
    assert row.status == "canceled"


@pytest.mark.asyncio
async def test_webhook_ignores_missing_org_metadata(anon_client, session, monkeypatch):
    """Events without org metadata should 200 without touching DB."""
    event = {
        "id": "evt_skip",
        "type": "customer.subscription.updated",
        "data": {
            "object": {
                "id": "sub_999",
                "customer": "cus_xyz",
                "status": "active",
                "metadata": {},
            }
        },
    }
    _stub_construct_event(monkeypatch, event)

    client = await anon_client()
    async with client:
        resp = await client.post(
            "/api/billing/webhook",
            content=json.dumps(event).encode(),
            headers={"stripe-signature": "ok"},
        )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_webhook_idempotent_on_replay(anon_client, session, test_org, monkeypatch):
    stripe_sub_obj = SimpleNamespace(
        status="active",
        current_period_end=1800000000,
        cancel_at_period_end=False,
    )
    monkeypatch.setattr(
        "agent_port.billing.webhook.stripe.Subscription.retrieve",
        lambda sub_id: stripe_sub_obj,
    )

    event = {
        "id": "evt_1",
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "client_reference_id": str(test_org.id),
                "subscription": "sub_123",
                "customer": "cus_abc",
            }
        },
    }
    _stub_construct_event(monkeypatch, event)

    client = await anon_client()
    async with client:
        resp1 = await client.post(
            "/api/billing/webhook",
            content=json.dumps(event).encode(),
            headers={"stripe-signature": "ok"},
        )
        resp2 = await client.post(
            "/api/billing/webhook",
            content=json.dumps(event).encode(),
            headers={"stripe-signature": "ok"},
        )
    assert resp1.status_code == 200
    assert resp2.status_code == 200

    session.expire_all()
    # Still exactly one row
    row = session.get(Subscription, test_org.id)
    assert row is not None
    assert row.tier == "plus"


@pytest.mark.asyncio
async def test_webhook_handles_stripe_object_payload(anon_client, session, test_org, monkeypatch):
    """Regression: real Stripe events arrive as StripeObject, not dict — no .get() available."""
    stripe_sub_obj = _StripeLike(
        status="active",
        current_period_end=1800000000,
        cancel_at_period_end=False,
    )
    monkeypatch.setattr(
        "agent_port.billing.webhook.stripe.Subscription.retrieve",
        lambda sub_id: stripe_sub_obj,
    )

    event = _StripeLike(
        id="evt_strp",
        type="checkout.session.completed",
        data=_StripeLike(
            object=_StripeLike(
                client_reference_id=str(test_org.id),
                subscription="sub_strp",
                customer="cus_strp",
            )
        ),
    )
    _stub_construct_event(monkeypatch, event)

    client = await anon_client()
    async with client:
        resp = await client.post(
            "/api/billing/webhook",
            content=b"{}",
            headers={"stripe-signature": "ok"},
        )
    assert resp.status_code == 200

    row = session.get(Subscription, test_org.id)
    assert row is not None
    assert row.tier == "plus"


@pytest.mark.asyncio
async def test_webhook_subscription_changed_stripe_object(
    anon_client, session, test_org, monkeypatch
):
    """Regression: subscription.updated events carry StripeObject metadata, not dict."""
    event = _StripeLike(
        id="evt_strp2",
        type="customer.subscription.updated",
        data=_StripeLike(
            object=_StripeLike(
                id="sub_strp2",
                customer="cus_strp2",
                status="active",
                current_period_end=1800000000,
                cancel_at_period_end=True,
                metadata=_StripeLike(org_id=str(test_org.id)),
            )
        ),
    )
    _stub_construct_event(monkeypatch, event)

    client = await anon_client()
    async with client:
        resp = await client.post(
            "/api/billing/webhook",
            content=b"{}",
            headers={"stripe-signature": "ok"},
        )
    assert resp.status_code == 200

    row = session.get(Subscription, test_org.id)
    assert row is not None
    assert row.tier == "plus"
    assert row.cancel_at_period_end is True


@pytest.mark.asyncio
async def test_webhook_404_when_billing_disabled(session, monkeypatch):
    monkeypatch.setattr(settings, "is_cloud", False)
    monkeypatch.setattr(settings, "stripe_api_key", "")
    monkeypatch.setattr(settings, "stripe_price_plus", "")

    from agent_port.db import get_session

    def override_session():
        yield session

    app.dependency_overrides[get_session] = override_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        resp = await c.post(
            "/api/billing/webhook",
            content=b"{}",
            headers={"stripe-signature": "x"},
        )
    app.dependency_overrides.clear()
    assert resp.status_code == 404


# Silence unused-import warnings for identifiers referenced via monkeypatch paths
_ = uuid
