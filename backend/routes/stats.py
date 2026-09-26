import time
from collections import defaultdict
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from backend.database import get_db
from backend.models import Subject, SrsItem

router = APIRouter()


@router.get("/summary")
def get_summary(db: Session = Depends(get_db)):
    now = time.time()

    reviews_available = (
        db.query(func.count(SrsItem.id))
        .filter(SrsItem.srs_stage.between(1, 8))
        .filter(SrsItem.next_review_at <= now)
        .scalar()
    )

    next_review = (
        db.query(func.min(SrsItem.next_review_at))
        .filter(SrsItem.srs_stage.between(1, 8))
        .filter(SrsItem.next_review_at > now)
        .scalar()
    )

    lessons_available = (
        db.query(func.count(SrsItem.id))
        .filter(SrsItem.srs_stage == 0)
        .scalar()
    )

    stage_counts = defaultdict(int)
    rows = db.query(SrsItem.srs_stage, func.count(SrsItem.id)).group_by(SrsItem.srs_stage).all()
    for stage, count in rows:
        stage_counts[str(stage)] = count

    jlpt_progress = {}
    jlpt_rows = (
        db.query(Subject.jlpt_level, func.count(Subject.id))
        .group_by(Subject.jlpt_level)
        .all()
    )
    for level, total in jlpt_rows:
        if level:
            burned = (
                db.query(func.count(SrsItem.id))
                .join(Subject)
                .filter(Subject.jlpt_level == level, SrsItem.srs_stage == 9)
                .scalar()
            )
            jlpt_progress[level] = {"total": total, "burned": burned}

    return {
        "reviews_available": reviews_available,
        "next_review_at": next_review,
        "lessons_available": lessons_available,
        "srs_stage_counts": dict(stage_counts),
        "jlpt_progress": jlpt_progress,
    }
