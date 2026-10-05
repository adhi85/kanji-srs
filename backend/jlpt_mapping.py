from __future__ import annotations

N5_KANJI = set(
    "一人入力二七八九十女子山小大口上下川三千万土"
    "友父分午今少円中天手牛五六月火水木日"
    "生母田本半古出北左右外立目白四"
    "先名年毎多安早西休行会気耳百"
    "男何社見言来車花足"
    "学国長東店門雨空金"
    "前後南食"
    "時高校書"
    "週魚"
    "間買飲道"
    "新電話"
    "語聞駅読"
)


def wanikani_level_to_jlpt(
    level: int,
    characters: str | None = None,
    subject_type: str | None = None,
) -> str | None:
    if subject_type == "kanji" and characters and characters in N5_KANJI:
        return "N5"
    if 1 <= level <= 10:
        if subject_type == "kanji":
            return "N4"
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
