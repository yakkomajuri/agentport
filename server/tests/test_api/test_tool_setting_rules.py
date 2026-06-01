from datetime import datetime

import pyotp
import pytest

RULES_BASE = "/api/tool-settings/resend/send_email/rules"


def _enable_totp(test_user, session) -> str:
    secret = pyotp.random_base32()
    test_user.totp_secret = secret
    test_user.totp_enabled = True
    test_user.totp_confirmed_at = datetime.utcnow()
    session.add(test_user)
    session.commit()
    return secret


def _rule_body(effect="require_approval", **kw):
    body = {
        "name": "Review sensitive subjects",
        "effect": effect,
        "priority": 100,
        "enabled": True,
        "conditions": [
            {"param_path": "subject", "operator": "contains", "values": ["password", "secret"]}
        ],
    }
    body.update(kw)
    return body


@pytest.mark.anyio
async def test_list_rules_empty(client):
    resp = await client.get(RULES_BASE)
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.anyio
async def test_create_and_list_rule(client):
    resp = await client.post(RULES_BASE, json=_rule_body())
    assert resp.status_code == 200
    rule = resp.json()
    assert rule["name"] == "Review sensitive subjects"
    assert rule["effect"] == "require_approval"
    assert rule["priority"] == 100
    assert rule["enabled"] is True
    assert len(rule["conditions"]) == 1
    assert rule["conditions"][0]["values"] == ["password", "secret"]

    resp = await client.get(RULES_BASE)
    assert resp.status_code == 200
    assert len(resp.json()) == 1


@pytest.mark.anyio
async def test_update_rule(client):
    created = (await client.post(RULES_BASE, json=_rule_body())).json()
    resp = await client.patch(
        f"{RULES_BASE}/{created['id']}",
        json={"name": "Renamed", "priority": 50, "enabled": False},
    )
    assert resp.status_code == 200
    updated = resp.json()
    assert updated["name"] == "Renamed"
    assert updated["priority"] == 50
    assert updated["enabled"] is False


@pytest.mark.anyio
async def test_update_rule_replaces_conditions(client):
    created = (await client.post(RULES_BASE, json=_rule_body())).json()
    resp = await client.patch(
        f"{RULES_BASE}/{created['id']}",
        json={
            "conditions": [
                {"param_path": "to", "operator": "ends_with", "values": ["@useskald.com"]}
            ]
        },
    )
    assert resp.status_code == 200
    conds = resp.json()["conditions"]
    assert len(conds) == 1
    assert conds[0]["param_path"] == "to"


@pytest.mark.anyio
async def test_delete_rule(client):
    created = (await client.post(RULES_BASE, json=_rule_body())).json()
    resp = await client.delete(f"{RULES_BASE}/{created['id']}")
    assert resp.status_code == 204
    resp = await client.get(RULES_BASE)
    assert resp.json() == []


@pytest.mark.anyio
async def test_delete_nonexistent_rule_404(client):
    import uuid

    resp = await client.delete(f"{RULES_BASE}/{uuid.uuid4()}")
    assert resp.status_code == 404


# ── validation ──


@pytest.mark.anyio
async def test_create_rejects_bad_effect(client):
    resp = await client.post(RULES_BASE, json=_rule_body(effect="maybe"))
    assert resp.status_code == 400


@pytest.mark.anyio
async def test_create_rejects_bad_operator(client):
    body = _rule_body()
    body["conditions"][0]["operator"] = "regex"
    resp = await client.post(RULES_BASE, json=body)
    assert resp.status_code == 400


@pytest.mark.anyio
async def test_create_rejects_empty_param_path(client):
    body = _rule_body()
    body["conditions"][0]["param_path"] = "  "
    resp = await client.post(RULES_BASE, json=body)
    assert resp.status_code == 400


@pytest.mark.anyio
async def test_create_rejects_too_many_values(client):
    body = _rule_body()
    body["conditions"][0]["values"] = [str(i) for i in range(21)]
    resp = await client.post(RULES_BASE, json=body)
    assert resp.status_code == 400


@pytest.mark.anyio
async def test_create_rejects_long_value(client):
    body = _rule_body()
    body["conditions"][0]["values"] = ["x" * 513]
    resp = await client.post(RULES_BASE, json=body)
    assert resp.status_code == 400


@pytest.mark.anyio
async def test_max_rules_per_tool(client):
    for i in range(20):
        resp = await client.post(RULES_BASE, json=_rule_body(name=f"r{i}"))
        assert resp.status_code == 200
    resp = await client.post(RULES_BASE, json=_rule_body(name="overflow"))
    assert resp.status_code == 400


