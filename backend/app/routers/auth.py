from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..auth import current_user, make_token, user_dict, verify_password
from ..db import get_db
from ..models import Actor, User
from ..schemas import LoginIn
from ..serializers import actor_dict

router = APIRouter(tags=["auth"])


@router.post("/auth/login")
def login(body: LoginIn, db: Session = Depends(get_db)) -> dict:
    u = db.get(User, body.username)
    if u is None or not verify_password(body.password, u.password_hash):
        raise HTTPException(401, "Sai tên đăng nhập hoặc mật khẩu")
    return {"token": make_token(u), "user": me_dict(db, u)}


def me_dict(db: Session, u: User) -> dict:
    a = db.get(Actor, u.actor_id) if u.actor_id else None
    return {**user_dict(u), "actor": actor_dict(a) if a else None}


@router.get("/me")
def me(user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    return me_dict(db, user)


@router.get("/auth/demo-users")
def demo_users(db: Session = Depends(get_db)) -> list[dict]:
    """Danh sách tài khoản demo cho trang đăng nhập (mật khẩu demo1234)."""
    out = []
    for u in db.query(User).order_by(User.username).all():
        a = db.get(Actor, u.actor_id) if u.actor_id else None
        out.append({"username": u.username, "role": u.role, "actorName": a.name if a else "Quản trị hệ thống"})
    return out
