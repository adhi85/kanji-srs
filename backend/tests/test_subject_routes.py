import json
from backend.models import Subject, SubjectDependency, SrsItem


def _seed(db):
    subjects = [
        Subject(id=1, type="radical", characters="一", slug="one", level=1, jlpt_level="N5",
                meanings=json.dumps([{"meaning": "One", "primary": True}])),
        Subject(id=2, type="kanji", characters="大", slug="big", level=1, jlpt_level="N5",
                meanings=json.dumps([{"meaning": "Big", "primary": True}]),
                readings=json.dumps([{"reading": "たい", "primary": True, "type": "onyomi"}])),
        Subject(id=3, type="kanji", characters="人", slug="person", level=2, jlpt_level="N5",
                meanings=json.dumps([{"meaning": "Person", "primary": True}]),
                readings=json.dumps([{"reading": "じん", "primary": True, "type": "onyomi"}])),
        Subject(id=4, type="vocabulary", characters="大人", slug="adult", level=3, jlpt_level="N5",
                meanings=json.dumps([{"meaning": "Adult", "primary": True}]),
                readings=json.dumps([{"reading": "おとな", "primary": True, "type": "kunyomi"}])),
    ]
    db.add_all(subjects)
    db.add(SubjectDependency(subject_id=2, component_id=1))
    for s in subjects:
        db.add(SrsItem(subject_id=s.id))
    db.commit()


def test_list_subjects(db, client):
    _seed(db)
    resp = client.get("/api/subjects")
    assert resp.status_code == 200
    assert len(resp.json()["items"]) == 4


def test_filter_by_jlpt(db, client):
    _seed(db)
    resp = client.get("/api/subjects?jlpt=N5")
    assert resp.status_code == 200
    assert len(resp.json()["items"]) == 4


def test_filter_by_type(db, client):
    _seed(db)
    resp = client.get("/api/subjects?type=kanji")
    assert resp.status_code == 200
    assert len(resp.json()["items"]) == 2


def test_search_by_query(db, client):
    _seed(db)
    resp = client.get("/api/subjects?q=big")
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert any(i["characters"] == "大" for i in items)


def test_get_subject_detail(db, client):
    _seed(db)
    resp = client.get("/api/subjects/2")
    assert resp.status_code == 200
    data = resp.json()
    assert data["characters"] == "大"
    assert len(data["components"]) == 1
    assert data["components"][0]["characters"] == "一"


def test_subject_detail_includes_used_in(db, client):
    _seed(db)
    resp = client.get("/api/subjects/1")
    data = resp.json()
    assert "used_in" in data
    assert len(data["used_in"]) == 1
    assert data["used_in"][0]["id"] == 2
    assert data["used_in"][0]["characters"] == "大"


def test_subject_detail_includes_visually_similar(db, client):
    db.add(Subject(id=10, type="kanji", characters="大", slug="big2", level=1, jlpt_level="N5",
                   meanings=json.dumps([{"meaning": "Big", "primary": True}]),
                   readings=json.dumps([{"reading": "たい", "primary": True}]),
                   visually_similar_subject_ids=json.dumps([11])))
    db.add(Subject(id=11, type="kanji", characters="太", slug="fat", level=1, jlpt_level="N5",
                   meanings=json.dumps([{"meaning": "Fat", "primary": True}]),
                   readings=json.dumps([{"reading": "ふと", "primary": True}])))
    db.add(SrsItem(subject_id=10))
    db.add(SrsItem(subject_id=11))
    db.commit()

    resp = client.get("/api/subjects/10")
    data = resp.json()
    assert "visually_similar" in data
    assert len(data["visually_similar"]) == 1
    assert data["visually_similar"][0]["characters"] == "太"