# ── TOTP escalation for allow rules ──


@pytest.mark.anyio
async def test_create_allow_rule_requires_totp(client, session, test_user):
    _enable_totp(test_user, session)
    resp = await client.post(RULES_BASE, json=_rule_body(effect="allow"))
    assert resp.status_code == 403
    assert resp.json()["detail"]["error"] == "totp_required"


@pytest.mark.anyio
async def test_create_allow_rule_with_valid_totp(client, session, test_user):
    secret = _enable_totp(test_user, session)
    resp = await client.post(
        RULES_BASE, json=_rule_body(effect="allow", totp_code=pyotp.TOTP(secret).now())
    )
    assert resp.status_code == 200
    assert resp.json()["effect"] == "allow"


@pytest.mark.anyio
async def test_create_non_allow_rule_no_totp(client, session, test_user):
    _enable_totp(test_user, session)
    resp = await client.post(RULES_BASE, json=_rule_body(effect="deny"))
    assert resp.status_code == 200


@pytest.mark.anyio
async def test_update_to_allow_requires_totp(client, session, test_user):
    created = (await client.post(RULES_BASE, json=_rule_body(effect="deny"))).json()
    _enable_totp(test_user, session)
    resp = await client.patch(f"{RULES_BASE}/{created['id']}", json={"effect": "allow"})
    assert resp.status_code == 403
    assert resp.json()["detail"]["error"] == "totp_required"


@pytest.mark.anyio
async def test_broadening_active_allow_rule_conditions_requires_totp(client, session, test_user):
    secret = _enable_totp(test_user, session)
    # Create an active allow rule (with TOTP), then try to broaden its conditions.
    created = (
        await client.post(
            RULES_BASE,
            json=_rule_body(
                effect="allow",
                totp_code=pyotp.TOTP(secret).now(),
                conditions=[
                    {"param_path": "to", "operator": "ends_with", "values": ["@useskald.com"]}
                ],
            ),
        )
    ).json()
    resp = await client.patch(
        f"{RULES_BASE}/{created['id']}",
        json={"conditions": [{"param_path": "to", "operator": "ends_with", "values": ["@"]}]},
    )
    assert resp.status_code == 403
    assert resp.json()["detail"]["error"] == "totp_required"


@pytest.mark.anyio
async def test_changing_active_allow_rule_priority_requires_totp(client, session, test_user):
    secret = _enable_totp(test_user, session)
    created = (
        await client.post(
            RULES_BASE,
            json=_rule_body(effect="allow", priority=100, totp_code=pyotp.TOTP(secret).now()),
        )
    ).json()
    resp = await client.patch(f"{RULES_BASE}/{created['id']}", json={"priority": 10})
    assert resp.status_code == 403
    assert resp.json()["detail"]["error"] == "totp_required"


@pytest.mark.anyio
async def test_renaming_active_allow_rule_does_not_require_totp(client, session, test_user):
    secret = _enable_totp(test_user, session)
    created = (
        await client.post(
            RULES_BASE, json=_rule_body(effect="allow", totp_code=pyotp.TOTP(secret).now())
        )
    ).json()
    # A cosmetic name-only change must not re-challenge.
    resp = await client.patch(f"{RULES_BASE}/{created['id']}", json={"name": "Renamed"})
    assert resp.status_code == 200
    assert resp.json()["name"] == "Renamed"


# ── test endpoint ──


@pytest.mark.anyio
async def test_test_endpoint_reports_rule_match(client):
    await client.post(
        RULES_BASE,
        json={
            "name": "deny secrets",
            "effect": "deny",
            "conditions": [{"param_path": "subject", "operator": "contains", "values": ["secret"]}],
        },
    )
    resp = await client.post(f"{RULES_BASE}/test", json={"args": {"subject": "a secret"}})
    assert resp.status_code == 200
    data = resp.json()
    assert data["effect"] == "deny"
    assert data["source"] == "rule"
    assert data["matched_rule_id"] is not None


@pytest.mark.anyio
async def test_test_endpoint_reports_fallback(client):
    resp = await client.post(f"{RULES_BASE}/test", json={"args": {"subject": "hello"}})
    assert resp.status_code == 200
    data = resp.json()
    assert data["effect"] == "require_approval"
    assert data["source"] == "fallback"
    assert data["matched_rule_id"] is None
