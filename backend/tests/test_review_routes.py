import json
import time
from backend.models import Subject, SrsItem, Setting
from backend.srs_engine import DEFAULT_INTERVALS


def _seed(db):
    s = Subject(id=1, type="kanji", characters="大", slug="big", level=1, jlpt_level="N5",
                meanings=json.dumps([{"meaning": "Big", "primary": True}]),
                readings=json.dumps([{"reading": "たい", "primary": True, "type": "onyomi"}]),
                meaning_mnemonic="A person stretching wide.")
    db.add(s)
    item = SrsItem(subject_id=1, srs_stage=2, next_review_at=time.time() - 100)
    db.add(item)
    db.add(Setting(key="srs_intervals", value=json.dumps(DEFAULT_INTERVALS)))
    db.commit()


def test_get_reviews_returns_due_items(db, client):
    _seed(db)
    resp = client.get("/api/reviews")
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) == 1
    assert items[0]["characters"] == "大"


def test_correct_meaning_answer(db, client):
    _seed(db)
    resp = client.post("/api/reviews/1", json={"answer_type": "meaning", "answer": "big"})
    assert resp.status_code == 200
    assert resp.json()["correct"] is True


def test_wrong_meaning_answer(db, client):
    _seed(db)
    resp = client.post("/api/reviews/1", json={"answer_type": "meaning", "answer": "small"})
    assert resp.status_code == 200
    assert resp.json()["correct"] is False
    assert resp.json()["correct_answer"] is not None


def test_correct_reading_answer(db, client):
    _seed(db)
    resp = client.post("/api/reviews/1", json={"answer_type": "reading", "answer": "たい"})
    assert resp.status_code == 200
    assert resp.json()["correct"] is True


def test_both_correct_advances_stage(db, client):
    _seed(db)
    client.post("/api/reviews/1", json={"answer_type": "meaning", "answer": "big"})
    resp = client.post("/api/reviews/1", json={"answer_type": "reading", "answer": "たい"})
    assert resp.json()["new_stage"] == 3


def test_one_wrong_retreats_stage(db, client):
    _seed(db)
    client.post("/api/reviews/1", json={"answer_type": "meaning", "answer": "wrong"})
    resp = client.post("/api/reviews/1", json={"answer_type": "reading", "answer": "たい"})
    assert resp.json()["new_stage"] == 1


def _seed_with_kunyomi(db):
    s = Subject(id=2, type="kanji", characters="一", slug="one", level=1, jlpt_level="N5",
                meanings=json.dumps([{"meaning": "One", "primary": True}]),
                readings=json.dumps([
                    {"reading": "いち", "primary": True, "accepted_answer": True, "type": "onyomi"},
                    {"reading": "ひと", "primary": False, "accepted_answer": False, "type": "kunyomi"},
                ]),
                meaning_mnemonic="The number one.")
    db.add(s)
    item = SrsItem(subject_id=2, srs_stage=2, next_review_at=time.time() - 100)
    db.add(item)
    db.add(Setting(key="srs_intervals", value=json.dumps(DEFAULT_INTERVALS)))
    db.commit()


def test_reading_hint_for_kunyomi(db, client):
    _seed_with_kunyomi(db)
    resp = client.post("/api/reviews/2", json={"answer_type": "reading", "answer": "ひと"})
    data = resp.json()
    assert data["correct"] is False
    assert data.get("retry") is True
    assert "onyomi" in data["hint"]
    srs_item = db.query(SrsItem).filter_by(subject_id=2).first()
    assert srs_item.srs_stage == 2
    assert srs_item.incorrect_count == 0


def test_double_wrong_only_drops_once(db, client):
    s = Subject(id=10, type="kanji", characters="火", slug="fire", level=1, jlpt_level="N5",
                meanings=json.dumps([{"meaning": "Fire", "primary": True}]),
                readings=json.dumps([{"reading": "ひ", "primary": True, "type": "kunyomi"}]),
                meaning_mnemonic="Flames.")
    db.add(s)
    db.add(SrsItem(subject_id=10, srs_stage=5, next_review_at=time.time() - 100))
    db.add(Setting(key="srs_intervals", value=json.dumps(DEFAULT_INTERVALS)))
    db.commit()

    resp1 = client.post("/api/reviews/10", json={"answer_type": "meaning", "answer": "water"})
    assert resp1.json()["correct"] is False
    assert resp1.json()["new_stage"] == 3

    resp2 = client.post("/api/reviews/10", json={"answer_type": "reading", "answer": "か"})
    assert resp2.json()["correct"] is False
    assert resp2.json()["new_stage"] == 3


def test_reading_no_hint_for_wrong_answer(db, client):
    _seed_with_kunyomi(db)
    resp = client.post("/api/reviews/2", json={"answer_type": "reading", "answer": "かん"})
    data = resp.json()
    assert data["correct"] is False
    assert data.get("retry") is not True
