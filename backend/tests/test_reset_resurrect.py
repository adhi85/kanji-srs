import json
import time
from backend.models import Subject, SrsItem


def _seed(db, user):
    db.add(Subject(id=1, type="kanji", characters="大", slug="big", level=1, jlpt_level="N5",
                   meanings=json.dumps([{"meaning": "Big", "primary": True}]),
                   readings=json.dumps([{"reading": "たい", "primary": True}])))
    db.add(SrsItem(user_id=user.id, subject_id=1, srs_stage=5, started_at=1000.0,
                   next_review_at=time.time() + 3600,
                   correct_count=10, incorrect_count=3))
    db.commit()


def test_reset_subject(db, client, test_user):
    _seed(db, test_user)
    resp = client.post("/api/subjects/1/reset")
    assert resp.status_code == 200
    data = resp.json()
    assert data["srs_stage"] == 0
    assert data["correct_count"] == 0

    item = db.query(SrsItem).filter_by(subject_id=1).first()
    assert item.srs_stage == 0
    assert item.started_at is None
    assert item.next_review_at is None


def test_reset_rejects_stage_0(db, client, test_user):
    db.add(Subject(id=2, type="radical", characters="r", slug="r", level=1,
                   meanings=json.dumps([{"meaning": "R", "primary": True}])))
    db.add(SrsItem(user_id=test_user.id, subject_id=2, srs_stage=0))
    db.commit()
    resp = client.post("/api/subjects/2/reset")
    assert resp.status_code == 400


def test_resurrect_burned_item(db, client, test_user):
    db.add(Subject(id=3, type="kanji", characters="火", slug="fire", level=1,
                   meanings=json.dumps([{"meaning": "Fire", "primary": True}]),
                   readings=json.dumps([{"reading": "ひ", "primary": True}])))
    db.add(SrsItem(user_id=test_user.id, subject_id=3, srs_stage=9, started_at=1000.0,
                   correct_count=20, incorrect_count=5))
    db.commit()

    resp = client.post("/api/subjects/3/resurrect")
    assert resp.status_code == 200
    data = resp.json()
    assert data["srs_stage"] == 1
    assert data["correct_count"] == 20

    item = db.query(SrsItem).filter_by(subject_id=3).first()
    assert item.srs_stage == 1
    assert item.next_review_at is not None


def test_resurrect_rejects_non_burned(db, client, test_user):
    _seed(db, test_user)
    resp = client.post("/api/subjects/1/resurrect")
    assert resp.status_code == 400
