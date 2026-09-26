import json

from fastapi import APIRouter, Depends
from sqlalchemy import case, func
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models import Subject, SrsItem

router = APIRouter()


def compute_current_level(db: Session) -> int:
    rows = (
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
def get_levels(db: Session = Depends(get_db)):
    current = compute_current_level(db)
    rows = (
        db.query(
            Subject.level,
            Subject.type,
            func.count(Subject.id).label("count"),
            func.sum(case((SrsItem.srs_stage >= 5, 1), else_=0)).label("passed"),
        )
        .outerjoin(SrsItem)
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
def get_level_detail(level: int, db: Session = Depends(get_db)):
    subjects = (
        db.query(Subject)
        .outerjoin(SrsItem)
        .filter(Subject.level == level)
        .all()
    )
    result = {"level": level, "radicals": [], "kanji": [], "vocabulary": []}
    for s in subjects:
        item = {
            "id": s.id,
            "characters": s.characters,
            "type": s.type,
            "meanings": json.loads(s.meanings) if s.meanings else [],
            "srs_stage": s.srs_item.srs_stage if s.srs_item else 0,
        }
        if s.type == "radical":
            result["radicals"].append(item)
        elif s.type == "kanji":
            result["kanji"].append(item)
        else:
            result["vocabulary"].append(item)
    return result
