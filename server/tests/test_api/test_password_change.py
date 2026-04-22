import pytest

from agent_port.security import hash_password, verify_password


@pytest.mark.anyio
async def test_change_password_success(client, test_user, session):
    test_user.hashed_password = hash_password("oldpass123")
    session.add(test_user)
    session.commit()

    resp = await client.post(
        "/api/users/me/change-password",
        json={"current_password": "oldpass123", "new_password": "newpass456"},
    )
    assert resp.status_code == 200
    assert resp.json()["message"] == "Password changed successfully"

    session.refresh(test_user)
    assert verify_password("newpass456", test_user.hashed_password)


@pytest.mark.anyio
async def test_change_password_wrong_current(client, test_user, session):
    test_user.hashed_password = hash_password("oldpass123")
    session.add(test_user)
    session.commit()

    resp = await client.post(
        "/api/users/me/change-password",
        json={"current_password": "wrongpass", "new_password": "newpass456"},
    )
    assert resp.status_code == 400
    assert "incorrect" in resp.json()["detail"].lower()


@pytest.mark.anyio
async def test_change_password_too_short(client, test_user, session):
    test_user.hashed_password = hash_password("oldpass123")
    session.add(test_user)
    session.commit()

    resp = await client.post(
        "/api/users/me/change-password",
        json={"current_password": "oldpass123", "new_password": "short"},
    )
    assert resp.status_code == 400
    assert "6 characters" in resp.json()["detail"]
