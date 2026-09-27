from __future__ import annotations
import json
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from backend.database import get_db
from backend.models import Subject, SubjectDependency, SrsItem, UserSynonym

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
    }


@router.get("/subjects")
def list_subjects(
    jlpt: str | None = None,
    type: str | None = None,
    q: str | None = None,
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
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


@router.get("/subjects/{subject_id}")
def get_subject(subject_id: int, db: Session = Depends(get_db)):
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
    srs = db.query(SrsItem).filter_by(subject_id=subject_id).first()
    if srs:
        result["srs"] = {
            "srs_stage": srs.srs_stage,
            "correct_count": srs.correct_count,
            "incorrect_count": srs.incorrect_count,
            "next_review_at": srs.next_review_at,
        }
    synonyms = db.query(UserSynonym).filter_by(subject_id=subject_id).all()
    result["user_synonyms"] = [
        {"id": s.id, "meaning": s.meaning} for s in synonyms
    ]
    return result


class SynonymRequest(BaseModel):
    meaning: str


@router.get("/subjects/{subject_id}/synonyms")
def list_synonyms(subject_id: int, db: Session = Depends(get_db)):
    return [
        {"id": s.id, "subject_id": s.subject_id, "meaning": s.meaning}
        for s in db.query(UserSynonym).filter_by(subject_id=subject_id).all()
    ]


@router.post("/subjects/{subject_id}/synonyms")
def add_synonym(subject_id: int, req: SynonymRequest, db: Session = Depends(get_db)):
    subject = db.get(Subject, subject_id)
    if not subject:
        raise HTTPException(status_code=404, detail="Subject not found")
    existing = db.query(UserSynonym).filter_by(
        subject_id=subject_id, meaning=req.meaning
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail="Synonym already exists")
    syn = UserSynonym(subject_id=subject_id, meaning=req.meaning)
    db.add(syn)
    db.commit()
    db.refresh(syn)
    return {"id": syn.id, "subject_id": syn.subject_id, "meaning": syn.meaning}


@router.delete("/subjects/{subject_id}/synonyms/{synonym_id}")
def delete_synonym(subject_id: int, synonym_id: int, db: Session = Depends(get_db)):
    syn = db.query(UserSynonym).filter_by(id=synonym_id, subject_id=subject_id).first()
    if not syn:
        raise HTTPException(status_code=404, detail="Synonym not found")
    db.delete(syn)
    db.commit()
    return {"deleted": True}
