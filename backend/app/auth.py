from __future__ import annotations

import datetime as dt
from typing import Callable, Optional

import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from . import config
from .db import get_db
from .models import User

bearer = HTTPBearer(auto_error=False)


def verify_password(pw: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(pw.encode(), hashed.encode())
    except ValueError:
        return False


def make_token(user: User) -> str:
    payload = {"sub": user.username, "role": user.role, "actorId": user.actor_id,
               "exp": dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=config.JWT_HOURS)}
    return jwt.encode(payload, config.JWT_SECRET, algorithm="HS256")


def user_from_token(token: str, db: Session) -> Optional[User]:
    try:
        data = jwt.decode(token, config.JWT_SECRET, algorithms=["HS256"])
    except jwt.PyJWTError:
        return None
    return db.get(User, data.get("sub"))


def current_user(cred: Optional[HTTPAuthorizationCredentials] = Depends(bearer), db: Session = Depends(get_db)) -> User:
    if cred is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Chưa đăng nhập")
    user = user_from_token(cred.credentials, db)
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token không hợp lệ hoặc đã hết hạn")
    return user


def require_roles(*roles: str) -> Callable:
    def dep(user: User = Depends(current_user)) -> User:
        if user.role != "ADMIN" and user.role not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Không đủ quyền")
        return user

    return dep


def user_dict(u: User) -> dict:
    return {"username": u.username, "role": u.role, "actorId": u.actor_id}
