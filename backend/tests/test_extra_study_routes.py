import json
import time
from backend.models import Subject, SrsItem


def _seed(db, user):
    db.add(Subject(id=1, type="kanji", characters="大", slug="big", level=1,
                   meanings=json.dumps([{"meaning": "Big", "primary": True}]),
                   readings=json.dumps([{"reading": "たい", "primary": True}]),
                   meaning_mnemonic="A person stretching wide."))
    db.add(SrsItem(user_id=user.id, subject_id=1, srs_stage=2, incorrect_count=3,
                   last_incorrect_at=time.time() - 3600,
                   next_review_at=time.time() + 86400))
    db.add(Subject(id=2, type="radical", characters="二", slug="two", level=1,
                   meanings=json.dumps([{"meaning": "Two", "primary": True}])))
    db.add(SrsItem(user_id=user.id, subject_id=2, srs_stage=1, started_at=time.time() - 1800))
    db.add(Subject(id=3, type="kanji", characters="人", slug="person", level=1,
                   meanings=json.dumps([{"meaning": "Person", "primary": True}]),
                   readings=json.dumps([{"reading": "じん", "primary": True}])))
    db.add(SrsItem(user_id=user.id, subject_id=3, srs_stage=9, correct_count=20, incorrect_count=2))
    db.add(Subject(id=4, type="radical", characters="三", slug="three", level=1,
                   meanings=json.dumps([{"meaning": "Three", "primary": True}])))
    db.add(SrsItem(user_id=user.id, subject_id=4, srs_stage=5, incorrect_count=1,
                   last_incorrect_at=time.time() - 100000))
    db.commit()


def test_recent_mistakes_returns_recent_only(db, client, test_user):
    _seed(db, test_user)
    resp = client.get("/api/extra-study?mode=recent_mistakes")
    assert resp.status_code == 200
    items = resp.json()
    ids = [i["subject_id"] for i in items]
    assert 1 in ids
    assert 4 not in ids


def test_recent_lessons_returns_recently_started(db, client, test_user):
    _seed(db, test_user)
    resp = client.get("/api/extra-study?mode=recent_lessons")
    assert resp.status_code == 200
    items = resp.json()
    ids = [i["subject_id"] for i in items]
    assert 2 in ids


def test_burned_returns_stage_9(db, client, test_user):
    _seed(db, test_user)
    resp = client.get("/api/extra-study?mode=burned")
    assert resp.status_code == 200
    items = resp.json()
    ids = [i["subject_id"] for i in items]
    assert 3 in ids
    assert 1 not in ids


def test_extra_study_submit_does_not_change_srs(db, client, test_user):
    _seed(db, test_user)
    original_stage = db.query(SrsItem).filter_by(subject_id=1).first().srs_stage
    resp = client.post("/api/extra-study/1",
                       json={"answer_type": "meaning", "answer": "wrong answer"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["correct"] is False
    db.expire_all()
    after_stage = db.query(SrsItem).filter_by(subject_id=1).first().srs_stage
    assert after_stage == original_stage


def test_extra_study_correct_answer(db, client, test_user):
    _seed(db, test_user)
    resp = client.post("/api/extra-study/1",
                       json={"answer_type": "meaning", "answer": "big"})
    assert resp.status_code == 200
    assert resp.json()["correct"] is True


def test_extra_study_summary(db, client, test_user):
    _seed(db, test_user)
    resp = client.get("/api/extra-study/summary")
    assert resp.status_code == 200
    data = resp.json()
    assert data["recent_mistakes"] >= 1
    assert data["recent_lessons"] >= 1
    assert data["burned"] >= 1


def test_invalid_mode_returns_400(db, client, test_user):
    _seed(db, test_user)
    resp = client.get("/api/extra-study?mode=invalid")
    assert resp.status_code == 400
