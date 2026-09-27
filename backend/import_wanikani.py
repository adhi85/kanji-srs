import json
import sys
import time

import httpx
from sqlalchemy.orm import Session

from backend.database import Base, engine, SessionLocal
from backend.jlpt_mapping import wanikani_level_to_jlpt
from backend.models import Subject, SubjectDependency, SrsItem

WANIKANI_API_BASE = "https://api.wanikani.com/v2"


def import_subjects(db: Session, token: str, user_id: int = 1):
    url = "{}/subjects".format(WANIKANI_API_BASE)
    headers = {"Authorization": "Bearer {}".format(token)}
    total_imported = 0

    with httpx.Client(timeout=30) as client:
        while url:
            resp = client.get(url, headers=headers)
            resp.raise_for_status()
            data = resp.json()

            for item in data["data"]:
                subj_data = item["data"]
                char_image = None
                for img in subj_data.get("character_images", []):
                    if img.get("content_type") == "image/svg+xml":
                        char_image = img.get("url")
                        break

                subject = Subject(
                    id=item["id"],
                    type=item["object"],
                    characters=subj_data.get("characters"),
                    slug=subj_data.get("slug"),
                    level=subj_data["level"],
                    jlpt_level=wanikani_level_to_jlpt(subj_data["level"]),
                    meanings=json.dumps(subj_data.get("meanings", [])),
                    readings=json.dumps(subj_data.get("readings", [])),
                    meaning_mnemonic=subj_data.get("meaning_mnemonic"),
                    reading_mnemonic=subj_data.get("reading_mnemonic"),
                    part_of_speech=json.dumps(subj_data.get("parts_of_speech", [])),
                    document_url=subj_data.get("document_url"),
                    context_sentences=json.dumps(subj_data.get("context_sentences", [])),
                    meaning_hint=subj_data.get("meaning_hint"),
                    reading_hint=subj_data.get("reading_hint"),
                    auxiliary_meanings=json.dumps(subj_data.get("auxiliary_meanings", [])),
                    visually_similar_subject_ids=json.dumps(subj_data.get("visually_similar_subject_ids", [])),
                    character_image=char_image,
                )
                db.merge(subject)

                for comp_id in subj_data.get("component_subject_ids", []):
                    db.merge(SubjectDependency(subject_id=item["id"], component_id=comp_id))

                existing_srs = db.query(SrsItem).filter_by(user_id=user_id, subject_id=item["id"]).first()
                if not existing_srs:
                    db.add(SrsItem(user_id=user_id, subject_id=item["id"], srs_stage=0))

            total_imported += len(data["data"])
            print("Imported {} subjects...".format(total_imported))

            url = data["pages"].get("next_url")

            remaining = int(resp.headers.get("RateLimit-Remaining", "59"))
            if remaining < 5:
                print("Rate limit approaching, sleeping 30s...")
                time.sleep(30)

    db.commit()
    print("Done. Total subjects imported: {}".format(total_imported))


def main():
    if len(sys.argv) < 2:
        print("Usage: python -m backend.import_wanikani <API_TOKEN>")
        sys.exit(1)

    token = sys.argv[1]
    Base.metadata.create_all(engine)
    db = SessionLocal()
    try:
        import_subjects(db, token)
    finally:
        db.close()


if __name__ == "__main__":
    main()
