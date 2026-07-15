"""資料層：接了 Supabase 就存真的資料；沒接（本機示範／還沒拿到金鑰）就退回
記憶體內的示範資料，讓專案在拿到 Supabase 專案金鑰之前也能先跑、先被看見。

`schema.sql` 是這裡對應的資料庫結構。
"""

import os
import uuid
from datetime import date

import ai_guide
from supabase_client import sb

DEFAULT_GROUP_NAME = "恩典少年"
DEFAULT_GUIDING_QUESTION = "哪一句話，也讓你想停下腳步？"

# 真人送出的領受目前一律長成花（圖鑑式的花／果／蝶／石分類是北極星文件明訂的
# 第二階段功能，這一版故意不做）。這個小色盤只是讓同一叢花園裡的花不要長得
# 一模一樣，跟「這朵比較稀有」完全無關。
_BLOOM_COLORS = ["#EFC26B", "#E8A98A", "#E2916A", "#D9B36C", "#E0A75E"]

# 記憶體示範模式的狀態。故意跟真正接 Supabase 之後的行為一致：
# 一開始「今天還沒有人排經文」，要先在 /admin 排一次才會出現——
# 不是內建一段固定範例硬掛著，這樣本機測試走的才是跟正式站一樣的路徑。
_demo_group = {"id": "demo-group", "name": DEFAULT_GROUP_NAME}
_demo_passage: dict | None = None
_demo_reflections: list[dict] = []


def _demo_mode() -> bool:
    return sb is None


def seed_demo_data() -> None:
    """本機快速預覽用：灌一段範例經文＋幾則示範領受，讓人一打開就看得到畫面長什麼樣。
    只在記憶體示範模式（沒接 Supabase）時有效果，正式站接了 Supabase 之後這個函式不會做任何事。
    """
    global _demo_passage, _demo_reflections
    if not _demo_mode():
        return

    _demo_passage = {
        "id": "demo-passage",
        "reference": "路加福音 24:13–17 · 以馬忤斯路上",
        "verses": [
            "正當那日，門徒中有兩個人往一個村子去，這村子名叫以馬忤斯，離耶路撒冷約有二十五里。",
            "他們彼此談論所遇見的這一切事。",
            "正談論相問的時候，耶穌親自就近他們，和他們同行。",
            "只是他們的眼睛迷糊了，不認得他。",
            "耶穌對他們說，你們走路彼此談論的是什麼事呢，你們為什麼愁容滿面呢。",
        ],
        "guiding_question": DEFAULT_GUIDING_QUESTION,
    }
    _demo_reflections = [
        {
            "id": str(uuid.uuid4()),
            "member_id": "demo-思彤",
            "name": "思彤",
            "verse_index": 3,
            "note": "我也覺得自己常常認不出，神其實已經在旁邊很久了。",
            "kind": "flower",
            "color": "#E8A98A",
        },
        {
            "id": str(uuid.uuid4()),
            "member_id": "demo-柏睿",
            "name": "柏睿",
            "verse_index": 2,
            "note": "",
            "kind": "stone",
            "color": "#A6A08C",
        },
        {
            "id": str(uuid.uuid4()),
            "member_id": "demo-瑀彤",
            "name": "瑀彤",
            "verse_index": 4,
            "note": "這句戳到我，這禮拜真的很低落，但原來耶穌會直接問。",
            "kind": "butterfly",
            "color": "#9FB3D9",
        },
        {
            "id": str(uuid.uuid4()),
            "member_id": "demo-柏諺",
            "name": "柏諺",
            "verse_index": 0,
            "note": "",
            "kind": "fruit",
            "color": "#E2916A",
        },
    ]


if _demo_mode() and os.environ.get("SEED_DEMO_DATA", "1") != "0":
    seed_demo_data()


def _bloom_color_for(member_id: str) -> str:
    return _BLOOM_COLORS[hash(member_id) % len(_BLOOM_COLORS)]


# ---------- group ----------


def get_or_create_default_group() -> dict:
    if _demo_mode():
        return _demo_group

    existing = sb.table("groups").select("*").limit(1).execute()
    if existing.data:
        return existing.data[0]
    created = sb.table("groups").insert({"name": DEFAULT_GROUP_NAME}).execute()
    return created.data[0]


