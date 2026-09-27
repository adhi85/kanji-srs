import json
import time
from backend.models import Subject, SrsItem, LevelEvent


def test_recently_unlocked(db, client, test_user):
    db.add(Subject(id=1, type="kanji", characters="大", slug="big", level=1, jlpt_level="N5",
                   meanings=json.dumps([{"meaning": "Big", "primary": True}])))
    db.add(SrsItem(user_id=test_user.id, subject_id=1, srs_stage=1, started_at=time.time() - 100))
    db.commit()

    resp = client.get("/api/recently-unlocked")
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) == 1
    assert items[0]["characters"] == "大"


def test_recently_unlocked_excludes_old(db, client, test_user):
    db.add(Subject(id=1, type="kanji", characters="大", slug="big", level=1, jlpt_level="N5",
                   meanings=json.dumps([{"meaning": "Big", "primary": True}])))
    db.add(SrsItem(user_id=test_user.id, subject_id=1, srs_stage=1, started_at=time.time() - 200000))
    db.commit()

    resp = client.get("/api/recently-unlocked")
    assert len(resp.json()) == 0


def test_level_history_empty(db, client):
    resp = client.get("/api/level-history")
    assert resp.status_code == 200
    assert resp.json() == []


def test_level_history_returns_events(db, client, test_user):
    db.add(LevelEvent(user_id=test_user.id, level=1, reached_at=1000000.0))
    db.add(LevelEvent(user_id=test_user.id, level=2, reached_at=2000000.0))
    db.commit()

    resp = client.get("/api/level-history")
    data = resp.json()
    assert len(data) == 2
    assert data[0]["level"] == 1
    assert data[1]["level"] == 2
