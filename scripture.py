"""和合本聖經文本查詢：書卷＋章節範圍 → 一段經文的逐句陣列。

`scripture/cuv.json` 是跟天父日記共用的同一份文本資料（從公版 iBibles 資料建出來的
和合本，天父日記的 `build_cuv_from_ibibles.py` 產出）。這裡是直接拿資料檔案過來用，
不是程式碼依賴——真的要做成「共用模組」的話，這會是第一個可以抽出去的地方。

`parse_range` / `get_scripture` 的邏輯照抄天父日記 app.py 裡驗證過會動的寫法。
"""

import json
import os
from typing import List, Tuple

_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "scripture", "cuv.json")

with open(_PATH, encoding="utf-8") as _f:
    BIBLE: dict = json.load(_f)

BOOK_NAMES: List[str] = list(BIBLE.keys())


def parse_range(rng: str) -> Tuple[int, int, int, int]:
    """解析像 '24:13-17'、'6:1-7:5'、'24:13' 這樣的一段範圍。"""
    rng = str(rng).strip()
    if "-" not in rng:
        ch, v = rng.split(":")
        c = int(ch)
        vv = int(v)
        return c, vv, c, vv

    start, end = rng.split("-", 1)
    sc, sv = map(int, start.split(":"))

    if ":" in end:
        ec, ev = map(int, end.split(":"))
    else:
        ec, ev = sc, int(end)

    return sc, sv, ec, ev


def _segment(book_data: dict, sc: int, sv: int, ec: int, ev: int) -> List[str]:
    verses: List[str] = []
    for ch in range(sc, ec + 1):
        chapter = book_data.get(str(ch))
        if not chapter:
            continue
        v_start = sv if ch == sc else 1
        v_end = ev if ch == ec else max(map(int, chapter.keys()))
        for v in range(v_start, v_end + 1):
            text = chapter.get(str(v))
            if text and text != "見上節":
                verses.append(text)
    return verses


def resolve_book_chapter(reference: str) -> Tuple[str, int] | None:
    """把「路加福音 24:13-17」這種 reference 拆成 (書卷, 起始章)。

    用「reference 是否以某個已知書卷開頭」來配對，不是單純 split(' ')——
    手動貼經文那條路（/admin 手動表單）的 reference 是輔導自己打的自由格式，
    不一定照著「書卷 章:節」排版，配不上已知書卷就回 None，呼叫端自己決定退回哪裡。
    """
    reference = (reference or "").strip()
    if not reference:
        return None
    for book in sorted(BOOK_NAMES, key=len, reverse=True):
        if reference.startswith(book):
            rest = reference[len(book):].strip()
            chapter_part = rest.split(":", 1)[0].split("-", 1)[0].strip()
            try:
                return book, int(chapter_part)
            except ValueError:
                return None
    return None


def get_scripture(book: str, rng: str) -> List[str]:
    """回傳一段話的逐句陣列（不含章節數字，接我們畫面上一句一行的樣子）。

    支援單一範圍（'1:1-31'）、跨章（'1:1-2:3'）、逗號分隔多段（'6:28-29,31:3'）。
    書卷或範圍找不到就回傳空陣列，呼叫端自己決定怎麼提示使用者。
    """
    book = (book or "").strip()
    rng = (rng or "").strip()
    if not book or not rng or book not in BIBLE:
        return []

    book_data = BIBLE[book]
    verses: List[str] = []
    for segment in [s.strip() for s in rng.split(",") if s.strip()]:
        try:
            sc, sv, ec, ev = parse_range(segment)
        except (ValueError, KeyError):
            continue
        verses.extend(_segment(book_data, sc, sv, ec, ev))

    return verses
