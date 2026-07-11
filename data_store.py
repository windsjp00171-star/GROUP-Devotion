"""資料層：目前用記憶體內的示範資料。

這一層刻意跟路由分開，之後接 Supabase（mark_core.supabase_client）時，
只需要換掉這個檔案裡的函式實作，app.py 不用動。
"""

import uuid

TODAY_PASSAGE = {
    "reference": "路加福音 24:13–17 · 以馬忤斯路上",
    "verses": [
        "正當那日，門徒中有兩個人往一個村子去，這村子名叫以馬忤斯，離耶路撒冷約有二十五里。",
        "他們彼此談論所遇見的這一切事。",
        "正談論相問的時候，耶穌親自就近他們，和他們同行。",
        "只是他們的眼睛迷糊了，不認得他。",
        "耶穌對他們說，你們走路彼此談論的是什麼事呢，你們為什麼愁容滿面呢。",
    ],
}

# 輔導種頭香 + 小組同伴既有的領受（示範資料，之後換成 Supabase 查詢）
_reflections = [
    {
        "id": str(uuid.uuid4()),
        "name": "思彤",
        "verse_index": 3,
        "note": "我也覺得自己常常認不出，神其實已經在旁邊很久了。",
        "kind": "flower",
        "color": "#E8A98A",
        "mine": False,
    },
    {
        "id": str(uuid.uuid4()),
        "name": "柏睿",
        "verse_index": 2,
        "note": "",
        "kind": "stone",
        "color": "#A6A08C",
        "mine": False,
    },
    {
        "id": str(uuid.uuid4()),
        "name": "瑀彤",
        "verse_index": 4,
        "note": "這句戳到我，這禮拜真的很低落，但原來耶穌會直接問。",
        "kind": "butterfly",
        "color": "#9FB3D9",
        "mine": False,
    },
    {
        "id": str(uuid.uuid4()),
        "name": "柏諺",
        "verse_index": 0,
        "note": "",
        "kind": "fruit",
        "color": "#E2916A",
        "mine": False,
    },
]


def get_today_passage():
    return TODAY_PASSAGE


def get_reflections():
    return _reflections


def get_my_reflection():
    return next((r for r in _reflections if r["mine"]), None)


def add_my_reflection(verse_index, note):
    """留一句領受。已經留過的話就更新，不會重複長出第二朵花。"""
    existing = get_my_reflection()
    if existing:
        existing["verse_index"] = verse_index
        existing["note"] = note
        return existing

    reflection = {
        "id": str(uuid.uuid4()),
        "name": "你",
        "verse_index": verse_index,
        "note": note,
        "kind": "flower",
        "color": "#EFC26B",
        "mine": True,
    }
    _reflections.append(reflection)
    return reflection


def export_reflections():
    """Rule 14：一鍵匯出今天這段經文的所有領受。"""
    return {
        "passage": TODAY_PASSAGE,
        "reflections": _reflections,
    }
