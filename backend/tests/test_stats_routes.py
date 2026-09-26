import json
import time
from backend.models import Subject, SrsItem


def _seed(db):
    db.add(Subject(id=1, type="radical", characters="一", slug="one", level=1, jlpt_level="N5",
                   meanings=json.dumps([{"meaning": "One", "primary": True}])))
    db.add(Subject(id=2, type="kanji", characters="大", slug="big", level=1, jlpt_level="N5",
                   meanings=json.dumps([{"meaning": "Big", "primary": True}])))
    db.add(Subject(id=3, type="kanji", characters="人", slug="person", level=11, jlpt_level="N4",
                   meanings=json.dumps([{"meaning": "Person", "primary": True}])))
    db.add(SrsItem(subject_id=1, srs_stage=0))
    db.add(SrsItem(subject_id=2, srs_stage=3, next_review_at=time.time() - 100))
    db.add(SrsItem(subject_id=3, srs_stage=9))
    db.commit()


def test_summary_counts(db, client):
    _seed(db)
    resp = client.get("/api/summary")
    assert resp.status_code == 200
    data = resp.json()
    assert data["reviews_available"] == 1
    assert data["lessons_available"] == 1


def test_summary_srs_stage_counts(db, client):
    _seed(db)
    resp = client.get("/api/summary")
    data = resp.json()
    counts = data["srs_stage_counts"]
    assert counts["0"] == 1
    assert counts["3"] == 1
    assert counts["9"] == 1


def test_summary_jlpt_progress(db, client):
    _seed(db)
    resp = client.get("/api/summary")
    data = resp.json()
    progress = data["jlpt_progress"]
    assert "N5" in progress
    assert progress["N5"]["total"] == 2
    assert progress["N5"]["burned"] == 0
    assert progress["N4"]["burned"] == 1
