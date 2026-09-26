from __future__ import annotations


def wanikani_level_to_jlpt(level: int) -> str | None:
    if 1 <= level <= 10:
        return "N5"
    if 11 <= level <= 20:
        return "N4"
    if 21 <= level <= 30:
        return "N3"
    if 31 <= level <= 40:
        return "N2"
    if 41 <= level <= 60:
        return "N1"
    return None
