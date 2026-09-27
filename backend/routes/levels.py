import json

from fastapi import APIRouter, Depends
from sqlalchemy import case, func
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models import Subject, SrsItem, User
from backend.auth import get_current_user

router = APIRouter()


def compute_current_level(db: Session, user_id: int) -> int:
    rows = (
        db.query(
            Subject.level,
            func.count(Subject.id).label("total"),
            func.sum(case((SrsItem.srs_stage >= 5, 1), else_=0)).label("passed"),
        )
        .outerjoin(SrsItem, (SrsItem.subject_id == Subject.id) & (SrsItem.user_id == user_id))
        .filter(Subject.type == "kanji")
        .group_by(Subject.level)
        .all()
    )
    level_map = {r.level: (r.total, r.passed or 0) for r in rows}
    current = 1
    for lvl in range(1, 61):
        if lvl not in level_map:
            break
        total, passed = level_map[lvl]
        if total > 0 and passed / total >= 0.9:
            current = lvl + 1
        else:
            break
    return min(current, 60)


@router.get("/levels")
def get_levels(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    current = compute_current_level(db, current_user.id)
    rows = (
        db.query(
            Subject.level,
            Subject.type,
            func.count(Subject.id).label("count"),
            func.sum(case((SrsItem.srs_stage >= 5, 1), else_=0)).label("passed"),
        )
        .outerjoin(SrsItem, (SrsItem.subject_id == Subject.id) & (SrsItem.user_id == current_user.id))
        .group_by(Subject.level, Subject.type)
        .all()
    )
    levels = {}
    for row in rows:
        lvl = row.level
        if lvl not in levels:
            levels[lvl] = {
                "level": lvl,
                "radical_count": 0, "kanji_count": 0, "vocab_count": 0,
                "radical_passed": 0, "kanji_passed": 0, "vocab_passed": 0,
            }
        key = "radical" if row.type == "radical" else "kanji" if row.type == "kanji" else "vocab"
        levels[lvl][f"{key}_count"] = row.count
        levels[lvl][f"{key}_passed"] = row.passed or 0
    return {
        "current_level": current,
        "levels": sorted(levels.values(), key=lambda x: x["level"]),
    }


@router.get("/levels/{level}")
def get_level_detail(level: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    subjects = (
        db.query(Subject)
        .filter(Subject.level == level)
        .all()
    )
    srs_map = {
        item.subject_id: item.srs_stage
        for item in db.query(SrsItem).filter(
            SrsItem.user_id == current_user.id,
            SrsItem.subject_id.in_([s.id for s in subjects])
        ).all()
    } if subjects else {}
    result = {"level": level, "radicals": [], "kanji": [], "vocabulary": []}
    for s in subjects:
        item = {
            "id": s.id,
            "characters": s.characters,
            "type": s.type,
            "meanings": json.loads(s.meanings) if s.meanings else [],
            "srs_stage": srs_map.get(s.id, 0),
        }
        if s.type == "radical":
            result["radicals"].append(item)
        elif s.type == "kanji":
            result["kanji"].append(item)
        else:
            result["vocabulary"].append(item)
    return result