# ---------- members ----------


def upsert_member(user: dict) -> dict:
    """LINE 登入成功後呼叫：把這個人存進小組成員名單（已存在就更新資料）。"""
    if _demo_mode():
        return {"id": f"demo-{user['line_user_id']}", **user}

    group = get_or_create_default_group()
    result = (
        sb.table("members")
        .upsert(
            {
                "group_id": group["id"],
                "line_user_id": user["line_user_id"],
                "display_name": user.get("display_name") or "",
                "picture_url": user.get("picture_url"),
            },
            on_conflict="line_user_id",
        )
        .execute()
    )
    return result.data[0]


def get_member_by_line_id(line_user_id: str) -> dict | None:
    if _demo_mode():
        return {"id": f"demo-{line_user_id}"}

    result = sb.table("members").select("*").eq("line_user_id", line_user_id).limit(1).execute()
    return result.data[0] if result.data else None


# ---------- 今天這段經文 ----------


def get_today_passage() -> dict | None:
    """回傳今天這段經文；如果小組今天還沒有輔導排經文，回傳 None。"""
    if _demo_mode():
        return _resolve_guiding_question(_demo_passage) if _demo_passage else None

    group = get_or_create_default_group()
    result = (
        sb.table("daily_passages")
        .select("*")
        .eq("group_id", group["id"])
        .eq("passage_date", date.today().isoformat())
        .limit(1)
        .execute()
    )
    passage = result.data[0] if result.data else None
    return _resolve_guiding_question(passage) if passage else None


def _resolve_guiding_question(passage: dict) -> dict:
    """引導問題留空的話，第一次真的被打開時才生一次、存回去，之後就是同一句
    （跟天父日記的做法一樣：AI 只呼叫一次，不是每個人打開都重新生一次）。
    這裡故意不在排經文／批次匯入當下就呼叫 AI——匯入一次可能是好幾天份，
    每一天都各自打一次 AI，很容易在單一個請求裡連續打好幾次而被 rate limit。
    """
    if passage.get("guiding_question"):
        return passage

    question = ai_guide.generate_guiding_question(passage["reference"], passage["verses"])
    question = question or DEFAULT_GUIDING_QUESTION
    passage["guiding_question"] = question

    if _demo_mode():
        global _demo_passage
        if _demo_passage and _demo_passage.get("id") == passage.get("id"):
            _demo_passage["guiding_question"] = question
    else:
        sb.table("daily_passages").update({"guiding_question": question}).eq("id", passage["id"]).execute()

    return passage


def set_passage_for_date(
    passage_date: str, reference: str, verses: list[str], guiding_question: str, leader_member_id: str
) -> dict:
    """排定某一天的經文（不限今天，讓輔導可以一次排好接下來好幾天）。
    已經排過同一天就更新，不會重複長出第二筆。
    引導問題留空就先存空的，等真的被打開那天再生（見 _resolve_guiding_question）。
    """
    payload = {
        "passage_date": passage_date,
        "reference": reference,
        "verses": verses,
        "guiding_question": guiding_question,
        "created_by": leader_member_id,
    }

    if _demo_mode():
        global _demo_passage, _demo_reflections
        if passage_date == date.today().isoformat():
            # 換了一段新的經文，昨天那批領受不該掛在新的一段底下。
            if _demo_passage is None or _demo_passage.get("reference") != reference:
                _demo_reflections = []
            _demo_passage = {"id": "demo-passage", **payload}
        return {"id": "demo-passage", **payload}

    group = get_or_create_default_group()
    payload["group_id"] = group["id"]
    result = sb.table("daily_passages").upsert(payload, on_conflict="group_id,passage_date").execute()
    return result.data[0]


def set_today_passage(reference: str, verses: list[str], guiding_question: str, leader_member_id: str) -> dict:
    """輔導種頭香：排定今天這段經文。"""
    return set_passage_for_date(date.today().isoformat(), reference, verses, guiding_question, leader_member_id)


