import json
import time
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from backend.database import get_db
from backend.models import Subject, SrsItem, Setting, UserSynonym
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
    return [
        {
            "srs_item_id": item.id,
            "subject_id": item.subject_id,
            "type": item.subject.type,
            "characters": item.subject.characters,
        }
        for item in items
    ]


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
        detailed = check_answer_meaning_detailed(req.answer, meanings, user_syns or None)
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
    both_needed = subject.type != "radical"
    meaning_done = item.meaning_correct_in_session == 1
    reading_done = item.reading_correct_in_session == 1 if both_needed else True

    if meaning_done and reading_done:
        new_stage = advance_stage(item.srs_stage)
        item.srs_stage = new_stage
        item.next_review_at = next_review_time(new_stage, intervals)
        item.meaning_correct_in_session = 0
        item.reading_correct_in_session = 0
    elif not correct:
        new_stage = retreat_stage(item.srs_stage)
        item.srs_stage = new_stage
        item.next_review_at = next_review_time(new_stage, intervals)
        item.meaning_correct_in_session = 0
        item.reading_correct_in_session = 0

    db.commit()

    return {
        "correct": correct,
        "close": False,
        "correct_answer": correct_answer if not correct else None,
        "new_stage": new_stage,
        "mnemonic": mnemonic if not correct else None,
    }
