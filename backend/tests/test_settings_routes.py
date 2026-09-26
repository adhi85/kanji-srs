import json
from backend.models import Setting


def _seed(db):
    defaults = {
        "srs_intervals": [0, 14400, 28800, 82800, 169200, 601200, 1206000, 2588400, 10364400, 0],
        "lesson_batch_size": 5,
        "jlpt_gating": True,
        "dependency_gating": True,
        "max_reviews_per_session": None,
    }
    for k, v in defaults.items():
        db.add(Setting(key=k, value=json.dumps(v)))
    db.commit()


def test_get_settings(db, client):
    _seed(db)
    resp = client.get("/api/settings")
    assert resp.status_code == 200
    data = resp.json()
    assert data["lesson_batch_size"] == 5
    assert data["jlpt_gating"] is True


def test_update_setting(db, client):
    _seed(db)
    resp = client.put("/api/settings", json={"lesson_batch_size": 10})
    assert resp.status_code == 200
    resp = client.get("/api/settings")
    assert resp.json()["lesson_batch_size"] == 10
