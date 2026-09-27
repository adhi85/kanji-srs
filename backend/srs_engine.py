from __future__ import annotations
import time

DEFAULT_INTERVALS = [0, 14400, 28800, 82800, 169200, 601200, 1206000, 2588400, 10364400, 0]


def advance_stage(current_stage: int) -> int:
    return min(current_stage + 1, 9)


def retreat_stage(current_stage: int) -> int:
    if current_stage <= 4:
        return max(current_stage - 1, 1)
    return max(current_stage - 2, 1)


def next_review_time(stage: int, intervals: list[int]) -> float | None:
    if stage == 0 or stage == 9:
        return None
    return time.time() + intervals[stage]


def check_answer_meaning(answer: str, meanings: list[dict]) -> bool:
    answer_lower = answer.strip().lower()
    for m in meanings:
        expected = m["meaning"].strip().lower()
        if answer_lower == expected:
            return True
        if len(expected) >= 5 and _levenshtein(answer_lower, expected) <= 1:
            return True
    return False


def check_answer_meaning_detailed(
    answer: str,
    meanings: list[dict],
    synonyms: list[str] | None = None,
) -> dict:
    answer_lower = answer.strip().lower()

    all_accepted = [m["meaning"] for m in meanings if m.get("accepted_answer", True)]
    if synonyms:
        all_accepted.extend(synonyms)

    for accepted in all_accepted:
        if answer_lower == accepted.strip().lower():
            return {"status": "correct"}

    closest_dist = float("inf")
    closest_word = None
    for accepted in all_accepted:
        expected = accepted.strip().lower()
        if len(expected) < 5:
            continue
        dist = _levenshtein(answer_lower, expected)
        if dist < closest_dist:
            closest_dist = dist
            closest_word = accepted

    threshold = 1 if (closest_word and len(closest_word) <= 7) else 2
    if closest_word and closest_dist <= threshold:
        return {"status": "close", "did_you_mean": closest_word}

    return {"status": "incorrect"}


def check_answer_reading(answer: str, readings: list[dict]) -> bool:
    answer_stripped = answer.strip()
    return any(
        r["reading"].strip() == answer_stripped
        for r in readings
        if r.get("accepted_answer") is not False
    )


def check_reading_hint(answer: str, readings: list[dict]) -> str | None:
    answer_stripped = answer.strip()
    for r in readings:
        if r["reading"].strip() == answer_stripped and r.get("accepted_answer") is False:
            wanted_type = next(
                (rd.get("type") for rd in readings if rd.get("accepted_answer") is not False),
                None,
            )
            if wanted_type:
                return f"We're looking for the {wanted_type} reading"
            return "That's not the reading we're looking for"
    return None


def _levenshtein(s1: str, s2: str) -> int:
    if len(s1) < len(s2):
        return _levenshtein(s2, s1)
    if len(s2) == 0:
        return len(s1)
    prev_row = list(range(len(s2) + 1))
    for i, c1 in enumerate(s1):
        curr_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = prev_row[j + 1] + 1
            deletions = curr_row[j] + 1
            substitutions = prev_row[j] + (c1 != c2)
            curr_row.append(min(insertions, deletions, substitutions))
        prev_row = curr_row
    return prev_row[-1]
