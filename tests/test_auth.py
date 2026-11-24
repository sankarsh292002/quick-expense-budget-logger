"""Tests for register / login / access control. Owner: Member D."""
import base64
import json
from datetime import datetime, timedelta, timezone

import jwt

from app.auth import AuthService
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
    header, payload, signature = token.split(".")  # a JWT has three parts
    data = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
    data["sub"] = "999"  # try to pretend to be user 999
    forged_payload = base64.urlsafe_b64encode(json.dumps(data).encode()).decode().rstrip("=")
    forged = f"{header}.{forged_payload}.{signature}"  # old signature no longer matches
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {forged}"}).status_code == 401


def test_token_is_a_jwt_with_sub_and_exp(client):
    headers = register(client, "ben")
    token = headers["Authorization"].split(" ")[1]
    payload = jwt.decode(token, AuthService.SECRET_KEY, algorithms=[AuthService.ALGORITHM])
    me = client.get("/api/auth/me", headers=headers).json()
    assert payload["sub"] == str(me["user_id"]) and "exp" in payload


def test_expired_token_is_rejected(client):
    headers = register(client, "ben")
    user_id = client.get("/api/auth/me", headers=headers).json()["user_id"]
    expired = jwt.encode(
        {"sub": str(user_id), "exp": datetime.now(timezone.utc) - timedelta(minutes=1)},
        AuthService.SECRET_KEY,
        algorithm=AuthService.ALGORITHM,
    )
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {expired}"}).status_code == 401
