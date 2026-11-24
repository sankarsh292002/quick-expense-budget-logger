"""
routers/auth.py - register, log in, and "who am I?".

Owner: Member A (API)

    POST /api/auth/register   create an account      -> 201 + token
    POST /api/auth/login      check username/password -> 200 + token
    GET  /api/auth/me         the logged-in user      -> 200
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from .. import crud, models, schemas
from ..database import get_db
from ..auth import AuthService, get_current_user

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", response_model=schemas.TokenOut, status_code=status.HTTP_201_CREATED)
def register(data: schemas.UserCreate, db: Session = Depends(get_db)):
    if crud.get_user_by_username(db, data.username):
        raise HTTPException(status_code=409, detail="Username already taken")
    if crud.get_user_by_email(db, data.email.lower()):
        raise HTTPException(status_code=409, detail="Email already registered")
    user = crud.create_user(db, data)
    return {"access_token": AuthService.create_token(user.user_id), "user": user}


@router.post("/login", response_model=schemas.TokenOut)
def login(data: schemas.LoginRequest, db: Session = Depends(get_db)):
    user = crud.get_user_by_username(db, data.username)
    # Same message for "no such user" and "wrong password", so an attacker
    # cannot find out which usernames exist.
    if user is None or not AuthService.verify_password(data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Wrong username or password")
    return {"access_token": AuthService.create_token(user.user_id), "user": user}


@router.get("/me", response_model=schemas.UserOut)
def me(user: models.User = Depends(get_current_user)):
    return user
