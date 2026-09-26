import json


def _seed_level(db, level, num_kanji=3, num_radical=1, num_vocab=2):
    from backend.models import Subject, SrsItem
    ids = []
    counter = level * 100
    for i in range(num_radical):
        counter += 1
        s = Subject(id=counter, type="radical", characters=None, slug=f"r-{counter}",
                    level=level, meanings=json.dumps([{"meaning": f"Rad{counter}", "primary": True}]))
        db.add(s)
        db.flush()
        db.add(SrsItem(subject_id=s.id, srs_stage=0))
        ids.append(s.id)
    for i in range(num_kanji):
        counter += 1
        s = Subject(id=counter, type="kanji", characters=f"K{counter}",
                    level=level, meanings=json.dumps([{"meaning": f"Kanji{counter}", "primary": True}]),
                    readings=json.dumps([{"reading": "か", "primary": True}]))
        db.add(s)
        db.flush()
        db.add(SrsItem(subject_id=s.id, srs_stage=0))
        ids.append(s.id)
    for i in range(num_vocab):
        counter += 1
        s = Subject(id=counter, type="vocabulary", characters=f"V{counter}",
                    level=level, meanings=json.dumps([{"meaning": f"Vocab{counter}", "primary": True}]),
                    readings=json.dumps([{"reading": "か", "primary": True}]))
        db.add(s)
        db.flush()
        db.add(SrsItem(subject_id=s.id, srs_stage=0))
        ids.append(s.id)
    db.commit()
    return ids


def test_get_levels_empty(client):
    resp = client.get("/api/levels")
    assert resp.status_code == 200
    data = resp.json()
    assert data["current_level"] == 1
    assert data["levels"] == []


def test_get_levels_with_data(client, db):
    _seed_level(db, 1)
    _seed_level(db, 2)
    resp = client.get("/api/levels")
    data = resp.json()
    assert data["current_level"] == 1
    assert len(data["levels"]) == 2
    lvl1 = data["levels"][0]
    assert lvl1["level"] == 1
    assert lvl1["radical_count"] == 1
    assert lvl1["kanji_count"] == 3
    assert lvl1["vocab_count"] == 2


def test_current_level_advances(client, db):
    from backend.models import SrsItem
    _seed_level(db, 1, num_kanji=3)
    _seed_level(db, 2, num_kanji=3)
    kanji_items = db.query(SrsItem).join(SrsItem.subject).filter(
        SrsItem.subject.has(type="kanji", level=1)).all()
    for item in kanji_items:
        item.srs_stage = 5
    db.commit()
    resp = client.get("/api/levels")
    assert resp.json()["current_level"] == 2


def test_get_level_detail(client, db):
    _seed_level(db, 1)
    resp = client.get("/api/levels/1")
    assert resp.status_code == 200
    data = resp.json()
    assert data["level"] == 1
    assert len(data["radicals"]) == 1
    assert len(data["kanji"]) == 3
    assert len(data["vocabulary"]) == 2
    assert "id" in data["kanji"][0]
    assert "characters" in data["kanji"][0]
    assert "meanings" in data["kanji"][0]
    assert "srs_stage" in data["kanji"][0]


def test_get_level_detail_empty(client):
    resp = client.get("/api/levels/99")
    assert resp.status_code == 200
    data = resp.json()
    assert data["radicals"] == []
    assert data["kanji"] == []
    assert data["vocabulary"] == []
