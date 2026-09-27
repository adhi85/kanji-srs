import json
from backend.models import Subject, SubjectDependency, SrsItem, Setting, UserSynonym, LevelEvent


def test_subject_creation(db):
    s = Subject(
        id=1,
        type="kanji",
        characters="大",
        slug="big",
        level=1,
        jlpt_level="N5",
        meanings=json.dumps([{"meaning": "Big", "primary": True}]),
        readings=json.dumps([{"reading": "たい", "primary": True, "type": "onyomi"}]),
        meaning_mnemonic="A person spreading arms wide is big.",
        reading_mnemonic="Tie a big knot.",
    )
    db.add(s)
    db.commit()
    fetched = db.get(Subject, 1)
    assert fetched.characters == "大"
    assert fetched.jlpt_level == "N5"
    assert json.loads(fetched.meanings)[0]["meaning"] == "Big"


def test_subject_dependency(db):
    radical = Subject(id=1, type="radical", characters="一", slug="one", level=1, jlpt_level="N5",
                      meanings=json.dumps([{"meaning": "One", "primary": True}]))
    kanji = Subject(id=2, type="kanji", characters="大", slug="big", level=1, jlpt_level="N5",
                    meanings=json.dumps([{"meaning": "Big", "primary": True}]))
    dep = SubjectDependency(subject_id=2, component_id=1)
    db.add_all([radical, kanji, dep])
    db.commit()

    deps = db.query(SubjectDependency).filter_by(subject_id=2).all()
    assert len(deps) == 1
    assert deps[0].component_id == 1


def test_srs_item_defaults(db):
    s = Subject(id=1, type="radical", characters="口", slug="mouth", level=1, jlpt_level="N5",
                meanings=json.dumps([{"meaning": "Mouth", "primary": True}]))
    db.add(s)
    db.commit()
    item = SrsItem(subject_id=1)
    db.add(item)
    db.commit()
    assert item.srs_stage == 0
    assert item.correct_count == 0
    assert item.incorrect_count == 0
    assert item.next_review_at is None


def test_setting_roundtrip(db):
    setting = Setting(key="lesson_batch_size", value=json.dumps(5))
    db.add(setting)
    db.commit()
    fetched = db.query(Setting).filter_by(key="lesson_batch_size").one()
    assert json.loads(fetched.value) == 5


def test_subject_has_new_columns(db):
    s = Subject(
        id=99, type="vocabulary", characters="食べる", slug="taberu", level=5,
        meanings=json.dumps([{"meaning": "To Eat", "primary": True}]),
        context_sentences=json.dumps([{"ja": "ご飯を食べる", "en": "I eat rice"}]),
        meaning_hint="Think about what you do with food",
        reading_hint="The kun'yomi reading",
        auxiliary_meanings=json.dumps([{"meaning": "Eat", "type": "whitelist"}]),
        visually_similar_subject_ids=json.dumps([440, 441]),
    )
    db.add(s)
    db.commit()
    loaded = db.get(Subject, 99)
    assert loaded.context_sentences is not None
    assert json.loads(loaded.context_sentences)[0]["ja"] == "ご飯を食べる"
    assert loaded.meaning_hint == "Think about what you do with food"
    assert loaded.reading_hint == "The kun'yomi reading"


def test_srs_item_has_last_incorrect_at(db):
    db.add(Subject(id=98, type="radical", characters="一", slug="one", level=1,
                   meanings=json.dumps([{"meaning": "One", "primary": True}])))
    db.add(SrsItem(subject_id=98, srs_stage=2, last_incorrect_at=1695000000.0))
    db.commit()
    item = db.query(SrsItem).filter_by(subject_id=98).first()
    assert item.last_incorrect_at == 1695000000.0


def test_user_synonym_model(db):
    db.add(Subject(id=97, type="kanji", characters="大", slug="big", level=1,
                   meanings=json.dumps([{"meaning": "Big", "primary": True}])))
    db.commit()
    db.add(UserSynonym(subject_id=97, meaning="Huge"))
    db.commit()
    syns = db.query(UserSynonym).filter_by(subject_id=97).all()
    assert len(syns) == 1
    assert syns[0].meaning == "Huge"


def test_srs_item_has_incorrect_in_session(db):
    db.add(Subject(id=96, type="radical", characters="x", slug="x", level=1,
                   meanings=json.dumps([{"meaning": "X", "primary": True}])))
    db.add(SrsItem(subject_id=96, incorrect_in_session=1))
    db.commit()
    item = db.query(SrsItem).filter_by(subject_id=96).first()
    assert item.incorrect_in_session == 1


def test_level_event_model(db):
    db.add(LevelEvent(level=2, reached_at=1000000.0))
    db.commit()
    row = db.query(LevelEvent).first()
    assert row.level == 2
    assert row.reached_at == 1000000.0
