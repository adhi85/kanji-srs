from sqlalchemy import Column, Integer, Text, Float, ForeignKey
from sqlalchemy.orm import relationship
from backend.database import Base


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

    srs_item = relationship("SrsItem", back_populates="subject", uselist=False)
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
    subject_id = Column(Integer, ForeignKey("subjects.id"), unique=True, nullable=False)
    srs_stage = Column(Integer, nullable=False, default=0)
    unlocked_at = Column(Float, nullable=True)
    started_at = Column(Float, nullable=True)
    next_review_at = Column(Float, nullable=True)
    correct_count = Column(Integer, default=0)
    incorrect_count = Column(Integer, default=0)
    meaning_correct_in_session = Column(Integer, default=0)
    reading_correct_in_session = Column(Integer, default=0)

    subject = relationship("Subject", back_populates="srs_item")


class Setting(Base):
    __tablename__ = "settings"

    key = Column(Text, primary_key=True)
    value = Column(Text, nullable=False)
