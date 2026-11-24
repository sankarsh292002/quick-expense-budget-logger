"""Tests for register / login / access control. Owner: Member D."""
from conftest import register


def test_register_and_me(client):
    headers = register(client, "ben")
    me = client.get("/api/auth/me", headers=headers).json()
    assert me["username"] == "ben"
    assert "password" not in me and "password_hash" not in me  # never leak the hash


def test_duplicate_username_is_rejected(client):
    register(client, "ben")
    res = client.post("/api/auth/register", json={"username": "ben", "email": "x@y.de", "password": "secret123"})
    assert res.status_code == 409


def test_login_right_and_wrong_password(client):
    register(client, "ben", "secret123")
    assert client.post("/api/auth/login", json={"username": "ben", "password": "secret123"}).status_code == 200
    assert client.post("/api/auth/login", json={"username": "ben", "password": "wrong"}).status_code == 401


def test_short_password_is_rejected(client):
    res = client.post("/api/auth/register", json={"username": "ben", "email": "b@x.de", "password": "123"})
    assert res.status_code == 422


def test_protected_routes_need_login(client):
    assert client.get("/api/expenses").status_code == 401
    assert client.get("/api/expenses", headers={"Authorization": "Bearer fake.token.here"}).status_code == 401


def test_tampered_token_is_rejected(client):
    headers = register(client, "ben")
    token = headers["Authorization"].split(" ")[1]
    user_id, expires, signature = token.split(".")
    forged = f"999.{expires}.{signature}"  # try to pretend to be user 999
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {forged}"}).status_code == 401
