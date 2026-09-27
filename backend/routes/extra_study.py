import json
import time
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from backend.database import get_db
from backend.models import Subject, SrsItem, User
from backend.auth import get_current_user
from backend.srs_engine import check_answer_meaning, check_answer_reading

router = APIRouter()

TWENTY_FOUR_HOURS = 86400


@router.get("/extra-study/summary")
def extra_study_summary(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    now = time.time()
    cutoff = now - TWENTY_FOUR_HOURS
    recent_mistakes = (
        db.query(SrsItem)
        .filter(SrsItem.user_id == current_user.id)
        .filter(SrsItem.last_incorrect_at != None, SrsItem.last_incorrect_at >= cutoff)
        .count()
    )
    recent_lessons = (
        db.query(SrsItem)
        .filter(SrsItem.user_id == current_user.id)
        .filter(SrsItem.started_at != None, SrsItem.started_at >= cutoff,
                SrsItem.srs_stage >= 1)
        .count()
    )
    burned = (
        db.query(SrsItem)
        .filter(SrsItem.user_id == current_user.id)
        .filter(SrsItem.srs_stage == 9)
        .count()
    )
    return {
        "recent_mistakes": recent_mistakes,
        "recent_lessons": recent_lessons,
        "burned": burned,
    }


@router.get("/extra-study")
def get_extra_study(mode: str = Query(...), db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    now = time.time()
    cutoff = now - TWENTY_FOUR_HOURS

    if mode == "recent_mistakes":
        items = (
            db.query(SrsItem).join(Subject)
            .filter(SrsItem.user_id == current_user.id)
            .filter(SrsItem.last_incorrect_at != None, SrsItem.last_incorrect_at >= cutoff)
            .all()
        )
    elif mode == "recent_lessons":
        items = (
            db.query(SrsItem).join(Subject)
            .filter(SrsItem.user_id == current_user.id)
            .filter(SrsItem.started_at != None, SrsItem.started_at >= cutoff,
                    SrsItem.srs_stage >= 1)
            .all()
        )
    elif mode == "burned":
        items = (
            db.query(SrsItem).join(Subject)
            .filter(SrsItem.user_id == current_user.id)
            .filter(SrsItem.srs_stage == 9)
            .all()
        )
    else:
        raise HTTPException(status_code=400, detail="Invalid mode")

    return [
        {
            "subject_id": item.subject_id,
            "type": item.subject.type,
            "characters": item.subject.characters,
        }
        for item in items
    ]


class ExtraStudyAnswer(BaseModel):
    answer_type: str
    answer: str


@router.post("/extra-study/{subject_id}")
def submit_extra_study(subject_id: int, req: ExtraStudyAnswer,
                       db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    subject = db.get(Subject, subject_id)
    if not subject:
        raise HTTPException(status_code=404, detail="Subject not found")

    meanings = json.loads(subject.meanings)
    readings = json.loads(subject.readings) if subject.readings else []

    if req.answer_type == "meaning":
        correct = check_answer_meaning(req.answer, meanings)
        correct_answer = next(
            (m["meaning"] for m in meanings if m.get("primary")), meanings[0]["meaning"]
        )
        mnemonic = subject.meaning_mnemonic
    elif req.answer_type == "reading":
        correct = check_answer_reading(req.answer, readings)
        correct_answer = next(
            (r["reading"] for r in readings if r.get("primary")),
            readings[0]["reading"] if readings else "",
        )
        mnemonic = subject.reading_mnemonic
    else:
        raise HTTPException(status_code=400, detail="answer_type must be 'meaning' or 'reading'")

    return {
        "correct": correct,
        "correct_answer": correct_answer if not correct else None,
        "mnemonic": mnemonic if not correct else None,
    }
