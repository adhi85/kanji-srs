import json
import time
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from backend.database import get_db
from backend.models import User, Setting, Subject, SrsItem
from backend.auth import hash_password, verify_password, create_access_token, get_current_user

router = APIRouter(prefix="/auth")

SETTING_DEFAULTS = {
    "srs_intervals": [0, 14400, 28800, 82800, 169200, 601200, 1206000, 2588400, 10364400, 0],
    "lesson_batch_size": 5,
    "jlpt_gating": True,
    "dependency_gating": True,
    "max_reviews_per_session": None,
}


class AuthRequest(BaseModel):
    username: str
    password: str


@router.post("/register")
def register(req: AuthRequest, db: Session = Depends(get_db)):
    existing = db.query(User).filter_by(username=req.username).first()
    if existing:
        raise HTTPException(status_code=409, detail="Username already taken")
    user = User(
        username=req.username,
        password_hash=hash_password(req.password),
        created_at=time.time(),
    )
    db.add(user)
    db.flush()
    for k, v in SETTING_DEFAULTS.items():
        db.add(Setting(user_id=user.id, key=k, value=json.dumps(v)))
    subject_ids = [s.id for s in db.query(Subject.id).all()]
    for sid in subject_ids:
        db.add(SrsItem(user_id=user.id, subject_id=sid, srs_stage=0))
    db.commit()
    token = create_access_token(user.id, user.username)
    return {"token": token, "user": {"id": user.id, "username": user.username}}


@router.post("/login")
def login(req: AuthRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter_by(username=req.username).first()
    if not user or not verify_password(req.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_access_token(user.id, user.username)
    return {"token": token, "user": {"id": user.id, "username": user.username}}


@router.get("/me")
def me(current_user: User = Depends(get_current_user)):
    return {"id": current_user.id, "username": current_user.username}
