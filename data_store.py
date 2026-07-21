"""資料層：接了 Supabase 就存真的資料；沒接（本機示範／還沒拿到金鑰）就退回
記憶體內的示範資料，讓專案在拿到 Supabase 專案金鑰之前也能先跑、先被看見。

`schema.sql` 是這裡對應的資料庫結構。
"""

import os
import secrets
import uuid

import ai_guide
import local_time
from supabase_client import sb

DEFAULT_GROUP_NAME = "恩典少年"
DEFAULT_GUIDING_QUESTION = "哪一句話，也讓你想停下腳步？"

# 加入碼用的字元集，刻意去掉容易看錯的 0/O/1/I，讓人手動輸入不容易打錯。
_JOIN_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def _generate_join_code(length: int = 6) -> str:
    return "".join(secrets.choice(_JOIN_CODE_ALPHABET) for _ in range(length))

# 對別人領受的反應，固定幾種、各自對應一句寫死的鼓勵語，不是自由留言——
# 自由留言在青少年小組的靈修內容底下風險較高，怕不小心引發論戰。
# 之後想加新的反應，只要在這裡多一組就好，資料庫端不再有 CHECK 限制卡著
# （合法值一律以這份 dict 為準，set_reaction 會擋掉不在名單裡的 kind）。
REACTION_KINDS = {
    "resonate": {"emoji": "🌼", "phrase": "也很有共鳴"},
    "comfort": {"emoji": "💛", "phrase": "覺得很安慰"},
    "light": {"emoji": "✨", "phrase": "也被光照到"},
    "pray": {"emoji": "🙏", "phrase": "想為你禱告"},
    "thankful": {"emoji": "🌱", "phrase": "謝謝你的分享"},
    "moved": {"emoji": "💫", "phrase": "也被觸動了"},
    "amen": {"emoji": "🕊️", "phrase": "跟你一起阿們"},
}

# 真人送出的領受目前一律長成花（圖鑑式的花／果／蝶／石分類是北極星文件明訂的
# 第二階段功能，這一版故意不做）。這個小色盤只是讓同一叢花園裡的花不要長得
# 一模一樣，跟「這朵比較稀有」完全無關。
_BLOOM_COLORS = ["#EFC26B", "#E8A98A", "#E2916A", "#D9B36C", "#E0A75E"]

# 記憶體示範模式的狀態。故意跟真正接 Supabase 之後的行為一致：
# 一開始「今天還沒有人排經文」，要先在 /admin 排一次才會出現——
# 不是內建一段固定範例硬掛著，這樣本機測試走的才是跟正式站一樣的路徑。
#
# 多小組：示範模式也要能同時存在好幾組，才測得出「A 組看不到 B 組」的隔離。
#   _demo_groups      : {group_id: {id, name, join_code}}
#   _demo_members     : {line_user_id: 成員 dict（含 group_id，null = 還沒加入任何組）}
#   _demo_passages    : [經文 dict（各自帶 group_id、passage_date）]
#   _demo_reflections : [領受 dict（各自帶 passage_id）]
_DEMO_GROUP_ID = "demo-group"
_demo_groups: dict[str, dict] = {}
_demo_members: dict[str, dict] = {}
_demo_passages: list[dict] = []
_demo_reflections: list[dict] = []
_demo_reactions: list[dict] = []


def _demo_mode() -> bool:
    return sb is None


def _demo_member(
    line_user_id: str,
    group_id: str | None,
    *,
    is_leader: bool = False,
    is_muted: bool = False,
    display_name: str = "",
    nickname: str | None = None,
) -> dict:
    return {
        "id": f"demo-{line_user_id}",
        "line_user_id": line_user_id,
        "group_id": group_id,
        "is_leader": is_leader,
        "is_muted": is_muted,
        "display_name": display_name,
        "nickname": nickname,
    }


def _find_demo_passage(group_id: str, passage_date: str) -> dict | None:
    return next(
        (p for p in _demo_passages if p["group_id"] == group_id and p["passage_date"] == passage_date), None
    )


