import json
import time
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from backend.database import get_db
from sqlalchemy import func
from backend.models import Subject, SrsItem, Setting, UserSynonym, SubjectDependency, LevelEvent
from backend.routes.levels import compute_current_level
from backend.srs_engine import (
    advance_stage,
    retreat_stage,
    next_review_time,
    check_answer_meaning,
    check_answer_meaning_detailed,
    check_answer_reading,
    check_reading_hint,
    DEFAULT_INTERVALS,
)

router = APIRouter()


def _get_intervals(db: Session) -> list:
    row = db.query(Setting).filter_by(key="srs_intervals").first()
    return json.loads(row.value) if row else DEFAULT_INTERVALS


@router.get("/reviews")
def get_reviews(db: Session = Depends(get_db)):
    now = time.time()
    items = (
        db.query(SrsItem)
        .join(Subject)
        .filter(SrsItem.srs_stage.between(1, 8))
        .filter(SrsItem.next_review_at <= now)
        .order_by(SrsItem.next_review_at)
        .all()
    )
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
        synonyms = [{"id": syn.id, "meaning": syn.meaning}
                     for syn in db.query(UserSynonym).filter_by(subject_id=s.id).all()]
        results.append({
            "srs_item_id": item.id,
            "subject_id": item.subject_id,
            "type": s.type,
            "characters": s.characters,
            "meanings": json.loads(s.meanings),
            "readings": json.loads(s.readings) if s.readings else [],
            "meaning_mnemonic": s.meaning_mnemonic,
            "reading_mnemonic": s.reading_mnemonic,
            "meaning_hint": s.meaning_hint,
            "reading_hint": s.reading_hint,
            "auxiliary_meanings": json.loads(s.auxiliary_meanings) if s.auxiliary_meanings else [],
            "components": components,
            "user_synonyms": synonyms,
        })
    return results


class AnswerRequest(BaseModel):
    answer_type: str
    answer: str


@router.post("/reviews/{subject_id}")
def submit_review(subject_id: int, req: AnswerRequest, db: Session = Depends(get_db)):
    item = db.query(SrsItem).filter_by(subject_id=subject_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="SRS item not found")
    subject = db.get(Subject, subject_id)
    if not subject:
        raise HTTPException(status_code=404, detail="Subject not found")

    meanings = json.loads(subject.meanings)
    readings = json.loads(subject.readings) if subject.readings else []

    if req.answer_type == "meaning":
        user_syns = [s.meaning for s in db.query(UserSynonym).filter_by(subject_id=subject_id).all()]
        aux_meanings = json.loads(subject.auxiliary_meanings) if subject.auxiliary_meanings else []
        detailed = check_answer_meaning_detailed(req.answer, meanings, user_syns or None, auxiliary_meanings=aux_meanings or None)
        correct = detailed["status"] == "correct"
        close = detailed["status"] == "close"
        correct_answer = next((m["meaning"] for m in meanings if m.get("primary")), meanings[0]["meaning"])
        mnemonic = subject.meaning_mnemonic
    elif req.answer_type == "reading":
        correct = check_answer_reading(req.answer, readings)
        if not correct:
            hint = check_reading_hint(req.answer, readings)
            if hint:
                db.commit()
                return {
                    "correct": False,
                    "retry": True,
                    "hint": hint,
                    "correct_answer": None,
                    "new_stage": item.srs_stage,
                    "mnemonic": None,
                }
        close = False
        detailed = None
        correct_answer = next((r["reading"] for r in readings if r.get("primary")), readings[0]["reading"] if readings else "")
        mnemonic = subject.reading_mnemonic
    else:
        raise HTTPException(status_code=400, detail="answer_type must be 'meaning' or 'reading'")

    if close:
        return {
            "correct": False,
            "close": True,
            "did_you_mean": detailed.get("did_you_mean") if detailed else None,
            "correct_answer": None,
            "new_stage": item.srs_stage,
            "mnemonic": None,
        }

    if correct:
        if req.answer_type == "meaning":
            item.meaning_correct_in_session = 1
        else:
            item.reading_correct_in_session = 1
        item.correct_count += 1
    else:
        item.incorrect_count += 1
        item.last_incorrect_at = time.time()

    intervals = _get_intervals(db)
    new_stage = item.srs_stage
    both_needed = subject.type not in ("radical", "kana_vocabulary")
    meaning_done = item.meaning_correct_in_session == 1
    reading_done = item.reading_correct_in_session == 1 if both_needed else True

    if not correct and item.incorrect_in_session == 0:
        new_stage = retreat_stage(item.srs_stage)
        item.srs_stage = new_stage
        item.next_review_at = next_review_time(new_stage, intervals)
        item.incorrect_in_session = 1

    if meaning_done and reading_done:
        new_stage = advance_stage(item.srs_stage)
        item.srs_stage = new_stage
        item.next_review_at = next_review_time(new_stage, intervals)
        item.meaning_correct_in_session = 0
        item.reading_correct_in_session = 0
        item.incorrect_in_session = 0

    db.commit()

    level_up = None
    if meaning_done and reading_done:
        current_level = compute_current_level(db)
        max_recorded = db.query(func.max(LevelEvent.level)).scalar() or 0
        if current_level > max_recorded:
            db.add(LevelEvent(level=current_level, reached_at=time.time()))
            db.commit()
            level_up = {"new_level": current_level}

    return {
        "correct": correct,
        "close": False,
        "correct_answer": correct_answer if not correct else None,
        "new_stage": new_stage,
        "mnemonic": mnemonic if not correct else None,
        "level_up": level_up,
    }
