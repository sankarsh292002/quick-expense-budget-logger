"""
security.py - password hashing and login tokens.

Owner: Member A (API)

Uses only Python's standard library, so there is nothing extra to install.

PASSWORDS
  We store hash(salt + password), never the password itself. A "salt" is
  random bytes added so that two users with the same password still get
  different hashes. PBKDF2 runs the hash 200,000 times to make guessing slow.

TOKENS
  After login the server gives the browser a token like
      "7.1767225600.Zm9vYmFy..."   ->   user_id . expiry time . signature
  The signature is an HMAC: a fingerprint made with a secret key only the
  server knows. If anyone changes the user_id, the fingerprint no longer
  matches and the token is rejected. The browser sends the token back in
  every request header:  Authorization: Bearer <token>
"""
import base64
import hashlib
import hmac
import os
import secrets
import time

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from .database import get_db
from . import models

# In a real deployment this must be a long random secret set outside the code.
SECRET_KEY = os.getenv("SECRET_KEY", "change-me-for-anything-real")  # set in .env
TOKEN_LIFETIME_SECONDS = 60 * 60 * 24  # 24 hours
PBKDF2_ROUNDS = 200_000


# ---------- Passwords ----------

def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, PBKDF2_ROUNDS)
    return f"{salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    salt_hex, digest_hex = stored.split("$")
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt_hex), PBKDF2_ROUNDS)
    # compare_digest avoids leaking information through timing differences
    return hmac.compare_digest(digest.hex(), digest_hex)


# ---------- Tokens ----------

def _sign(message: str) -> str:
    mac = hmac.new(SECRET_KEY.encode(), message.encode(), hashlib.sha256).digest()
    return base64.urlsafe_b64encode(mac).decode().rstrip("=")


def create_token(user_id: int) -> str:
    expires = int(time.time()) + TOKEN_LIFETIME_SECONDS
    message = f"{user_id}.{expires}"
    return f"{message}.{_sign(message)}"


def read_token(token: str) -> int | None:
    """Return the user_id if the token is genuine and not expired, else None."""
    try:
        user_id, expires, signature = token.split(".")
    except ValueError:
        return None
    if not hmac.compare_digest(signature, _sign(f"{user_id}.{expires}")):
        return None
    if int(expires) < time.time():
        return None
    return int(user_id)


# ---------- The dependency every protected route uses ----------

bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> models.User:
    """Find the logged-in user from the Authorization header, or answer 401."""
    not_logged_in = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not logged in or session expired",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if credentials is None:
        raise not_logged_in
    user_id = read_token(credentials.credentials)
    if user_id is None:
        raise not_logged_in
    user = db.get(models.User, user_id)
    if user is None:
        raise not_logged_in
    return user