def seed_demo_data() -> None:
    """本機快速預覽用：灌一組示範小組＋一段範例經文＋幾則示範領受，讓人一打開就看得到
    畫面長什麼樣。只在記憶體示範模式（沒接 Supabase）時有效果，正式站接了 Supabase
    之後這個函式不會做任何事。
    """
    global _demo_groups, _demo_members, _demo_passages, _demo_reflections, _demo_reactions
    if not _demo_mode():
        return

    _demo_groups = {_DEMO_GROUP_ID: {"id": _DEMO_GROUP_ID, "name": DEFAULT_GROUP_NAME, "join_code": "DEMO01"}}
    # 常用的測試身分（本機 /dev/login、pytest 直接注入 session 的那些人）預設就已經在
    # 示範小組裡，這樣既有流程不用每次都先走一次 onboarding。真正沒加入過的新 line id
    # （不在這份名單裡）get_member_by_line_id 會回 None → 被導去 /onboarding。
    _demo_members = {
        "test-user": _demo_member("test-user", _DEMO_GROUP_ID, display_name="測試", nickname="小組員"),
        "test-admin": _demo_member(
            "test-admin", _DEMO_GROUP_ID, is_leader=True, display_name="輔導", nickname="輔導"
        ),
        "dev-user": _demo_member(
            "dev-user", _DEMO_GROUP_ID, is_leader=True, display_name="你（測試用）", nickname="你"
        ),
    }
    _demo_passages = [
        {
            "id": "demo-passage",
            "group_id": _DEMO_GROUP_ID,
            "passage_date": local_time.today().isoformat(),
            "reference": "路加福音 24:13–17 · 以馬忤斯路上",
            "verses": [
                "正當那日，門徒中有兩個人往一個村子去，這村子名叫以馬忤斯，離耶路撒冷約有二十五里。",
                "他們彼此談論所遇見的這一切事。",
                "正談論相問的時候，耶穌親自就近他們，和他們同行。",
                "只是他們的眼睛迷糊了，不認得他。",
                "耶穌對他們說，你們走路彼此談論的是什麼事呢，你們為什麼愁容滿面呢。",
            ],
            "verse_labels": ["24:13", "24:14", "24:15", "24:16", "24:17"],
            "guiding_question": DEFAULT_GUIDING_QUESTION,
        }
    ]
    _demo_reflections = [
        {
            "id": str(uuid.uuid4()),
            "passage_id": "demo-passage",
            "member_id": "demo-思彤",
            "name": "思彤",
            "verse_indexes": [3],
            "note": "我也覺得自己常常認不出，神其實已經在旁邊很久了。",
            "kind": "flower",
            "color": "#E8A98A",
        },
        {
            "id": str(uuid.uuid4()),
            "passage_id": "demo-passage",
            "member_id": "demo-柏睿",
            "name": "柏睿",
            "verse_indexes": [2],
            "note": "",
            "kind": "stone",
            "color": "#A6A08C",
        },
        {
            "id": str(uuid.uuid4()),
            "passage_id": "demo-passage",
            "member_id": "demo-瑀彤",
            "name": "瑀彤",
            "verse_indexes": [4, 3],
            "note": "這句戳到我，這禮拜真的很低落，但原來耶穌會直接問。",
            "kind": "butterfly",
            "color": "#9FB3D9",
        },
        {
            "id": str(uuid.uuid4()),
            "passage_id": "demo-passage",
            "member_id": "demo-柏諺",
            "name": "柏諺",
            "verse_indexes": [0],
            "note": "",
            "kind": "fruit",
            "color": "#E2916A",
        },
    ]
    _demo_reactions = []


if _demo_mode() and os.environ.get("SEED_DEMO_DATA", "1") != "0":
    seed_demo_data()


def _bloom_color_for(member_id: str) -> str:
    return _BLOOM_COLORS[hash(member_id) % len(_BLOOM_COLORS)]


def _upsert_with_fallback(table: str, payload: dict | list[dict], on_conflict: str, optional_keys: list[str]):
    """先整包 upsert；Railway 部署程式碼是即時的，但 Supabase 的欄位要手動到 SQL
    Editor 跑 migration 才會加上去，兩邊不會同時發生——如果失敗是因為 optional_keys
    裡的欄位還沒手動加到資料庫，就把那些欄位拿掉重試一次，退化成沒有新欄位的舊行為，
    好過讓「留下我的領受」這種核心流程直接 500。payload 可以是單筆或批次的一串。
    """
    try:
        return sb.table(table).upsert(payload, on_conflict=on_conflict).execute()
    except Exception as exc:  # noqa: BLE001 - 只在明確是「欄位不存在」時重試，其他錯誤照樣往外丟
        # PostgREST 找不到欄位的實際錯誤長這樣（用真的請求驗證過，不是猜的）：
        # code='PGRST204', message="Could not find the 'xxx' column of 'table' in the schema cache"
        message = getattr(exc, "message", None) or str(exc)
        code = getattr(exc, "code", None)
        missing = [k for k in optional_keys if f"'{k}'" in message]
        if not (code == "PGRST204" and missing):
            raise

        def _trim(row: dict) -> dict:
            return {k: v for k, v in row.items() if k not in missing}

        trimmed = [_trim(row) for row in payload] if isinstance(payload, list) else _trim(payload)
        return sb.table(table).upsert(trimmed, on_conflict=on_conflict).execute()


