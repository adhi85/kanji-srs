import json
from backend.models import Subject, SrsItem


def _seed(db):
    db.add(Subject(id=1, type="kanji", characters="大", slug="big", level=1,
                   meanings=json.dumps([{"meaning": "Big", "primary": True}])))
    db.add(SrsItem(subject_id=1, srs_stage=0))
    db.commit()


def test_add_synonym(db, client):
    _seed(db)
    resp = client.post("/api/subjects/1/synonyms", json={"meaning": "Huge"})
    assert resp.status_code == 200
    assert resp.json()["meaning"] == "Huge"


def test_list_synonyms(db, client):
    _seed(db)
    client.post("/api/subjects/1/synonyms", json={"meaning": "Huge"})
    client.post("/api/subjects/1/synonyms", json={"meaning": "Large"})
    resp = client.get("/api/subjects/1/synonyms")
    assert resp.status_code == 200
    assert len(resp.json()) == 2


def test_delete_synonym(db, client):
    _seed(db)
    resp = client.post("/api/subjects/1/synonyms", json={"meaning": "Huge"})
    syn_id = resp.json()["id"]
    del_resp = client.delete(f"/api/subjects/1/synonyms/{syn_id}")
    assert del_resp.status_code == 200
    list_resp = client.get("/api/subjects/1/synonyms")
    assert len(list_resp.json()) == 0


def test_duplicate_synonym_returns_409(db, client):
    _seed(db)
    client.post("/api/subjects/1/synonyms", json={"meaning": "Huge"})
    resp = client.post("/api/subjects/1/synonyms", json={"meaning": "Huge"})
    assert resp.status_code == 409
