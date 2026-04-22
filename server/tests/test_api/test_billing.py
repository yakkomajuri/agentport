"""Tests for /api/billing routes."""

import pytest
from httpx import ASGITransport, AsyncClient

from agent_port.config import settings
from agent_port.main import app


@pytest.fixture
def billing_on(monkeypatch):
    """Enable billing_enabled() to return True for this test."""
    monkeypatch.setattr(settings, "is_cloud", True)
    monkeypatch.setattr(settings, "stripe_api_key", "sk_test_dummy")
    monkeypatch.setattr(settings, "stripe_price_plus", "price_plus_123")
    monkeypatch.setattr(settings, "stripe_webhook_secret", "whsec_test")
    assert settings.billing_enabled()


@pytest.fixture
def stripe_stubs(monkeypatch):
    """Stub out all external Stripe SDK calls so tests run offline."""

    class _Customer:
        id = "cus_test123"

    class _Checkout:
        url = "https://checkout.stripe.com/test"

    class _Portal:
        url = "https://billing.stripe.com/test"

    monkeypatch.setattr(
        "agent_port.api.billing.stripe.Customer.create",
        lambda **kw: _Customer(),
    )
    monkeypatch.setattr(
        "agent_port.api.billing.stripe.checkout.Session.create",
        lambda **kw: _Checkout(),
    )
    monkeypatch.setattr(
        "agent_port.api.billing.stripe.billing_portal.Session.create",
        lambda **kw: _Portal(),
    )


@pytest.fixture
def billing_off(monkeypatch):
    monkeypatch.setattr(settings, "is_cloud", False)
    monkeypatch.setattr(settings, "stripe_api_key", "")
    monkeypatch.setattr(settings, "stripe_price_plus", "")


@pytest.mark.asyncio
async def test_subscription_returns_404_when_billing_disabled(client, billing_off):
    resp = await client.get("/api/billing/subscription")
    assert resp.status_code == 404
    assert resp.json()["detail"] == "billing_disabled"


@pytest.mark.asyncio
async def test_subscription_requires_auth():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        resp = await c.get("/api/billing/subscription")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_subscription_creates_free_row_on_first_access(
    client, session, test_org, billing_on, stripe_stubs
):
    from agent_port.models.subscription import Subscription

    assert session.get(Subscription, test_org.id) is None

    resp = await client.get("/api/billing/subscription")
    assert resp.status_code == 200
    body = resp.json()
    assert body["tier"] == "free"
    assert body["status"] == "active"
    assert body["cancel_at_period_end"] is False
    assert "@" in body["enterprise_contact_email"]

    row = session.get(Subscription, test_org.id)
    assert row is not None
    assert row.stripe_customer_id == "cus_test123"


@pytest.mark.asyncio
async def test_checkout_returns_redirect_url(client, billing_on, stripe_stubs):
    resp = await client.post("/api/billing/checkout")
    assert resp.status_code == 200
    assert resp.json()["url"] == "https://checkout.stripe.com/test"


@pytest.mark.asyncio
async def test_portal_returns_redirect_url(client, billing_on, stripe_stubs):
    resp = await client.post("/api/billing/portal")
    assert resp.status_code == 200
    assert resp.json()["url"] == "https://billing.stripe.com/test"


@pytest.mark.asyncio
async def test_non_owner_cannot_checkout(client, session, test_user, test_org, billing_on):
    from agent_port.models.org_membership import OrgMembership

    membership = session.get(OrgMembership, (test_user.id, test_org.id))
    assert membership is not None
    membership.role = "member"
    session.add(membership)
    session.commit()

    resp = await client.post("/api/billing/checkout")
    assert resp.status_code == 403
    assert resp.json()["detail"] == "owner_required"


@pytest.mark.asyncio
async def test_non_owner_cannot_open_portal(client, session, test_user, test_org, billing_on):
    from agent_port.models.org_membership import OrgMembership

    membership = session.get(OrgMembership, (test_user.id, test_org.id))
    assert membership is not None
    membership.role = "member"
    session.add(membership)
    session.commit()

    resp = await client.post("/api/billing/portal")
    assert resp.status_code == 403