def _insert_reflection_with_fallback(payload: dict):
    """留一則新的領受。跟 _upsert_with_fallback 一樣，欄位還沒手動加好就拿掉重試。

    另外處理一種過渡狀態：如果「拿掉 (passage_id, member_id) 唯一限制」那個 migration
    還沒手動跑過，資料庫還是只准一人一段經文一則，這裡 insert 第二則會被舊限制擋下來
    （code 23505 unique_violation）——退化成 upsert（蓋掉舊的那一則），好過整個請求
    500；等 migration 真的跑過，才會變成真正可以留好幾則不同時間點的領受。
    """
    optional_keys = ["verse_indexes"]
    try:
        return sb.table("reflections").insert(payload).execute()
    except Exception as exc:  # noqa: BLE001 - 只在明確認得出的錯誤才重試，其他錯誤照樣往外丟
        message = getattr(exc, "message", None) or str(exc)
        code = getattr(exc, "code", None)

        if code == "PGRST204":
            missing = [k for k in optional_keys if f"'{k}'" in message]
            if not missing:
                raise
            trimmed = {k: v for k, v in payload.items() if k not in missing}
            return _insert_reflection_with_fallback(trimmed)

        if code == "23505":
            return sb.table("reflections").upsert(payload, on_conflict="passage_id,member_id").execute()

        raise


# ---------- group（多小組：每個人屬於一組，靠加入碼加入／建立） ----------


def get_group(group_id: str | None) -> dict | None:
    if not group_id:
        return None
    if _demo_mode():
        return _demo_groups.get(group_id)
    result = sb.table("groups").select("*").eq("id", group_id).limit(1).execute()
    return result.data[0] if result.data else None


def get_group_by_code(code: str) -> dict | None:
    """用加入碼找小組，找不到回 None。加入碼一律轉大寫比對。"""
    code = (code or "").strip().upper()
    if not code:
        return None
    if _demo_mode():
        return next((g for g in _demo_groups.values() if (g.get("join_code") or "").upper() == code), None)
    result = sb.table("groups").select("*").eq("join_code", code).limit(1).execute()
    return result.data[0] if result.data else None


def _set_demo_member_group(member_id: str, group_id: str, *, is_leader: bool) -> None:
    for m in _demo_members.values():
        if m["id"] == member_id:
            m["group_id"] = group_id
            m["is_leader"] = is_leader
            return


def create_group(name: str, member_id: str) -> dict:
    """建一個新小組：建立者自動成為這一組的輔導（is_leader）。任何登入的人都能自助建組。
    回傳新建立的 group（含加入碼，可以分享給組員）。"""
    name = (name or "").strip() or DEFAULT_GROUP_NAME

    if _demo_mode():
        group_id = f"demo-group-{uuid.uuid4().hex[:8]}"
        _demo_groups[group_id] = {"id": group_id, "name": name, "join_code": _generate_join_code()}
        _set_demo_member_group(member_id, group_id, is_leader=True)
        return _demo_groups[group_id]

    # 產生一組還沒被用過的加入碼（碰撞機率極低，重試幾次就夠）。
    code = _generate_join_code()
    for _ in range(10):
        if not get_group_by_code(code):
            break
        code = _generate_join_code()
    created = sb.table("groups").insert({"name": name, "join_code": code}).execute()
    group = created.data[0]
    sb.table("members").update({"group_id": group["id"], "is_leader": True}).eq("id", member_id).execute()
    return group


def ensure_join_code(group_id: str) -> dict | None:
    """拿一組的資料，順便確保它有加入碼。舊的小組（加入碼這個欄位加上去之前就存在的，
    例如一開始那組「恩典少年」）沒有加入碼，這裡在輔導第一次打開後台時就地補一組、
    存回資料庫——不用任何人去 Supabase 跑 SQL，輔導根本不需要知道資料庫是什麼。

    唯一還是需要開發者手動做一次的，是「把 join_code 這個欄位加進資料表」那一步 DDL
    （欄位不存在就沒地方存值）；欄位加好之後，值一律由程式自動補，不再需要人工。"""
    group = get_group(group_id)
    if not group or group.get("join_code"):
        return group

    # 補一組還沒被用過的加入碼。
    code = _generate_join_code()
    for _ in range(10):
        if not get_group_by_code(code):
            break
        code = _generate_join_code()

    if _demo_mode():
        group["join_code"] = code  # get_group 回的就是 _demo_groups 裡的同一個 dict
        return group

    try:
        result = sb.table("groups").update({"join_code": code}).eq("id", group_id).execute()
        return result.data[0] if result.data else {**group, "join_code": code}
    except Exception as exc:  # noqa: BLE001 - join_code 欄位還沒加（migration 沒跑）就安靜退回
        message = getattr(exc, "message", None) or str(exc)
        if getattr(exc, "code", None) == "PGRST204" and "join_code" in message:
            return group  # 欄位還不存在，維持沒有加入碼；這是開發者要補的一步，不是輔導
        raise


