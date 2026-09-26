import json
from unittest.mock import patch, MagicMock
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.database import Base
from backend.models import Subject, SubjectDependency, SrsItem
from backend.import_wanikani import import_subjects


def _make_api_response(subjects, next_url=None):
    return {
        "total_count": len(subjects),
        "pages": {"next_url": next_url, "previous_url": None, "per_page": 1000},
        "data": subjects,
    }


def _make_subject(id, obj_type, characters, level, meanings, readings=None, components=None):
    return {
        "id": id,
        "object": obj_type,
        "data": {
            "characters": characters,
            "slug": characters,
            "level": level,
            "meanings": [{"meaning": m, "primary": i == 0} for i, m in enumerate(meanings)],
            "readings": [{"reading": r, "primary": i == 0, "type": "onyomi"} for i, r in enumerate(readings or [])],
            "meaning_mnemonic": "A mnemonic.",
            "reading_mnemonic": "A reading mnemonic.",
            "component_subject_ids": components or [],
            "document_url": "https://wanikani.com/{}/{}".format(obj_type, characters),
            "parts_of_speech": [],
        },
    }


def test_import_subjects():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)

    api_data = [
        _make_subject(1, "radical", "一", 1, ["One"]),
        _make_subject(2, "kanji", "大", 1, ["Big"], ["たい", "おお"], [1]),
        _make_subject(3, "vocabulary", "大人", 3, ["Adult"], ["おとな"], [2]),
    ]
    mock_response = MagicMock()
    mock_response.json.return_value = _make_api_response(api_data)
    mock_response.status_code = 200
    mock_response.headers = {"RateLimit-Remaining": "59"}

    with patch("backend.import_wanikani.httpx") as mock_httpx:
        mock_client = MagicMock()
        mock_client.__enter__ = lambda s: s
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get.return_value = mock_response
        mock_httpx.Client.return_value = mock_client

        db = Session()
        import_subjects(db, "fake-token")
        db.close()

    db = Session()
    assert db.query(Subject).count() == 3
    assert db.query(SubjectDependency).count() == 2
    assert db.query(SrsItem).count() == 3
    kanji = db.get(Subject, 2)
    assert kanji.jlpt_level == "N5"
    assert json.loads(kanji.meanings)[0]["meaning"] == "Big"
    db.close()
