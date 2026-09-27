"""Add context_sentences, hints, synonyms, and last_incorrect_at columns."""

import sqlite3
import sys
from pathlib import Path

DEFAULT_DB = str(Path(__file__).parent.parent / "data" / "kanji-srs.db")


def migrate(db_path: str = DEFAULT_DB):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    existing = {row[1] for row in cursor.execute("PRAGMA table_info(subjects)")}
    for col in ["context_sentences", "meaning_hint", "reading_hint",
                "auxiliary_meanings", "visually_similar_subject_ids"]:
        if col not in existing:
            cursor.execute(f"ALTER TABLE subjects ADD COLUMN {col} TEXT")

    srs_cols = {row[1] for row in cursor.execute("PRAGMA table_info(srs_items)")}
    if "last_incorrect_at" not in srs_cols:
        cursor.execute("ALTER TABLE srs_items ADD COLUMN last_incorrect_at REAL")

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_synonyms (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            subject_id INTEGER NOT NULL REFERENCES subjects(id),
            meaning TEXT NOT NULL,
            UNIQUE(subject_id, meaning)
        )
    """)

    if "character_image" not in existing:
        cursor.execute("ALTER TABLE subjects ADD COLUMN character_image TEXT")

    if "incorrect_in_session" not in srs_cols:
        cursor.execute("ALTER TABLE srs_items ADD COLUMN incorrect_in_session INTEGER DEFAULT 0")

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS level_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            level INTEGER UNIQUE NOT NULL,
            reached_at REAL NOT NULL
        )
    """)

    conn.commit()
    conn.close()
    print(f"Migration complete: {db_path}")


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_DB
    migrate(path)
