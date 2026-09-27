import json
from backend.models import Subject, SrsItem


def _seed(db, user):
    db.add(Subject(id=1, type="kanji", characters="難", slug="difficult", level=10,
                   meanings=json.dumps([{"meaning": "Difficult", "primary": True}])))
    db.add(SrsItem(user_id=user.id, subject_id=1, srs_stage=3, correct_count=3, incorrect_count=7))
    db.add(Subject(id=2, type="kanji", characters="大", slug="big", level=1,
                   meanings=json.dumps([{"meaning": "Big", "primary": True}])))
    db.add(SrsItem(user_id=user.id, subject_id=2, srs_stage=7, correct_count=20, incorrect_count=1))
    db.add(Subject(id=3, type="radical", characters="一", slug="one", level=1,
                   meanings=json.dumps([{"meaning": "One", "primary": True}])))
    db.add(SrsItem(user_id=user.id, subject_id=3, srs_stage=2, correct_count=1, incorrect_count=2))
    db.commit()


def test_critical_items_returns_leeches(db, client, test_user):
    _seed(db, test_user)
    resp = client.get("/api/critical-items")
    assert resp.status_code == 200
    items = resp.json()
    ids = [i["subject_id"] for i in items]
    assert 1 in ids
    assert 2 not in ids
    assert 3 not in ids


def test_critical_items_includes_error_rate(db, client, test_user):
    _seed(db, test_user)
    resp = client.get("/api/critical-items")
    items = resp.json()
    leech = next(i for i in items if i["subject_id"] == 1)
    assert leech["error_rate"] == 70


def test_critical_items_sorted_by_error_rate(db, client, test_user):
    _seed(db, test_user)
    db.add(Subject(id=4, type="kanji", characters="悪", slug="bad", level=10,
                   meanings=json.dumps([{"meaning": "Bad", "primary": True}])))
    db.add(SrsItem(user_id=test_user.id, subject_id=4, srs_stage=2, correct_count=1, incorrect_count=9))
    db.commit()
    resp = client.get("/api/critical-items")
    items = resp.json()
    assert items[0]["subject_id"] == 4
    assert items[1]["subject_id"] == 1


def test_critical_items_respects_limit(db, client, test_user):
    _seed(db, test_user)
    resp = client.get("/api/critical-items?limit=0")
    assert resp.json() == []


def test_critical_items_empty_when_no_leeches(db, client):
    resp = client.get("/api/critical-items")
    assert resp.json() == []
