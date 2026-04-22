"""Tests for the require_plus billing gate."""

import pytest
from fastapi import HTTPException

from agent_port.billing.gate import require_plus
from agent_port.models.subscription import Subscription


def test_require_plus_raises_when_no_subscription_row(session, test_org):
    with pytest.raises(HTTPException) as exc:
        require_plus(org=test_org, session=session)
    assert exc.value.status_code == 402


def test_require_plus_raises_for_free_tier(session, test_org):
    session.add(
        Subscription(
            org_id=test_org.id,
            stripe_customer_id="cus_x",
            tier="free",
            status="active",
        )
    )
    session.commit()

    with pytest.raises(HTTPException) as exc:
        require_plus(org=test_org, session=session)
    assert exc.value.status_code == 402


def test_require_plus_passes_for_active_plus(session, test_org):
    session.add(
        Subscription(
            org_id=test_org.id,
            stripe_customer_id="cus_x",
            stripe_subscription_id="sub_x",
            tier="plus",
            status="active",
        )
    )
    session.commit()

    # Returns None on success
    require_plus(org=test_org, session=session)


def test_require_plus_passes_for_trialing_plus(session, test_org):
    session.add(
        Subscription(
            org_id=test_org.id,
            stripe_customer_id="cus_x",
            stripe_subscription_id="sub_x",
            tier="plus",
            status="trialing",
        )
    )
    session.commit()
    require_plus(org=test_org, session=session)


def test_require_plus_raises_for_past_due(session, test_org):
    session.add(
        Subscription(
            org_id=test_org.id,
            stripe_customer_id="cus_x",
            stripe_subscription_id="sub_x",
            tier="plus",
            status="past_due",
        )
    )
    session.commit()

    with pytest.raises(HTTPException) as exc:
        require_plus(org=test_org, session=session)
    assert exc.value.status_code == 402


def test_require_plus_raises_for_canceled(session, test_org):
    session.add(
        Subscription(
            org_id=test_org.id,
            stripe_customer_id="cus_x",
            tier="free",
            status="canceled",
        )
    )
    session.commit()

    with pytest.raises(HTTPException) as exc:
        require_plus(org=test_org, session=session)
    assert exc.value.status_code == 402
