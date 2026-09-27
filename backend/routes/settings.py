import json
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from backend.database import get_db
from backend.models import Setting, User
from backend.auth import get_current_user

router = APIRouter()


@router.get("/settings")
def get_settings(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    rows = db.query(Setting).filter_by(user_id=current_user.id).all()
    return {row.key: json.loads(row.value) for row in rows}


@router.put("/settings")
def update_settings(updates: dict, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    for key, value in updates.items():
        setting = db.query(Setting).filter_by(user_id=current_user.id, key=key).first()
        if setting:
            setting.value = json.dumps(value)
    db.commit()
    return get_settings(db=db, current_user=current_user)
