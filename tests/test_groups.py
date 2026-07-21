"""最小版多小組（加入碼）：onboarding 流程、每查詢隔離、禁言下放到各組輔導。

這些測試都跑在記憶體示範模式（conftest 強制），不會碰到真實資料庫。
"""

import data_store


def _login(client, line_user_id, display_name="新朋友"):
    """模擬登入：像 line_callback 那樣先 upsert 出一個「還沒選組」的成員，再塞 session。
    （測試直接注入 session，不會走真的 LINE OAuth，所以要自己補這一步。）"""
    data_store.upsert_member(
        {"line_user_id": line_user_id, "display_name": display_name, "picture_url": None}
    )
    with client.session_transaction() as sess:
        sess["user"] = {"line_user_id": line_user_id, "display_name": display_name, "picture_url": None}


def _csrf(client):
    # GET 一個頁面觸發 csrf_token()（沒組的人會被導去 onboarding，一樣會 render 出 token）。
    client.get("/", follow_redirects=True)
    with client.session_transaction() as sess:
        return sess.get("csrf_token")


def _group_id_of(line_user_id):
    return data_store.get_member_by_line_id(line_user_id)["group_id"]


def _make_group(app, line_user_id, name):
    """開一個新 client、登入、建一組，回傳 (client, group_id)。建組的人自動是輔導。"""
    client = app.test_client()
    _login(client, line_user_id)
    token = _csrf(client)
    client.post("/onboarding/create", data={"csrf_token": token, "name": name})
    return client, _group_id_of(line_user_id)


def _make_group_with_passage(app, line_user_id, name, verse_range):
    client, gid = _make_group(app, line_user_id, name)
    token = _csrf(client)
    client.post(
        "/admin/schedule_by_range",
        data={"csrf_token": token, "book": "詩篇", "range": verse_range},
        follow_redirects=True,
    )
    return client, gid


# ---------- onboarding ----------


def test_new_user_without_group_is_sent_to_onboarding(client):
    _login(client, "newbie")
    r = client.get("/", follow_redirects=False)
    assert r.status_code == 302
    assert "/onboarding" in r.headers["Location"]


def test_create_group_makes_you_leader_with_join_code(client):
    _login(client, "founder")
    token = _csrf(client)
    r = client.post("/onboarding/create", data={"csrf_token": token, "name": "週五學青"}, follow_redirects=False)
    assert r.status_code == 302
    member = data_store.get_member_by_line_id("founder")
    assert member["group_id"] is not None
    assert member["is_leader"] is True
    group = data_store.get_group(member["group_id"])
    assert group["name"] == "週五學青"
    assert group["join_code"]  # 有一組加入碼可以分享


def test_join_existing_group_by_code(app):
    _, gid = _make_group(app, "founder2", "組A")
    code = data_store.get_group(gid)["join_code"]

    joiner = app.test_client()
    _login(joiner, "joiner")
    token = _csrf(joiner)
    joiner.post("/onboarding/join", data={"csrf_token": token, "code": code})

    member = data_store.get_member_by_line_id("joiner")
    assert member["group_id"] == gid
    assert member["is_leader"] is False  # 加入的人是一般成員，不是輔導


def test_join_code_is_case_insensitive(app):
    _, gid = _make_group(app, "founder3", "組C")
    code = data_store.get_group(gid)["join_code"]

    joiner = app.test_client()
    _login(joiner, "joiner_lower")
    token = _csrf(joiner)
    joiner.post("/onboarding/join", data={"csrf_token": token, "code": code.lower()})
    assert _group_id_of("joiner_lower") == gid


def test_bad_join_code_stays_groupless(client):
    _login(client, "lost")
    token = _csrf(client)
    r = client.post("/onboarding/join", data={"csrf_token": token, "code": "ZZZZZZ"}, follow_redirects=False)
    assert "/onboarding" in r.headers["Location"]
    assert "err=" in r.headers["Location"]
    assert data_store.get_member_by_line_id("lost")["group_id"] is None


def test_leader_can_rename_own_group(app):
    client, gid = _make_group(app, "renamer", "舊名字")
    token = _csrf(client)
    client.post("/admin/group/rename", data={"csrf_token": token, "name": "週五學青小組"})
    assert data_store.get_group(gid)["name"] == "週五學青小組"


def test_admin_autofills_missing_join_code(app):
    # 模擬「舊的組沒有加入碼」（加入碼欄位加上去之前就存在的組）。
    client, gid = _make_group(app, "codeless", "沒碼組")
    data_store._demo_groups[gid]["join_code"] = None
    # 輔導只是打開後台，程式就自動補一組加入碼，不用去資料庫跑任何東西。
    html = client.get("/admin").data.decode()
    assert data_store.get_group(gid)["join_code"]
    assert "還在設定中" not in html


