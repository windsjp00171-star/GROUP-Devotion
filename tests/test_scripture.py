"""和合本查詢層：確保經文一律從正版帶出、範圍解析正確。"""

from scripture import get_scripture, get_scripture_with_labels, parse_range, resolve_book_chapter


def test_labels_basic():
    items = get_scripture_with_labels("路加福音", "24:13-17")
    assert len(items) == 5
    assert items[0][0] == "24:13"
    assert items[0][1].startswith("正當那日")


def test_plain_matches_labeled_text():
    labeled = get_scripture_with_labels("詩篇", "23:1-6")
    plain = get_scripture("詩篇", "23:1-6")
    assert plain == [t for _, t in labeled]
    assert len(plain) == 6


def test_cross_chapter_labels_carry_right_chapter():
    items = get_scripture_with_labels("路加福音", "1:1-2:2")
    chapters = {lbl.split(":")[0] for lbl, _ in items}
    assert "1" in chapters and "2" in chapters


def test_invalid_book_returns_empty():
    assert get_scripture_with_labels("不存在的書卷", "1:1") == []
    assert get_scripture("路加福音", "999:1") == []


def test_resolve_book_chapter():
    assert resolve_book_chapter("路加福音 24:13-17") == ("路加福音", 24)
    assert resolve_book_chapter("詩篇 23:1 · 我的牧者") == ("詩篇", 23)
    assert resolve_book_chapter("隨便亂打的字") is None
    assert resolve_book_chapter("") is None


def test_parse_range():
    assert parse_range("24:13-17") == (24, 13, 24, 17)
    assert parse_range("6:1-7:5") == (6, 1, 7, 5)
    assert parse_range("24:13") == (24, 13, 24, 13)
