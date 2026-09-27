import json
import time
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from backend.database import get_db
from backend.models import Subject, SrsItem, Setting, SubjectDependency, User
from backend.auth import get_current_user
from backend.srs_engine import next_review_time, DEFAULT_INTERVALS

router = APIRouter()


def _get_setting(db: Session, user_id: int, key: str, default=None):
    row = db.query(Setting).filter_by(user_id=user_id, key=key).first()
    return json.loads(row.value) if row else default


def _get_intervals(db: Session, user_id: int) -> list:
    return _get_setting(db, user_id, "srs_intervals", DEFAULT_INTERVALS)


@router.get("/lessons")
def get_lessons(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    from sqlalchemy import func
    from backend.jlpt_mapping import wanikani_level_to_jlpt
    from backend.routes.levels import compute_current_level

    batch_size = _get_setting(db, current_user.id, "lesson_batch_size", 5)
    dep_gating = _get_setting(db, current_user.id, "dependency_gating", False)
    jlpt_gating = _get_setting(db, current_user.id, "jlpt_gating", False)

    query = (
        db.query(SrsItem)
        .join(Subject)
        .filter(SrsItem.user_id == current_user.id)
        .filter(SrsItem.srs_stage == 0)
    )

    if dep_gating:
        blocked_ids = (
            db.query(SubjectDependency.subject_id)
            .join(SrsItem, SrsItem.subject_id == SubjectDependency.component_id)
            .filter(SrsItem.user_id == current_user.id)
            .group_by(SubjectDependency.subject_id)
            .having(func.min(SrsItem.srs_stage) < 5)
            .subquery()
        )
        query = query.filter(~SrsItem.subject_id.in_(db.query(blocked_ids)))

    if jlpt_gating:
        current_level = compute_current_level(db, current_user.id)
        current_jlpt = wanikani_level_to_jlpt(current_level)
        jlpt_order = {"N5": 1, "N4": 2, "N3": 3, "N2": 4, "N1": 5}
        current_rank = jlpt_order.get(current_jlpt, 5)
        allowed = [k for k, v in jlpt_order.items() if v <= current_rank]
        query = query.filter(Subject.jlpt_level.in_(allowed))

    items = query.order_by(Subject.level, Subject.id).limit(batch_size).all()
    results = []
    for item in items:
        s = item.subject
        comp_ids = db.query(SubjectDependency.component_id).filter_by(subject_id=s.id).all()
        components = []
        for (cid,) in comp_ids:
            c = db.get(Subject, cid)
            if c:
                components.append({
                    "id": c.id, "characters": c.characters, "type": c.type,
                    "meanings": json.loads(c.meanings),
                })

        vis_similar = []
        if s.type == "kanji" and s.visually_similar_subject_ids:
            for vid in json.loads(s.visually_similar_subject_ids):
                vs = db.get(Subject, vid)
                if vs:
                    vis_similar.append({
                        "id": vs.id, "characters": vs.characters, "type": vs.type,
                        "meanings": json.loads(vs.meanings),
                    })

        results.append({
            "id": s.id,
            "type": s.type,
            "characters": s.characters,
            "slug": s.slug,
            "character_image": s.character_image,
            "meanings": json.loads(s.meanings),
            "readings": json.loads(s.readings) if s.readings else [],
            "meaning_mnemonic": s.meaning_mnemonic,
            "reading_mnemonic": s.reading_mnemonic,
            "meaning_hint": s.meaning_hint,
            "reading_hint": s.reading_hint,
            "components": components,
            "context_sentences": json.loads(s.context_sentences) if s.context_sentences else [],
            "part_of_speech": json.loads(s.part_of_speech) if s.part_of_speech else [],
            "visually_similar": vis_similar,
        })
    return results


class StartLessonsRequest(BaseModel):
    subject_ids: list


@router.post("/lessons/start")
def start_lessons(req: StartLessonsRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    intervals = _get_intervals(db, current_user.id)
    started = 0
    for sid in req.subject_ids:
        item = db.query(SrsItem).filter_by(user_id=current_user.id, subject_id=sid, srs_stage=0).first()
        if item:
            item.srs_stage = 1
            item.started_at = time.time()
            item.next_review_at = next_review_time(1, intervals)
            started += 1
    db.commit()
    return {"started": started}
