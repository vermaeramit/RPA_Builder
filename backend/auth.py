"""Authentication & role-based access control.

- Passwords are hashed with bcrypt.
- Login issues a JWT (HS256) carrying the username (sub) and role.
- FastAPI dependencies enforce a minimum role on protected endpoints.

Roles form a hierarchy: viewer < editor < admin < superadmin.
  viewer     - read-only, OWN workflows/runs/schedules only
  editor     - viewer + run flows, create/edit/delete OWN workflows, manage OWN schedules
  admin      - editor + manage users (cannot grant superadmin)
  superadmin - sees & manages ALL users' workflows, runs, logs, schedules

Data ownership: every workflow/run/schedule has an owner_id. Non-superadmins are
scoped to rows they own; superadmin sees everything.
"""
from __future__ import annotations

import datetime
import os
import time
import uuid
from typing import List, Optional

import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select

from db import SessionLocal
from models import User

JWT_SECRET = os.getenv("JWT_SECRET", "dev-only-change-me")
JWT_ALGO = "HS256"
JWT_EXPIRE_HOURS = int(os.getenv("JWT_EXPIRE_HOURS", "12"))

ROLES = {"viewer": 1, "editor": 2, "admin": 3, "superadmin": 4}


def is_superadmin(user: dict) -> bool:
    return user.get("role") == "superadmin"

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/auth/login", auto_error=True)


# ---- password hashing -----------------------------------------------------
def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        return False


# ---- tokens ---------------------------------------------------------------
def create_token(username: str, role: str) -> str:
    now = datetime.datetime.now(datetime.timezone.utc)
    payload = {
        "sub": username,
        "role": role,
        "iat": now,
        "exp": now + datetime.timedelta(hours=JWT_EXPIRE_HOURS),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGO)


def _decode(token: str) -> dict:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGO])
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )


# ---- user store -----------------------------------------------------------
def _to_dict(u: User) -> dict:
    return {"id": u.id, "username": u.username, "role": u.role, "created": u.created}


def get_user(username: str) -> Optional[User]:
    with SessionLocal() as s:
        return s.execute(select(User).where(User.username == username)).scalar_one_or_none()


def get_user_by_id(user_id: str) -> Optional[dict]:
    with SessionLocal() as s:
        u = s.get(User, user_id)
        return _to_dict(u) if u else None


def authenticate(username: str, password: str) -> Optional[dict]:
    u = get_user(username)
    if u and verify_password(password, u.password_hash):
        return _to_dict(u)
    return None


def create_user(username: str, password: str, role: str = "viewer") -> dict:
    if role not in ROLES:
        raise ValueError(f"Invalid role '{role}'")
    if get_user(username):
        raise ValueError("Username already exists")
    with SessionLocal() as s:
        u = User(
            id=uuid.uuid4().hex[:12],
            username=username,
            password_hash=hash_password(password),
            role=role,
            created=int(time.time()),
        )
        s.add(u)
        s.commit()
        return _to_dict(u)


def list_users() -> List[dict]:
    with SessionLocal() as s:
        return [_to_dict(u) for u in s.execute(select(User).order_by(User.username)).scalars()]


def username_map() -> dict:
    """{user_id: username} — used to annotate owned rows for the superadmin view."""
    with SessionLocal() as s:
        return {u.id: u.username for u in s.execute(select(User)).scalars()}


def set_role(user_id: str, role: str) -> Optional[dict]:
    if role not in ROLES:
        raise ValueError(f"Invalid role '{role}'")
    with SessionLocal() as s:
        u = s.get(User, user_id)
        if not u:
            return None
        u.role = role
        s.commit()
        return _to_dict(u)


def delete_user(user_id: str) -> bool:
    with SessionLocal() as s:
        u = s.get(User, user_id)
        if not u:
            return False
        s.delete(u)
        s.commit()
        return True


def count_users() -> int:
    with SessionLocal() as s:
        return len(s.execute(select(User.id)).all())


def bootstrap_admin() -> None:
    """Create the root superadmin from env if the users table is empty."""
    if count_users() > 0:
        return
    username = os.getenv("ADMIN_USERNAME", "admin")
    password = os.getenv("ADMIN_PASSWORD", "admin")
    create_user(username, password, "superadmin")
    print(
        f"[auth] Bootstrapped superadmin '{username}'. "
        "CHANGE THIS PASSWORD via the Users panel for any real deployment."
    )


# ---- FastAPI dependencies -------------------------------------------------
def get_current_user(token: str = Depends(oauth2_scheme)) -> dict:
    payload = _decode(token)
    username = payload.get("sub")
    u = get_user(username) if username else None
    if not u:
        raise HTTPException(status_code=401, detail="User no longer exists")
    return _to_dict(u)


def require_role(min_role: str):
    """Dependency factory: require the current user to have at least `min_role`."""
    threshold = ROLES[min_role]

    def checker(user: dict = Depends(get_current_user)) -> dict:
        if ROLES.get(user["role"], 0) < threshold:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires '{min_role}' role or higher",
            )
        return user

    return checker
