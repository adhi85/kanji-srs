from backend.jlpt_mapping import wanikani_level_to_jlpt, N5_KANJI


def test_n5_kanji_by_character():
    assert wanikani_level_to_jlpt(1, characters="一", subject_type="kanji") == "N5"
    assert wanikani_level_to_jlpt(16, characters="書", subject_type="kanji") == "N5"
    assert wanikani_level_to_jlpt(13, characters="駅", subject_type="kanji") == "N5"


def test_non_n5_kanji_at_low_wk_level():
    assert wanikani_level_to_jlpt(2, characters="犬", subject_type="kanji") == "N4"
    assert wanikani_level_to_jlpt(5, characters="世", subject_type="kanji") == "N4"


def test_non_kanji_uses_level_mapping():
    assert wanikani_level_to_jlpt(1) == "N5"
    assert wanikani_level_to_jlpt(10) == "N5"
    assert wanikani_level_to_jlpt(1, characters="一", subject_type="radical") == "N5"


def test_level_11_is_n4():
    assert wanikani_level_to_jlpt(11) == "N4"


def test_level_30_is_n3():
    assert wanikani_level_to_jlpt(30) == "N3"


def test_level_40_is_n2():
    assert wanikani_level_to_jlpt(40) == "N2"


def test_level_50_is_n1():
    assert wanikani_level_to_jlpt(50) == "N1"


def test_level_60_is_n1():
    assert wanikani_level_to_jlpt(60) == "N1"


def test_invalid_level_returns_none():
    assert wanikani_level_to_jlpt(0) is None
    assert wanikani_level_to_jlpt(61) is None


def test_n5_kanji_set_has_108_entries():
    assert len(N5_KANJI) == 108
