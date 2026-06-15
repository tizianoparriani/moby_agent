from __future__ import annotations
from datetime import datetime, timezone, timedelta

import bcrypt
import jwt
from fastapi import Depends, Header, HTTPException

from apps.api.settings import settings
from apps.api.db import get_user_by_username


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())


def create_token(username: str) -> str:
    payload = {
        "sub": username,
        "exp": datetime.now(timezone.utc) + timedelta(hours=settings.JWT_EXPIRE_HOURS),
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm="HS256")


def _decode_token(token: str) -> str:
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=["HS256"])
        return payload["sub"]
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Sessione scaduta, effettua nuovamente il login")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Token non valido")


def _bearer_token(authorization: str | None = Header(None)) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Token mancante")
    return authorization.split(" ", 1)[1]


def get_current_user(token: str = Depends(_bearer_token)) -> dict:
    username = _decode_token(token)
    user = get_user_by_username(username)
    if not user:
        raise HTTPException(status_code=401, detail="Utente non trovato")
    return user


def require_admin(user: dict = Depends(get_current_user)) -> dict:
    if not user["is_admin"]:
        raise HTTPException(status_code=403, detail="Accesso riservato agli amministratori")
    return user
