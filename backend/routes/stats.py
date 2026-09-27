import json
import time
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import case, func
from backend.database import get_db
from backend.models import Subject, SrsItem, LevelEvent, User
from backend.auth import get_current_user

router = APIRouter()


@router.get("/summary")
def get_summary(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    now = time.time()

    reviews_available = (
        db.query(func.count(SrsItem.id))
        .filter(SrsItem.user_id == current_user.id)
        .filter(SrsItem.srs_stage.between(1, 8))
        .filter(SrsItem.next_review_at <= now)
        .scalar()
    )

    next_review = (
        db.query(func.min(SrsItem.next_review_at))
        .filter(SrsItem.user_id == current_user.id)
        .filter(SrsItem.srs_stage.between(1, 8))
        .filter(SrsItem.next_review_at > now)
        .scalar()
    )

    lessons_available = (
        db.query(func.count(SrsItem.id))
        .filter(SrsItem.user_id == current_user.id)
        .filter(SrsItem.srs_stage == 0)
        .scalar()
    )

    stage_counts = defaultdict(int)
    rows = (
        db.query(SrsItem.srs_stage, func.count(SrsItem.id))
        .filter(SrsItem.user_id == current_user.id)
        .group_by(SrsItem.srs_stage)
        .all()
    )
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
                .filter(SrsItem.user_id == current_user.id)
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
        .outerjoin(SrsItem, (SrsItem.subject_id == Subject.id) & (SrsItem.user_id == current_user.id))
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
        .outerjoin(SrsItem, (SrsItem.subject_id == Subject.id) & (SrsItem.user_id == current_user.id))
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


@router.get("/forecast")
def get_forecast(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    now = time.time()
    now_dt = datetime.fromtimestamp(now, tz=timezone.utc)

    items = (
        db.query(SrsItem.next_review_at)
        .filter(SrsItem.user_id == current_user.id)
        .filter(SrsItem.srs_stage.between(1, 8))
        .filter(SrsItem.next_review_at > now)
        .filter(SrsItem.next_review_at <= now + 5 * 86400)
        .all()
    )

    hourly = {}
    daily = {}

    for (review_at,) in items:
        review_dt = datetime.fromtimestamp(review_at, tz=timezone.utc)
        if review_at <= now + 86400:
            hour_key = review_dt.strftime("%Y-%m-%dT%H:00")
            hourly[hour_key] = hourly.get(hour_key, 0) + 1
        day_key = review_dt.strftime("%Y-%m-%d")
        daily[day_key] = daily.get(day_key, 0) + 1

    next_24h = []
    for h in range(24):
        hour_dt = now_dt.replace(minute=0, second=0, microsecond=0) + timedelta(hours=h)
        key = hour_dt.strftime("%Y-%m-%dT%H:00")
        label = hour_dt.strftime("%H:00")
        next_24h.append({"hour": key, "label": label, "count": hourly.get(key, 0)})

    next_5_days = []
    for d in range(5):
        day_dt = now_dt + timedelta(days=d)
        key = day_dt.strftime("%Y-%m-%d")
        label = day_dt.strftime("%a %m/%d")
        next_5_days.append({"date": key, "label": label, "count": daily.get(key, 0)})

    return {"next_24h": next_24h, "next_5_days": next_5_days}


@router.get("/critical-items")
def get_critical_items(limit: int = Query(10, ge=0), db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    items = (
        db.query(SrsItem)
        .join(Subject)
        .filter(SrsItem.user_id == current_user.id)
        .filter(SrsItem.incorrect_count >= 4)
        .filter(SrsItem.srs_stage.between(1, 8))
        .all()
    )
    leeches = []
    for item in items:
        total = item.correct_count + item.incorrect_count
        if total == 0:
            continue
        error_rate = round(item.incorrect_count / total * 100)
        if error_rate > 50:
            leeches.append({
                "subject_id": item.subject_id,
                "type": item.subject.type,
                "characters": item.subject.characters,
                "meanings": json.loads(item.subject.meanings),
                "srs_stage": item.srs_stage,
                "error_rate": error_rate,
                "correct_count": item.correct_count,
                "incorrect_count": item.incorrect_count,
            })
    leeches.sort(key=lambda x: x["error_rate"], reverse=True)
    return leeches[:limit]


@router.get("/recently-unlocked")
def get_recently_unlocked(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    cutoff = time.time() - 172800
    items = (
        db.query(SrsItem)
        .join(Subject)
        .filter(SrsItem.user_id == current_user.id)
        .filter(SrsItem.started_at != None, SrsItem.started_at >= cutoff)
        .order_by(SrsItem.started_at.desc())
        .limit(10)
        .all()
    )
    return [
        {
            "id": item.subject.id,
            "characters": item.subject.characters,
            "type": item.subject.type,
            "meanings": json.loads(item.subject.meanings),
            "srs_stage": item.srs_stage,
        }
        for item in items
    ]


@router.get("/level-history")
def get_level_history(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    events = db.query(LevelEvent).filter_by(user_id=current_user.id).order_by(LevelEvent.level.asc()).all()
    return [{"level": e.level, "reached_at": e.reached_at} for e in events]
