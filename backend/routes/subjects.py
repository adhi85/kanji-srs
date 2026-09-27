from __future__ import annotations
import json
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from backend.database import get_db
from backend.models import Subject, SubjectDependency, SrsItem, UserSynonym, User
from backend.auth import get_current_user

router = APIRouter()


def _subject_to_dict(s: Subject) -> dict:
    return {
        "id": s.id,
        "type": s.type,
        "characters": s.characters,
        "slug": s.slug,
        "level": s.level,
        "jlpt_level": s.jlpt_level,
        "meanings": json.loads(s.meanings),
        "readings": json.loads(s.readings) if s.readings else [],
        "meaning_mnemonic": s.meaning_mnemonic,
        "reading_mnemonic": s.reading_mnemonic,
        "part_of_speech": json.loads(s.part_of_speech) if s.part_of_speech else [],
        "context_sentences": json.loads(s.context_sentences) if s.context_sentences else [],
        "meaning_hint": s.meaning_hint,
        "reading_hint": s.reading_hint,
        "visually_similar_subject_ids": json.loads(s.visually_similar_subject_ids) if s.visually_similar_subject_ids else [],
        "character_image": s.character_image,
    }


@router.get("/subjects")
def list_subjects(
    jlpt: str | None = None,
    type: str | None = None,
    q: str | None = None,
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(Subject)
    if jlpt:
        query = query.filter(Subject.jlpt_level == jlpt)
    if type:
        query = query.filter(Subject.type == type)
    if q:
        q_lower = f"%{q.lower()}%"
        query = query.filter(
            (Subject.characters.ilike(q_lower)) | (Subject.meanings.ilike(q_lower))
        )
    total = query.count()
    items = query.order_by(Subject.level, Subject.id).offset((page - 1) * per_page).limit(per_page).all()
    return {"items": [_subject_to_dict(s) for s in items], "total": total, "page": page}


@router.get("/subjects/by-type/{item_type}")
def list_subjects_by_type(
    item_type: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    valid_types = ("radical", "kanji", "vocabulary", "kana_vocabulary")
    if item_type not in valid_types:
        raise HTTPException(status_code=400, detail=f"type must be one of {valid_types}")
    type_filter = [item_type]
    if item_type == "vocabulary":
        type_filter.append("kana_vocabulary")
    subjects = (
        db.query(Subject)
        .filter(Subject.type.in_(type_filter))
        .order_by(Subject.level, Subject.id)
        .all()
    )
    srs_map = {}
    if subjects:
        for srs in db.query(SrsItem).filter(
            SrsItem.user_id == current_user.id,
            SrsItem.subject_id.in_([s.id for s in subjects]),
        ).all():
            srs_map[srs.subject_id] = srs.srs_stage

    levels = {}
    for s in subjects:
        if s.level not in levels:
            levels[s.level] = []
        primary = next(
            (m["meaning"] for m in json.loads(s.meanings) if m.get("primary")),
            json.loads(s.meanings)[0]["meaning"] if s.meanings else "",
        )
        levels[s.level].append({
            "id": s.id,
            "characters": s.characters,
            "slug": s.slug,
            "type": s.type,
            "meanings": json.loads(s.meanings),
            "character_image": s.character_image,
            "srs_stage": srs_map.get(s.id, 0),
        })
    return {
        "type": item_type,
        "levels": [
            {"level": lvl, "items": items}
            for lvl, items in sorted(levels.items())
        ],
    }


@router.get("/subjects/{subject_id}")
def get_subject(subject_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    subject = db.get(Subject, subject_id)
    if not subject:
        raise HTTPException(status_code=404, detail="Subject not found")
    result = _subject_to_dict(subject)
    dep_ids = db.query(SubjectDependency.component_id).filter_by(subject_id=subject_id).all()
    components = [db.get(Subject, d[0]) for d in dep_ids]
    result["components"] = [_subject_to_dict(c) for c in components if c]
    used_in_rows = (
        db.query(Subject)
        .join(SubjectDependency, SubjectDependency.subject_id == Subject.id)
        .filter(SubjectDependency.component_id == subject_id)
        .all()
    )
    result["used_in"] = [_subject_to_dict(s) for s in used_in_rows]
    vis_sim_ids = json.loads(subject.visually_similar_subject_ids) if subject.visually_similar_subject_ids else []
    vis_similar = []
    for vid in vis_sim_ids:
        vs = db.get(Subject, vid)
        if vs:
            vis_similar.append({
                "id": vs.id, "characters": vs.characters, "type": vs.type,
                "meanings": json.loads(vs.meanings),
            })
    result["visually_similar"] = vis_similar
    srs = db.query(SrsItem).filter_by(user_id=current_user.id, subject_id=subject_id).first()
    if srs:
        result["srs"] = {
            "srs_stage": srs.srs_stage,
            "correct_count": srs.correct_count,
            "incorrect_count": srs.incorrect_count,
            "next_review_at": srs.next_review_at,
        }
    synonyms = db.query(UserSynonym).filter_by(user_id=current_user.id, subject_id=subject_id).all()
    result["user_synonyms"] = [
        {"id": s.id, "meaning": s.meaning} for s in synonyms
    ]
    return result


class SynonymRequest(BaseModel):
    meaning: str


@router.get("/subjects/{subject_id}/synonyms")
def list_synonyms(subject_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return [
        {"id": s.id, "subject_id": s.subject_id, "meaning": s.meaning}
        for s in db.query(UserSynonym).filter_by(user_id=current_user.id, subject_id=subject_id).all()
    ]


@router.post("/subjects/{subject_id}/synonyms")
def add_synonym(subject_id: int, req: SynonymRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    subject = db.get(Subject, subject_id)
    if not subject:
        raise HTTPException(status_code=404, detail="Subject not found")
    existing = db.query(UserSynonym).filter_by(
        user_id=current_user.id, subject_id=subject_id, meaning=req.meaning
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail="Synonym already exists")
    syn = UserSynonym(user_id=current_user.id, subject_id=subject_id, meaning=req.meaning)
    db.add(syn)
    db.commit()
    db.refresh(syn)
    return {"id": syn.id, "subject_id": syn.subject_id, "meaning": syn.meaning}


@router.post("/subjects/{subject_id}/reset")
def reset_subject(subject_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    item = db.query(SrsItem).filter_by(user_id=current_user.id, subject_id=subject_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="SRS item not found")
    if item.srs_stage < 1:
        raise HTTPException(status_code=400, detail="Item is not started")
    item.srs_stage = 0
    item.started_at = None
    item.next_review_at = None
    item.correct_count = 0
    item.incorrect_count = 0
    item.meaning_correct_in_session = 0
    item.reading_correct_in_session = 0
    item.incorrect_in_session = 0
    db.commit()
    return {"srs_stage": 0, "correct_count": 0, "incorrect_count": 0}


@router.post("/subjects/{subject_id}/resurrect")
def resurrect_subject(subject_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    import time as _time
    item = db.query(SrsItem).filter_by(user_id=current_user.id, subject_id=subject_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="SRS item not found")
    if item.srs_stage != 9:
        raise HTTPException(status_code=400, detail="Only burned items can be resurrected")
    item.srs_stage = 1
    item.next_review_at = _time.time()
    item.meaning_correct_in_session = 0
    item.reading_correct_in_session = 0
    item.incorrect_in_session = 0
    db.commit()
    return {
        "srs_stage": 1,
        "correct_count": item.correct_count,
        "incorrect_count": item.incorrect_count,
    }


@router.delete("/subjects/{subject_id}/synonyms/{synonym_id}")
def delete_synonym(subject_id: int, synonym_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    syn = db.query(UserSynonym).filter_by(id=synonym_id, user_id=current_user.id, subject_id=subject_id).first()
    if not syn:
        raise HTTPException(status_code=404, detail="Synonym not found")
    db.delete(syn)
    db.commit()
    return {"deleted": True}
