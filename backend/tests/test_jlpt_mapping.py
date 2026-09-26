from backend.jlpt_mapping import wanikani_level_to_jlpt


def test_level_1_is_n5():
    assert wanikani_level_to_jlpt(1) == "N5"

def test_level_10_is_n5():
    assert wanikani_level_to_jlpt(10) == "N5"

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
