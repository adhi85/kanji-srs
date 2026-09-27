from sqlalchemy import Column, Integer, Text, Float, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from backend.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(Text, unique=True, nullable=False)
    password_hash = Column(Text, nullable=False)
    created_at = Column(Float, nullable=False)


class Subject(Base):
    __tablename__ = "subjects"

    id = Column(Integer, primary_key=True)
    type = Column(Text, nullable=False)
    characters = Column(Text, nullable=True)
    slug = Column(Text, nullable=True)
    level = Column(Integer, nullable=False)
    jlpt_level = Column(Text, nullable=True)
    meanings = Column(Text, nullable=False)
    readings = Column(Text, nullable=True)
    meaning_mnemonic = Column(Text, nullable=True)
    reading_mnemonic = Column(Text, nullable=True)
    part_of_speech = Column(Text, nullable=True)
    document_url = Column(Text, nullable=True)
    context_sentences = Column(Text, nullable=True)
    meaning_hint = Column(Text, nullable=True)
    reading_hint = Column(Text, nullable=True)
    auxiliary_meanings = Column(Text, nullable=True)
    visually_similar_subject_ids = Column(Text, nullable=True)

    srs_items = relationship("SrsItem", back_populates="subject")
    components = relationship(
        "Subject",
        secondary="subject_dependencies",
        primaryjoin="Subject.id == SubjectDependency.subject_id",
        secondaryjoin="Subject.id == SubjectDependency.component_id",
        viewonly=True,
    )


class SubjectDependency(Base):
    __tablename__ = "subject_dependencies"

    subject_id = Column(Integer, ForeignKey("subjects.id"), primary_key=True)
    component_id = Column(Integer, ForeignKey("subjects.id"), primary_key=True)


class SrsItem(Base):
    __tablename__ = "srs_items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    subject_id = Column(Integer, ForeignKey("subjects.id"), nullable=False)
    srs_stage = Column(Integer, nullable=False, default=0)
    unlocked_at = Column(Float, nullable=True)
    started_at = Column(Float, nullable=True)
    next_review_at = Column(Float, nullable=True)
    correct_count = Column(Integer, default=0)
    incorrect_count = Column(Integer, default=0)
    meaning_correct_in_session = Column(Integer, default=0)
    reading_correct_in_session = Column(Integer, default=0)
    last_incorrect_at = Column(Float, nullable=True)
    incorrect_in_session = Column(Integer, default=0)

    subject = relationship("Subject", back_populates="srs_items")
    user = relationship("User")

    __table_args__ = (UniqueConstraint("user_id", "subject_id"),)


class Setting(Base):
    __tablename__ = "settings"

    user_id = Column(Integer, ForeignKey("users.id"), primary_key=True)
    key = Column(Text, primary_key=True)
    value = Column(Text, nullable=False)


class LevelEvent(Base):
    __tablename__ = "level_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    level = Column(Integer, nullable=False)
    reached_at = Column(Float, nullable=False)

    __table_args__ = (UniqueConstraint("user_id", "level"),)


class UserSynonym(Base):
    __tablename__ = "user_synonyms"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    subject_id = Column(Integer, ForeignKey("subjects.id"), nullable=False)
    meaning = Column(Text, nullable=False)

    __table_args__ = (UniqueConstraint("user_id", "subject_id", "meaning"),)
