import json
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from backend.database import get_db
from backend.models import Setting

router = APIRouter()


@router.get("/settings")
def get_settings(db: Session = Depends(get_db)):
    rows = db.query(Setting).all()
    return {row.key: json.loads(row.value) for row in rows}


@router.put("/settings")
def update_settings(updates: dict, db: Session = Depends(get_db)):
    for key, value in updates.items():
        setting = db.query(Setting).filter_by(key=key).first()
        if setting:
            setting.value = json.dumps(value)
    db.commit()
    return get_settings(db)
