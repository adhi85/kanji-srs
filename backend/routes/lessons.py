import json
import time
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from backend.database import get_db
from backend.models import Subject, SrsItem, Setting
from backend.srs_engine import next_review_time, DEFAULT_INTERVALS

router = APIRouter()


def _get_setting(db: Session, key: str, default=None):
    row = db.query(Setting).filter_by(key=key).first()
    return json.loads(row.value) if row else default


def _get_intervals(db: Session) -> list:
    return _get_setting(db, "srs_intervals", DEFAULT_INTERVALS)


@router.get("/lessons")
def get_lessons(db: Session = Depends(get_db)):
    batch_size = _get_setting(db, "lesson_batch_size", 5)
    items = (
        db.query(SrsItem)
        .join(Subject)
        .filter(SrsItem.srs_stage == 0)
        .order_by(Subject.level, Subject.id)
        .limit(batch_size)
        .all()
    )
    results = []
    for item in items:
        s = item.subject
        results.append({
            "id": s.id,
            "type": s.type,
            "characters": s.characters,
            "meanings": json.loads(s.meanings),
            "readings": json.loads(s.readings) if s.readings else [],
            "meaning_mnemonic": s.meaning_mnemonic,
            "reading_mnemonic": s.reading_mnemonic,
        })
    return results


class StartLessonsRequest(BaseModel):
    subject_ids: list


@router.post("/lessons/start")
def start_lessons(req: StartLessonsRequest, db: Session = Depends(get_db)):
    intervals = _get_intervals(db)
    started = 0
    for sid in req.subject_ids:
        item = db.query(SrsItem).filter_by(subject_id=sid, srs_stage=0).first()
        if item:
            item.srs_stage = 1
            item.started_at = time.time()
            item.next_review_at = next_review_time(1, intervals)
            started += 1
    db.commit()
    return {"started": started}
