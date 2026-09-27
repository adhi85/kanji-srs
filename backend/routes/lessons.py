import json
import time
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from backend.database import get_db
from backend.models import Subject, SrsItem, Setting, SubjectDependency
from backend.srs_engine import next_review_time, DEFAULT_INTERVALS

router = APIRouter()


def _get_setting(db: Session, key: str, default=None):
    row = db.query(Setting).filter_by(key=key).first()
    return json.loads(row.value) if row else default


def _get_intervals(db: Session) -> list:
    return _get_setting(db, "srs_intervals", DEFAULT_INTERVALS)


@router.get("/lessons")
def get_lessons(db: Session = Depends(get_db)):
    from sqlalchemy import func
    from backend.jlpt_mapping import wanikani_level_to_jlpt
    from backend.routes.levels import compute_current_level

    batch_size = _get_setting(db, "lesson_batch_size", 5)
    dep_gating = _get_setting(db, "dependency_gating", False)
    jlpt_gating = _get_setting(db, "jlpt_gating", False)

    query = (
        db.query(SrsItem)
        .join(Subject)
        .filter(SrsItem.srs_stage == 0)
    )

    if dep_gating:
        blocked_ids = (
            db.query(SubjectDependency.subject_id)
            .join(SrsItem, SrsItem.subject_id == SubjectDependency.component_id)
            .group_by(SubjectDependency.subject_id)
            .having(func.min(SrsItem.srs_stage) < 5)
            .subquery()
        )
        query = query.filter(~SrsItem.subject_id.in_(db.query(blocked_ids)))

    if jlpt_gating:
        current_level = compute_current_level(db)
        current_jlpt = wanikani_level_to_jlpt(current_level)
        jlpt_order = {"N5": 1, "N4": 2, "N3": 3, "N2": 4, "N1": 5}
        current_rank = jlpt_order.get(current_jlpt, 5)
        allowed = [k for k, v in jlpt_order.items() if v <= current_rank]
        query = query.filter(Subject.jlpt_level.in_(allowed))

    items = query.order_by(Subject.level, Subject.id).limit(batch_size).all()
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
