import time
from backend.srs_engine import (
    advance_stage,
    retreat_stage,
    next_review_time,
    check_answer_meaning,
    check_answer_meaning_detailed,
    check_answer_reading,
    check_reading_hint,
    DEFAULT_INTERVALS,
)


class TestStageAdvancement:
    def test_advance_from_1_to_2(self):
        assert advance_stage(1) == 2

    def test_advance_from_8_to_9_burned(self):
        assert advance_stage(8) == 9

    def test_advance_capped_at_9(self):
        assert advance_stage(9) == 9


class TestStageRetreat:
    def test_retreat_apprentice_drops_by_1(self):
        assert retreat_stage(2) == 1
        assert retreat_stage(3) == 2
        assert retreat_stage(4) == 3

    def test_retreat_apprentice_floor_is_1(self):
        assert retreat_stage(1) == 1

    def test_retreat_guru_and_above_drops_by_2(self):
        assert retreat_stage(5) == 3
        assert retreat_stage(6) == 4
        assert retreat_stage(7) == 5
        assert retreat_stage(8) == 6


class TestNextReviewTime:
    def test_stage_0_returns_none(self):
        assert next_review_time(0, DEFAULT_INTERVALS) is None

    def test_stage_9_returns_none(self):
        assert next_review_time(9, DEFAULT_INTERVALS) is None

    def test_stage_1_returns_4_hours_from_now(self):
        now = time.time()
        result = next_review_time(1, DEFAULT_INTERVALS)
        assert abs(result - (now + 14400)) < 2


class TestAnswerChecking:
    def test_meaning_exact_match(self):
        meanings = [{"meaning": "Big", "primary": True}, {"meaning": "Large", "primary": False}]
        assert check_answer_meaning("big", meanings) is True
        assert check_answer_meaning("Big", meanings) is True
        assert check_answer_meaning("large", meanings) is True

    def test_meaning_wrong(self):
        meanings = [{"meaning": "Big", "primary": True}]
        assert check_answer_meaning("small", meanings) is False

    def test_meaning_close_typo_tolerance(self):
        meanings = [{"meaning": "Construction", "primary": True}]
        assert check_answer_meaning("constructon", meanings) is True

    def test_meaning_no_tolerance_short_words(self):
        meanings = [{"meaning": "Big", "primary": True}]
        assert check_answer_meaning("bag", meanings) is False

    def test_reading_exact_hiragana(self):
        readings = [{"reading": "たい", "primary": True, "type": "onyomi"}]
        assert check_answer_reading("たい", readings) is True

    def test_reading_wrong(self):
        readings = [{"reading": "たい", "primary": True, "type": "onyomi"}]
        assert check_answer_reading("だい", readings) is False

    def test_reading_accepts_any_valid(self):
        readings = [
            {"reading": "たい", "primary": True, "type": "onyomi"},
            {"reading": "おお", "primary": False, "accepted_answer": True, "type": "kunyomi"},
        ]
        assert check_answer_reading("おお", readings) is True

    def test_reading_rejects_non_accepted(self):
        readings = [
            {"reading": "いち", "primary": True, "accepted_answer": True, "type": "onyomi"},
            {"reading": "ひと", "primary": False, "accepted_answer": False, "type": "kunyomi"},
        ]
        assert check_answer_reading("ひと", readings) is False

    def test_reading_hint_for_non_accepted(self):
        readings = [
            {"reading": "いち", "primary": True, "accepted_answer": True, "type": "onyomi"},
            {"reading": "ひと", "primary": False, "accepted_answer": False, "type": "kunyomi"},
        ]
        hint = check_reading_hint("ひと", readings)
        assert hint is not None
        assert "onyomi" in hint

    def test_reading_hint_none_for_wrong_answer(self):
        readings = [
            {"reading": "いち", "primary": True, "accepted_answer": True, "type": "onyomi"},
        ]
        assert check_reading_hint("かん", readings) is None

    def test_reading_hint_none_for_correct_answer(self):
        readings = [
            {"reading": "いち", "primary": True, "accepted_answer": True, "type": "onyomi"},
        ]
        assert check_reading_hint("いち", readings) is None


class TestDetailedAnswerChecking:
    def test_exact_match_returns_correct(self):
        meanings = [{"meaning": "Big", "primary": True}]
        result = check_answer_meaning_detailed("big", meanings)
        assert result["status"] == "correct"

    def test_typo_returns_close(self):
        meanings = [{"meaning": "Beginning", "primary": True}]
        result = check_answer_meaning_detailed("begining", meanings)
        assert result["status"] == "close"

    def test_wrong_answer_returns_incorrect(self):
        meanings = [{"meaning": "Big", "primary": True}]
        result = check_answer_meaning_detailed("small", meanings)
        assert result["status"] == "incorrect"

    def test_short_word_typo_is_wrong_not_close(self):
        meanings = [{"meaning": "Big", "primary": True}]
        result = check_answer_meaning_detailed("bag", meanings)
        assert result["status"] == "incorrect"

    def test_close_includes_did_you_mean(self):
        meanings = [{"meaning": "Construction", "primary": True}]
        result = check_answer_meaning_detailed("constructon", meanings)
        assert result["status"] == "close"
        assert result["did_you_mean"] == "Construction"

    def test_synonym_list_checked(self):
        meanings = [{"meaning": "Big", "primary": True}]
        synonyms = ["Huge", "Enormous"]
        result = check_answer_meaning_detailed("huge", meanings, synonyms)
        assert result["status"] == "correct"