def test_rename_only_touches_own_group(app):
    ca, gida = _make_group(app, "renameA", "A 的名字")
    _, gidb = _make_group(app, "renameB", "B 的名字")
    token = _csrf(ca)
    ca.post("/admin/group/rename", data={"csrf_token": token, "name": "A 改過了"})
    # A 改名不會動到 B。
    assert data_store.get_group(gida)["name"] == "A 改過了"
    assert data_store.get_group(gidb)["name"] == "B 的名字"


# ---------- 每查詢隔離：A 組看不到 B 組 ----------


def test_groups_do_not_see_each_others_passage(app):
    ca, gida = _make_group_with_passage(app, "leadA", "組A", "23:1-3")
    _, gidb = _make_group_with_passage(app, "leadB", "組B", "1:1-3")

    pa = data_store.get_today_passage(gida)
    pb = data_store.get_today_passage(gidb)
    assert "23:1-3" in pa["reference"]
    assert "1:1-3" in pb["reference"]
    assert pa["id"] != pb["id"]

    # A 的首頁看得到自己那段（詩篇 23），看不到 B 那段（詩篇 1）。
    home = ca.get("/").data.decode()
    assert "詩篇 23:1-3" in home
    assert "詩篇 1:1-3" not in home


def test_cannot_read_other_groups_passage_by_id(app):
    _, gida = _make_group_with_passage(app, "leadA2", "A2", "23:1-3")
    _, gidb = _make_group_with_passage(app, "leadB2", "B2", "1:1-3")
    pb = data_store.get_today_passage(gidb)
    # 拿 B 的 passage_id、帶 A 的 group_id 去查 → 擋掉。
    assert data_store.get_passage_by_id(pb["id"], gida) is None
    # 帶對的 group_id 才拿得到。
    assert data_store.get_passage_by_id(pb["id"], gidb) is not None


def test_cannot_post_reflection_to_other_groups_passage(app):
    ca, _ = _make_group_with_passage(app, "leadA3", "A3", "23:1-3")
    _, gidb = _make_group_with_passage(app, "leadB3", "B3", "1:1-3")
    pb = data_store.get_today_passage(gidb)

    before = len(data_store.get_reflections(pb["id"]))
    token = _csrf(ca)
    ca.post(
        "/reflections",
        data={"csrf_token": token, "passage_id": pb["id"], "verse_indexes": "0", "note": "跨組亂入"},
    )
    after = len(data_store.get_reflections(pb["id"]))
    assert after == before  # A 不能在 B 的經文底下留領受


def test_cannot_react_to_other_groups_reflection(app):
    _, gida = _make_group_with_passage(app, "leadA4", "A4", "23:1-3")
    cb, gidb = _make_group_with_passage(app, "leadB4", "B4", "1:1-3")

    # B 的輔導在自己組留一則領受。
    pb = data_store.get_today_passage(gidb)
    token_b = _csrf(cb)
    cb.post("/reflections", data={"csrf_token": token_b, "verse_indexes": "0", "note": "B 的領受"})
    reflections_b = data_store.get_reflections(pb["id"])
    target = next(r for r in reflections_b if r["note"] == "B 的領受")

    # A 的人試著對 B 的領受留反應 → 擋掉，不會建立反應。
    ca = app.test_client()
    _login(ca, "a4-member")
    code_a = data_store.get_group(gida)["join_code"]
    ta = _csrf(ca)
    ca.post("/onboarding/join", data={"csrf_token": ta, "code": code_a})
    ta = _csrf(ca)
    ca.post(f"/reflections/{target['id']}/react", data={"csrf_token": ta, "kind": "resonate"})

    reactions = data_store.get_reactions_for_passage([target["id"]])
    assert reactions.get(target["id"], []) == []


# ---------- 禁言下放到各組輔導 ----------


def test_group_leader_can_mute_own_member(app):
    cl, gid = _make_group(app, "muteLead", "禁言組")
    code = data_store.get_group(gid)["join_code"]

    cm = app.test_client()
    _login(cm, "mutee")
    tm = _csrf(cm)
    cm.post("/onboarding/join", data={"csrf_token": tm, "code": code})
    mutee_id = data_store.get_member_by_line_id("mutee")["id"]

    tl = _csrf(cl)
    cl.post("/admin/leaders/mute", data={"csrf_token": tl, "member_id": mutee_id, "is_muted": "1"})
    assert data_store.get_member_by_line_id("mutee")["is_muted"] is True


def test_leader_cannot_mute_other_groups_member(app):
    cl, _ = _make_group(app, "leaderX", "X組")
    _, _ = _make_group(app, "leaderY", "Y組")
    victim_id = data_store.get_member_by_line_id("leaderY")["id"]

    tl = _csrf(cl)
    cl.post("/admin/leaders/mute", data={"csrf_token": tl, "member_id": victim_id, "is_muted": "1"})
    # 跨組禁言無效：Y 組的人不會被 X 組輔導禁言。
    assert data_store.get_member_by_line_id("leaderY")["is_muted"] is False
