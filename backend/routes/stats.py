import time
from collections import defaultdict
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import case, func
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

    level_rows = (
        db.query(
            Subject.level,
            func.count(Subject.id).label("total"),
            func.sum(case((SrsItem.srs_stage >= 5, 1), else_=0)).label("passed"),
        )
        .outerjoin(SrsItem)
        .filter(Subject.type == "kanji")
        .group_by(Subject.level)
        .all()
    )
    level_map = {r.level: (r.total, r.passed or 0) for r in level_rows}
    current_level = 1
    for lvl in range(1, 61):
        if lvl not in level_map:
            break
        total_k, passed_k = level_map[lvl]
        if total_k > 0 and passed_k / total_k >= 0.9:
            current_level = lvl + 1
        else:
            break
    current_level = min(current_level, 60)

    progress_rows = (
        db.query(
            Subject.type,
            func.count(Subject.id).label("total"),
            func.sum(case((SrsItem.srs_stage >= 5, 1), else_=0)).label("passed"),
        )
        .outerjoin(SrsItem)
        .filter(Subject.level == current_level)
        .group_by(Subject.type)
        .all()
    )
    level_progress = {"level": current_level, "kanji_total": 0, "kanji_passed": 0,
                      "radical_total": 0, "radical_passed": 0}
    for row in progress_rows:
        if row.type == "kanji":
            level_progress["kanji_total"] = row.total
            level_progress["kanji_passed"] = row.passed or 0
        elif row.type == "radical":
            level_progress["radical_total"] = row.total
            level_progress["radical_passed"] = row.passed or 0

    jlpt_list = sorted(
        [{"jlpt_level": k, **v} for k, v in jlpt_progress.items()],
        key=lambda x: x["jlpt_level"],
    )

    return {
        "reviews_available": reviews_available,
        "next_review_at": next_review,
        "lessons_available": lessons_available,
        "srs_stage_counts": dict(stage_counts),
        "jlpt_progress": jlpt_list,
        "current_level": current_level,
        "level_progress": level_progress,
    }
