import json
from backend.models import Subject, SrsItem, Setting, SubjectDependency
from backend.srs_engine import DEFAULT_INTERVALS


def _seed(db):
    for i in range(1, 11):
        db.add(Subject(id=i, type="kanji", characters=chr(0x5B57 + i), slug="char{}".format(i), level=1,
                       jlpt_level="N5",
                       meanings=json.dumps([{"meaning": "Char{}".format(i), "primary": True}]),
                       readings=json.dumps([{"reading": "じ", "primary": True, "type": "onyomi"}])))
        db.add(SrsItem(subject_id=i, srs_stage=0))
    db.add(Setting(key="lesson_batch_size", value=json.dumps(5)))
    db.add(Setting(key="jlpt_gating", value=json.dumps(False)))
    db.add(Setting(key="dependency_gating", value=json.dumps(False)))
    db.add(Setting(key="srs_intervals", value=json.dumps([0, 14400, 28800, 82800, 169200, 601200, 1206000, 2588400, 10364400, 0])))
    db.commit()


def test_get_lessons_returns_batch(db, client):
    _seed(db)
    resp = client.get("/api/lessons")
    assert resp.status_code == 200
    assert len(resp.json()) == 5


def test_start_lessons_moves_to_stage_1(db, client):
    _seed(db)
    resp = client.get("/api/lessons")
    ids = [item["id"] for item in resp.json()]
    resp = client.post("/api/lessons/start", json={"subject_ids": ids})
    assert resp.status_code == 200
    assert resp.json()["started"] == 5

    resp = client.get("/api/lessons")
    new_ids = [item["id"] for item in resp.json()]
    assert not any(i in new_ids for i in ids)


def test_dependency_gating_filters_unguru_components(db, client):
    db.add(Subject(id=100, type="radical", characters="r", slug="r", level=1, jlpt_level="N5",
                   meanings=json.dumps([{"meaning": "R", "primary": True}])))
    db.add(SrsItem(subject_id=100, srs_stage=2))

    db.add(Subject(id=101, type="kanji", characters="k", slug="k", level=1, jlpt_level="N5",
                   meanings=json.dumps([{"meaning": "K", "primary": True}]),
                   readings=json.dumps([{"reading": "か", "primary": True}])))
    db.add(SrsItem(subject_id=101, srs_stage=0))
    db.add(SubjectDependency(subject_id=101, component_id=100))

    db.add(Subject(id=102, type="radical", characters="s", slug="s", level=1, jlpt_level="N5",
                   meanings=json.dumps([{"meaning": "S", "primary": True}])))
    db.add(SrsItem(subject_id=102, srs_stage=0))

    db.add(Setting(key="lesson_batch_size", value=json.dumps(10)))
    db.add(Setting(key="dependency_gating", value=json.dumps(True)))
    db.add(Setting(key="jlpt_gating", value=json.dumps(False)))
    db.add(Setting(key="srs_intervals", value=json.dumps(DEFAULT_INTERVALS)))
    db.commit()

    resp = client.get("/api/lessons")
    ids = [item["id"] for item in resp.json()]
    assert 102 in ids
    assert 101 not in ids


def test_dependency_gating_allows_guru_components(db, client):
    db.add(Subject(id=200, type="radical", characters="r", slug="r2", level=1, jlpt_level="N5",
                   meanings=json.dumps([{"meaning": "R2", "primary": True}])))
    db.add(SrsItem(subject_id=200, srs_stage=5))

    db.add(Subject(id=201, type="kanji", characters="k", slug="k2", level=1, jlpt_level="N5",
                   meanings=json.dumps([{"meaning": "K2", "primary": True}]),
                   readings=json.dumps([{"reading": "き", "primary": True}])))
    db.add(SrsItem(subject_id=201, srs_stage=0))
    db.add(SubjectDependency(subject_id=201, component_id=200))

    db.add(Setting(key="lesson_batch_size", value=json.dumps(10)))
    db.add(Setting(key="dependency_gating", value=json.dumps(True)))
    db.add(Setting(key="jlpt_gating", value=json.dumps(False)))
    db.add(Setting(key="srs_intervals", value=json.dumps(DEFAULT_INTERVALS)))
    db.commit()

    resp = client.get("/api/lessons")
    ids = [item["id"] for item in resp.json()]
    assert 201 in ids


def test_lessons_include_components_and_context(db, client):
    db.add(Subject(id=300, type="radical", characters="r", slug="r3", level=1, jlpt_level="N5",
                   meanings=json.dumps([{"meaning": "R3", "primary": True}])))
    db.add(SrsItem(subject_id=300, srs_stage=5))

    db.add(Subject(id=301, type="kanji", characters="k", slug="k3", level=1, jlpt_level="N5",
                   meanings=json.dumps([{"meaning": "K3", "primary": True}]),
                   readings=json.dumps([{"reading": "か", "primary": True}]),
                   meaning_hint="Think of K",
                   context_sentences=json.dumps([{"ja": "これはKです", "en": "This is K"}])))
    db.add(SrsItem(subject_id=301, srs_stage=0))
    db.add(SubjectDependency(subject_id=301, component_id=300))

    db.add(Setting(key="lesson_batch_size", value=json.dumps(10)))
    db.add(Setting(key="dependency_gating", value=json.dumps(False)))
    db.add(Setting(key="jlpt_gating", value=json.dumps(False)))
    db.add(Setting(key="srs_intervals", value=json.dumps(DEFAULT_INTERVALS)))
    db.commit()

    resp = client.get("/api/lessons")
    item = resp.json()[0]
    assert item["id"] == 301
    assert len(item["components"]) == 1
    assert item["meaning_hint"] == "Think of K"
    assert len(item["context_sentences"]) == 1