def rename_group(group_id: str, name: str) -> None:
    """輔導改自己這一組的名字（開組之後也能改）。空字串忽略，不會把組名清成空白。"""
    name = (name or "").strip()
    if not group_id or not name:
        return
    if _demo_mode():
        group = _demo_groups.get(group_id)
        if group:
            group["name"] = name
        return
    sb.table("groups").update({"name": name}).eq("id", group_id).execute()


def join_group_by_code(member_id: str, code: str) -> dict | None:
    """用加入碼加入既有小組（加入的人是一般成員，不是輔導）。加入碼找不到回 None。"""
    group = get_group_by_code(code)
    if not group:
        return None

    if _demo_mode():
        _set_demo_member_group(member_id, group["id"], is_leader=False)
        return group

    sb.table("members").update({"group_id": group["id"], "is_leader": False}).eq("id", member_id).execute()
    return group


# ---------- members ----------


def upsert_member(user: dict) -> dict:
    """LINE 登入成功後呼叫：把這個人存進成員名單（已存在就更新基本資料）。
    刻意不在這裡指定 group_id——剛登入的新成員 group_id 是 null，之後在 /onboarding
    自己選「用加入碼加入」或「建一個新組」才會有值；回頭登入的舊成員則保留原本的 group_id
    （upsert 沒把 group_id 列進去，衝突更新時不會被蓋掉）。"""
    if _demo_mode():
        line_user_id = user["line_user_id"]
        existing = _demo_members.get(line_user_id)
        if existing:
            existing["display_name"] = user.get("display_name") or existing.get("display_name") or ""
            return existing
        member = _demo_member(line_user_id, None, display_name=user.get("display_name") or "")
        _demo_members[line_user_id] = member
        return member

    result = (
        sb.table("members")
        .upsert(
            {
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
        return _demo_members.get(line_user_id)

    result = sb.table("members").select("*").eq("line_user_id", line_user_id).limit(1).execute()
    return result.data[0] if result.data else None


def list_members(group_id: str) -> list[dict]:
    """某一組的所有成員，管理輔導名單／禁言用。只列出這一組的人（多小組隔離：
    輔導只看得到、也只管得到自己這一組的成員）。"""
    if not group_id:
        return []
    if _demo_mode():
        return [m for m in _demo_members.values() if m.get("group_id") == group_id]

    result = sb.table("members").select("*").eq("group_id", group_id).order("created_at").execute()
    return result.data


def set_member_leader(member_id: str, is_leader: bool, group_id: str | None = None) -> None:
    """把某個成員設成／取消輔導。傳 group_id 就一起篩，確保只能改到自己這一組的成員
    （多小組隔離：A 組輔導不能去改 B 組的人）。"""
    if _demo_mode():
        for m in _demo_members.values():
            if m["id"] == member_id and (group_id is None or m.get("group_id") == group_id):
                m["is_leader"] = is_leader
        return
    query = sb.table("members").update({"is_leader": is_leader}).eq("id", member_id)
    if group_id is not None:
        query = query.eq("group_id", group_id)
    query.execute()


def set_member_muted(member_id: str, is_muted: bool, group_id: str | None = None) -> None:
    """禁言：不是封鎖帳號，還是能登入、能讀、能看動態牆，只是不能再留新的領受
    （也不能編輯舊的）。各組輔導可以禁言自己組內的成員（平台方不可能一個人管所有組），
    傳 group_id 就一起篩，確保只動得到自己這一組的人。"""
    if _demo_mode():
        for m in _demo_members.values():
            if m["id"] == member_id and (group_id is None or m.get("group_id") == group_id):
                m["is_muted"] = is_muted
        return
    try:
        query = sb.table("members").update({"is_muted": is_muted}).eq("id", member_id)
        if group_id is not None:
            query = query.eq("group_id", group_id)
        query.execute()
    except Exception as exc:  # noqa: BLE001 - 只在明確是「欄位不存在」時安靜放棄
        message = getattr(exc, "message", None) or str(exc)
        if getattr(exc, "code", None) == "PGRST204" and "'is_muted'" in message:
            return
        raise


def set_nickname(member_id: str, nickname: str) -> None:
    """設定自己的暱稱，不是本名也可以。留空（傳空字串）就退回顯示 LINE 的名字。"""
    if _demo_mode():
        return
    sb.table("members").update({"nickname": nickname or None}).eq("id", member_id).execute()


def _display_name(member_row: dict | None) -> str:
    if not member_row:
        return "小夥伴"
    return member_row.get("nickname") or member_row.get("display_name") or "小夥伴"


# ---------- 今天這段經文 ----------


def get_today_passage(group_id: str) -> dict | None:
    """回傳某一組今天這段經文；如果這組今天還沒有輔導排經文（或還沒選組），回傳 None。
    多小組隔離：一定要指定是哪一組，不會有「全站共用的今天」。"""
    if not group_id:
        return None
    today = local_time.today().isoformat()
    if _demo_mode():
        passage = _find_demo_passage(group_id, today)
        return _resolve_guiding_question(passage) if passage else None

    result = (
        sb.table("daily_passages")
        .select("*")
        .eq("group_id", group_id)
        .eq("passage_date", today)
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

    if not _demo_mode():
        sb.table("daily_passages").update({"guiding_question": question}).eq("id", passage["id"]).execute()

    return passage


def set_passage_for_date(
    passage_date: str,
    reference: str,
    verses: list[str],
    guiding_question: str,
    leader_member_id: str,
    group_id: str,
    verse_labels: list[str] | None = None,
) -> dict:
    """排定某一組某一天的經文（不限今天，讓輔導可以一次排好接下來好幾天）。
    已經排過同一組同一天就更新，不會重複長出第二筆。
    引導問題留空就先存空的，等真的被打開那天再生（見 _resolve_guiding_question）。
    verse_labels 是每一句對應的節號（像 '9:13'），畫面上經文前面顯示節號用；
    手動貼經文那條路沒有節號可以配，留 None 就好，畫面上就不顯示節號。
    """
    payload = {
        "passage_date": passage_date,
        "reference": reference,
        "verses": verses,
        "verse_labels": verse_labels,
        "guiding_question": guiding_question,
        "created_by": leader_member_id,
    }

    if _demo_mode():
        global _demo_reflections
        existing = _find_demo_passage(group_id, passage_date)
        passage_id = existing["id"] if existing else f"demo-passage-{uuid.uuid4().hex[:8]}"
        # 換了一段新的經文，原本那批領受不該掛在新的一段底下。
        if existing and existing.get("reference") != reference:
            _demo_reflections = [r for r in _demo_reflections if r.get("passage_id") != passage_id]
        new_passage = {"id": passage_id, "group_id": group_id, **payload}
        if existing:
            _demo_passages[_demo_passages.index(existing)] = new_passage
        else:
            _demo_passages.append(new_passage)
        return new_passage

    payload["group_id"] = group_id
    result = _upsert_with_fallback(
        "daily_passages", payload, on_conflict="group_id,passage_date", optional_keys=["verse_labels"]
    )
    return result.data[0]


def set_today_passage(
    reference: str,
    verses: list[str],
    guiding_question: str,
    leader_member_id: str,
    group_id: str,
    verse_labels: list[str] | None = None,
) -> dict:
    """輔導種頭香：排定今天這段經文。"""
    return set_passage_for_date(
        local_time.today().isoformat(),
        reference,
        verses,
        guiding_question,
        leader_member_id,
        group_id,
        verse_labels=verse_labels,
    )


def import_passages(rows: list[dict], leader_member_id: str, group_id: str) -> tuple[int, list[str]]:
    """批次排經文：每一列 {date, reference, verses, verse_labels, guiding_question}。
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
                    row["date"],
                    row["reference"],
                    row["verses"],
                    row.get("guiding_question", ""),
                    leader_member_id,
                    group_id,
                    verse_labels=row.get("verse_labels"),
                )
                ok += 1
            except Exception as exc:  # noqa: BLE001 - 示範模式下單一列壞掉不能拖垮整批
                errors.append(f"{row.get('date', '?')}：{exc}")
        return ok, errors

    payloads = [
        {
            "group_id": group_id,
            "passage_date": row["date"],
            "reference": row["reference"],
            "verses": row["verses"],
            "verse_labels": row.get("verse_labels"),
            "guiding_question": row.get("guiding_question", ""),
            "created_by": leader_member_id,
        }
        for row in rows
    ]

    try:
        _upsert_with_fallback(
            "daily_passages", payloads, on_conflict="group_id,passage_date", optional_keys=["verse_labels"]
        )
        return len(payloads), []
    except Exception as exc:  # noqa: BLE001 - 整批寫入失敗，回報給使用者，不能讓網站 500
        return 0, [f"批次寫入資料庫失敗：{exc}"]


# ---------- 回顧（往回看排過的日子，不是往前排） ----------


def list_passage_dates(start_date: str, end_date: str, group_id: str) -> set[str]:
    """某一組在某個日期範圍內排過經文的日期，畫回顧月曆用——知道哪幾天可以點進去。
    只看這一組排過的日子（多小組隔離）。"""
    if not group_id:
        return set()
    if _demo_mode():
        return {
            p["passage_date"]
            for p in _demo_passages
            if p["group_id"] == group_id and start_date <= p["passage_date"] <= end_date
        }

    result = (
        sb.table("daily_passages")
        .select("passage_date")
        .eq("group_id", group_id)
        .gte("passage_date", start_date)
        .lte("passage_date", end_date)
        .execute()
    )
    return {row["passage_date"] for row in result.data}


def get_passage_by_date(passage_date: str, group_id: str) -> dict | None:
    """回顧用：拿某一組某一天排定的經文（不限今天），沒排過就回 None。
    故意不呼叫 AI 補引導問題——回顧是隨手往回翻，不該在瀏覽當下才觸發生成。
    """
    if not group_id:
        return None
    if _demo_mode():
        return _find_demo_passage(group_id, passage_date)

    result = (
        sb.table("daily_passages")
        .select("*")
        .eq("group_id", group_id)
        .eq("passage_date", passage_date)
        .limit(1)
        .execute()
    )
    return result.data[0] if result.data else None


# ---------- 領受 ----------


def get_reflections(passage_id: str, my_member_id: str | None = None, sort: str = "asc") -> list[dict]:
    """回傳這段經文下所有人的領受，附上 mine（是不是目前這個人自己留的）。
    sort 只有時間新舊兩種（'asc' 舊到新、'desc' 新到舊）——不是排行榜，
    不會有「誰的領受比較多」這種排序，純粹是瀏覽順序的偏好。
    """
    if _demo_mode():
        # 複製一份，不要讓下面正規化 verse_indexes 的動作改到記憶體示範資料本身。
        # 只回這一段經文底下的領受（用 passage_id 篩），別組的經文自然看不到。
        items = [dict(r) for r in _demo_reflections if r.get("passage_id") == passage_id]
        if sort == "desc":
            items = list(reversed(items))
    else:
        result = (
            sb.table("reflections")
            .select("*, members(display_name, nickname)")
            .eq("passage_id", passage_id)
            .order("created_at", desc=(sort == "desc"))
            .execute()
        )
        items = [
            {
                "id": r["id"],
                "member_id": r["member_id"],
                "name": _display_name(r.get("members")),
                # verse_indexes 是新欄位，可以同時標好幾句；舊資料只有單一 verse_index，
                # 沒有 verse_indexes 的話從舊欄位退回成單一元素的陣列，畫面不用分兩套邏輯。
                "verse_indexes": r.get("verse_indexes") or ([r["verse_index"]] if r.get("verse_index") is not None else []),
                "note": r["note"],
                "kind": r["kind"],
                "color": r["color"],
            }
            for r in result.data
        ]

    for item in items:
        # 一律正規化成 list——「我也讀了」存的是 None，畫面 {% for %} 不能 iterate None。
        if not item.get("verse_indexes"):
            item["verse_indexes"] = []
        item["mine"] = my_member_id is not None and item["member_id"] == my_member_id
    return items


def _shape_verse_indexes(row: dict) -> list[int]:
    """新欄位 verse_indexes 優先，沒有就從舊的單一 verse_index 退回成單元素陣列。"""
    return row.get("verse_indexes") or ([row["verse_index"]] if row.get("verse_index") is not None else [])


def get_my_reflections(member_id: str, sort: str = "desc") -> list[dict]:
    """某個人自己留過的所有領受（跨所有經文），每一則都附上當時是哪一段經文。
    給「我的領受」個人回顧頁用——不用一天一天點日曆翻。
    """
    if member_id is None:
        return []

    if _demo_mode():
        by_id = {p["id"]: p for p in _demo_passages}
        mine = [r for r in _demo_reflections if r["member_id"] == member_id]
        items = []
        for r in mine:
            p = by_id.get(r.get("passage_id"), {})
            items.append(
                {
                    "id": r["id"],
                    "passage_id": p.get("id"),
                    "passage_date": p.get("passage_date") or local_time.today().isoformat(),
                    "reference": p.get("reference", ""),
                    "verses": p.get("verses", []),
                    "verse_labels": p.get("verse_labels"),
                    "verse_indexes": r.get("verse_indexes") or [],
                    "note": r.get("note", ""),
                    "kind": r.get("kind", "flower"),
                    "color": r.get("color", "#EFC26B"),
                }
            )
        if sort == "desc":
            items.reverse()
        return items

    # 一次把當時那段經文一起帶出來（reflections.passage_id → daily_passages）。
    result = (
        sb.table("reflections")
        .select("*, daily_passages(id, passage_date, reference, verses, verse_labels)")
        .eq("member_id", member_id)
        .order("created_at", desc=(sort == "desc"))
        .execute()
    )
    items = []
    for r in result.data:
        p = r.get("daily_passages") or {}
        items.append(
            {
                "id": r["id"],
                "passage_id": p.get("id"),
                "passage_date": p.get("passage_date"),
                "reference": p.get("reference", ""),
                "verses": p.get("verses", []),
                "verse_labels": p.get("verse_labels"),
                "verse_indexes": _shape_verse_indexes(r),
                "note": r.get("note", ""),
                "kind": r.get("kind", "flower"),
                "color": r.get("color", "#EFC26B"),
            }
        )
    return items


def get_reflection_by_id(reflection_id: str, group_id: str | None = None) -> dict | None:
    """編輯領受用：拿單一則領受的原始資料（不含 name/mine 這些畫面加工過的欄位）。
    傳 group_id 就順便擋掉跨組存取——這則領受所屬的那段經文如果不是這一組的，回 None，
    就算有人拿別組的 reflection_id 直接打網址也讀不到（多小組隔離）。"""
    if _demo_mode():
        reflection = next((r for r in _demo_reflections if r["id"] == reflection_id), None)
    else:
        result = sb.table("reflections").select("*").eq("id", reflection_id).limit(1).execute()
        reflection = result.data[0] if result.data else None

    if reflection and group_id is not None:
        if get_passage_by_id(reflection.get("passage_id"), group_id) is None:
            return None
    return reflection


def add_my_reflection(passage_id: str, member_id: str, verse_indexes: list[int] | None, note: str) -> dict:
    """留一則新的領受，可以同時針對好幾句經文。同一段經文可以留好幾則不同時間點的
    領受，不會因為留過一次就被鎖住——回頭重讀有新的感動，本來就可以再留一則，
    不是只能編輯同一則（想改舊的那則的話，見 update_reflection）。
    """
    verse_indexes = list(verse_indexes) if verse_indexes else None
    payload = {
        "passage_id": passage_id,
        "member_id": member_id,
        # verse_index（單數）留著給還在用舊欄位的地方相容，只存第一句；
        # verse_indexes（複數）才是完整的選句清單。
        "verse_index": verse_indexes[0] if verse_indexes else None,
        "verse_indexes": verse_indexes,
        "note": note,
        "kind": "flower",
        "color": _bloom_color_for(member_id),
    }

    if _demo_mode():
        reflection = {"id": str(uuid.uuid4()), "name": "你", **payload}
        _demo_reflections.append(reflection)
        return reflection

    result = _insert_reflection_with_fallback(payload)
    return result.data[0]


def update_reflection(reflection_id: str, member_id: str, verse_indexes: list[int] | None, note: str) -> None:
    """編輯自己留過的某一則領受（改內容，不是留新的一則）。用 member_id 一起篩，
    確保只能改到自己那則，就算表單被竄改也一樣。
    """
    verse_indexes = list(verse_indexes) if verse_indexes else None
    payload = {
        "verse_index": verse_indexes[0] if verse_indexes else None,
        "verse_indexes": verse_indexes,
        "note": note,
    }

    if _demo_mode():
        existing = next(
            (r for r in _demo_reflections if r["id"] == reflection_id and r["member_id"] == member_id), None
        )
        if existing:
            existing.update(verse_indexes=verse_indexes, note=note)
        return

    try:
        sb.table("reflections").update(payload).eq("id", reflection_id).eq("member_id", member_id).execute()
    except Exception as exc:  # noqa: BLE001 - 只在明確是「欄位不存在」時重試
        message = getattr(exc, "message", None) or str(exc)
        if getattr(exc, "code", None) != "PGRST204" or "'verse_indexes'" not in message:
            raise
        trimmed = {k: v for k, v in payload.items() if k != "verse_indexes"}
        sb.table("reflections").update(trimmed).eq("id", reflection_id).eq("member_id", member_id).execute()


def delete_reflection(reflection_id: str) -> None:
    """輔導移除一則領受（過激或不當內容）。安靜移除，不公開標記、不通知當事人——
    是牧養上的處理，不是公開的懲罰或公審。"""
    if _demo_mode():
        global _demo_reflections
        _demo_reflections = [r for r in _demo_reflections if r["id"] != reflection_id]
        return
    sb.table("reflections").delete().eq("id", reflection_id).execute()


def delete_own_reflection(reflection_id: str, member_id: str) -> None:
    """本人刪掉自己的領受（寫了後悔的東西可以自己收回）。用 member_id 一起篩，
    就算 reflection_id 被竄改也刪不到別人的那則。"""
    if member_id is None:
        return
    if _demo_mode():
        global _demo_reflections
        _demo_reflections = [
            r for r in _demo_reflections if not (r["id"] == reflection_id and r["member_id"] == member_id)
        ]
        return
    sb.table("reflections").delete().eq("id", reflection_id).eq("member_id", member_id).execute()


# ---------- 反應（對某一則領受的固定反應，不是自由留言） ----------


def set_reaction(reflection_id: str, member_id: str, kind: str | None) -> None:
    """對一則領受留反應，kind 是 REACTION_KINDS 裡的其中一種；kind 是 None
    就是取消（再點一次同一個反應等於取消，呼叫端自己判斷）。一人對一則領受只有
    一種反應，換一種就是蓋掉舊的，不會同時掛好幾個。
    """
    if kind is not None and kind not in REACTION_KINDS:
        return

    if _demo_mode():
        global _demo_reactions
        _demo_reactions = [
            r for r in _demo_reactions if not (r["reflection_id"] == reflection_id and r["member_id"] == member_id)
        ]
        if kind is not None:
            _demo_reactions.append({"id": str(uuid.uuid4()), "reflection_id": reflection_id, "member_id": member_id, "kind": kind})
        return

    try:
        if kind is None:
            sb.table("reflection_reactions").delete().eq("reflection_id", reflection_id).eq(
                "member_id", member_id
            ).execute()
        else:
            sb.table("reflection_reactions").upsert(
                {"reflection_id": reflection_id, "member_id": member_id, "kind": kind},
                on_conflict="reflection_id,member_id",
            ).execute()
    except Exception as exc:  # noqa: BLE001 - migration 還沒跑完就安靜放棄，不要 500
        # PGRST205 = 表還沒建好；23514 = 舊的 CHECK 限制還在、擋掉新加的反應種類
        # （drop constraint 那條 migration 還沒跑）。兩種都是過渡狀態，反應是錦上添花，
        # 放棄這次寫入好過整頁 500——migration 跑完就正常了。
        if getattr(exc, "code", None) not in ("PGRST205", "23514"):
            raise


def get_reactions_for_passage(reflection_ids: list[str], my_member_id: str | None = None) -> dict[str, list[dict]]:
    """回傳 {reflection_id: [反應, ...]}，一次查完整段經文底下所有反應，
    不要每一則領受各自查一次造成 N+1。表還沒建好（migration 還沒跑）就回空的，
    不要讓動態牆整頁掛掉——反應是錦上添花的功能，不該擋住核心的「看領受」。
    """
    if _demo_mode():
        by_reflection: dict[str, list[dict]] = {}
        for r in _demo_reactions:
            if r["reflection_id"] in reflection_ids:
                by_reflection.setdefault(r["reflection_id"], []).append(
                    {**r, "name": "你", "mine": r["member_id"] == my_member_id}
                )
        return by_reflection

    if not reflection_ids:
        return {}
    try:
        result = (
            sb.table("reflection_reactions")
            .select("*, members(display_name, nickname)")
            .in_("reflection_id", reflection_ids)
            .order("created_at")
            .execute()
        )
    except Exception as exc:  # noqa: BLE001
        if getattr(exc, "code", None) == "PGRST205":
            return {}
        raise

    by_reflection: dict[str, list[dict]] = {}
    for r in result.data:
        by_reflection.setdefault(r["reflection_id"], []).append(
            {
                "id": r["id"],
                "member_id": r["member_id"],
                "kind": r["kind"],
                "name": _display_name(r.get("members")),
                "mine": my_member_id is not None and r["member_id"] == my_member_id,
            }
        )
    return by_reflection


def export_passage(passage_id: str) -> dict:
    """Rule 14：一鍵匯出這段經文的所有領受。"""
    return {
        "passage": get_passage_by_id(passage_id),
        "reflections": get_reflections(passage_id),
    }


def get_passage_by_id(passage_id: str, group_id: str | None = None) -> dict | None:
    """用 id 直接拿一段經文（不限今天）——編輯領受、匯出都要知道自己是針對哪一段。
    傳 group_id 就一起比對：這段經文不是這一組的就回 None，擋掉「拿別組的 passage_id
    直接打網址」的跨組存取（多小組隔離）。"""
    if not passage_id:
        return None
    if _demo_mode():
        passage = next((p for p in _demo_passages if p["id"] == passage_id), None)
    else:
        result = sb.table("daily_passages").select("*").eq("id", passage_id).limit(1).execute()
        passage = result.data[0] if result.data else None

    if passage and group_id is not None and passage.get("group_id") != group_id:
        return None
    return passage