def import_passages(rows: list[dict], leader_member_id: str) -> tuple[int, list[str]]:
    """批次排經文：每一列 {date, reference, verses, guiding_question}。
    回傳 (成功筆數, 失敗列的錯誤訊息)。

    正式站一次打包成單一個請求 upsert，不是每一列各打一次 API——一次匯入
    好幾十、好幾百天的話，逐列各打一次網路請求會慢到讓人以為當機（甚至真的
    拖到 gunicorn worker timeout）。批次 upsert 是同一個 SQL 交易，單一列壞掉
    會讓整批失敗，所以 plan_import.py 在解析階段已經先把明顯有問題的列擋掉。
    """
    if not rows:
        return 0, []

    if _demo_mode():
        ok = 0
        errors: list[str] = []
        for row in rows:
            try:
                set_passage_for_date(
                    row["date"], row["reference"], row["verses"], row.get("guiding_question", ""), leader_member_id
                )
                ok += 1
            except Exception as exc:  # noqa: BLE001 - 示範模式下單一列壞掉不能拖垮整批
                errors.append(f"{row.get('date', '?')}：{exc}")
        return ok, errors

    group = get_or_create_default_group()
    payloads = [
        {
            "group_id": group["id"],
            "passage_date": row["date"],
            "reference": row["reference"],
            "verses": row["verses"],
            "guiding_question": row.get("guiding_question", ""),
            "created_by": leader_member_id,
        }
        for row in rows
    ]

    try:
        sb.table("daily_passages").upsert(payloads, on_conflict="group_id,passage_date").execute()
        return len(payloads), []
    except Exception as exc:  # noqa: BLE001 - 整批寫入失敗，回報給使用者，不能讓網站 500
        return 0, [f"批次寫入資料庫失敗：{exc}"]


# ---------- 領受 ----------


def get_reflections(passage_id: str, my_member_id: str | None = None) -> list[dict]:
    """回傳這段經文下所有人的領受，附上 mine（是不是目前這個人自己留的）。"""
    if _demo_mode():
        items = list(_demo_reflections)
    else:
        result = (
            sb.table("reflections")
            .select("*, members(display_name)")
            .eq("passage_id", passage_id)
            .order("created_at")
            .execute()
        )
        items = [
            {
                "id": r["id"],
                "member_id": r["member_id"],
                "name": (r.get("members") or {}).get("display_name") or "小夥伴",
                "verse_index": r["verse_index"],
                "note": r["note"],
                "kind": r["kind"],
                "color": r["color"],
            }
            for r in result.data
        ]

    for item in items:
        item["mine"] = my_member_id is not None and item["member_id"] == my_member_id
    return items


def get_my_reflection(passage_id: str, member_id: str) -> dict | None:
    if _demo_mode():
        return next((r for r in _demo_reflections if r["member_id"] == member_id), None)

    result = (
        sb.table("reflections")
        .select("*")
        .eq("passage_id", passage_id)
        .eq("member_id", member_id)
        .limit(1)
        .execute()
    )
    return result.data[0] if result.data else None


def add_my_reflection(passage_id: str, member_id: str, verse_index: int, note: str) -> dict:
    """留一句領受。已經留過的話就更新內容，不會重複長出第二朵花。"""
    payload = {
        "passage_id": passage_id,
        "member_id": member_id,
        "verse_index": verse_index,
        "note": note,
        "kind": "flower",
        "color": _bloom_color_for(member_id),
    }

    if _demo_mode():
        existing = next((r for r in _demo_reflections if r["member_id"] == member_id), None)
        if existing:
            existing.update(verse_index=verse_index, note=note)
            return existing
        reflection = {"id": str(uuid.uuid4()), "name": "你", **payload}
        _demo_reflections.append(reflection)
        return reflection

    result = sb.table("reflections").upsert(payload, on_conflict="passage_id,member_id").execute()
    return result.data[0]


def export_passage(passage_id: str) -> dict:
    """Rule 14：一鍵匯出這段經文的所有領受。"""
    passage = get_today_passage() if _demo_mode() else _find_passage(passage_id)
    return {
        "passage": passage,
        "reflections": get_reflections(passage_id),
    }


def _find_passage(passage_id: str) -> dict | None:
    result = sb.table("daily_passages").select("*").eq("id", passage_id).limit(1).execute()
    return result.data[0] if result.data else None
