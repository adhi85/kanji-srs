import json
import time
from backend.models import Subject, SrsItem


def _seed_forecast(db, user):
    now = time.time()
    for i in range(1, 6):
        db.add(Subject(id=i, type="kanji", characters=f"字{i}", slug=f"char{i}", level=1,
                       meanings=json.dumps([{"meaning": f"Char{i}", "primary": True}])))
    db.add(SrsItem(user_id=user.id, subject_id=1, srs_stage=2, next_review_at=now + 1800))
    db.add(SrsItem(user_id=user.id, subject_id=2, srs_stage=3, next_review_at=now + 3000))
    db.add(SrsItem(user_id=user.id, subject_id=3, srs_stage=4, next_review_at=now + 18000))
    db.add(SrsItem(user_id=user.id, subject_id=4, srs_stage=6, next_review_at=now + 90000))
    db.add(SrsItem(user_id=user.id, subject_id=5, srs_stage=9))
    db.commit()


def test_forecast_returns_hourly_and_daily(db, client, test_user):
    _seed_forecast(db, test_user)
    resp = client.get("/api/forecast")
    assert resp.status_code == 200
    data = resp.json()
    assert "next_24h" in data
    assert "next_5_days" in data
    assert isinstance(data["next_24h"], list)
    assert isinstance(data["next_5_days"], list)


def test_forecast_hourly_counts(db, client, test_user):
    _seed_forecast(db, test_user)
    resp = client.get("/api/forecast")
    data = resp.json()
    total_24h = sum(h["count"] for h in data["next_24h"])
    assert total_24h >= 3


def test_forecast_daily_counts(db, client, test_user):
    _seed_forecast(db, test_user)
    resp = client.get("/api/forecast")
    data = resp.json()
    total_5d = sum(d["count"] for d in data["next_5_days"])
    assert total_5d >= 4


def test_forecast_empty_when_no_reviews(db, client):
    resp = client.get("/api/forecast")
    data = resp.json()
    assert sum(h["count"] for h in data["next_24h"]) == 0
