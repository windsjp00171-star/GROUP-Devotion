"""留領受：新增、複選、編輯、刪除，以及越權保護。"""

import data_store

# demo 模式下，test-user 這個身分的 member id（見 conftest 的說明）
NORMAL_MEMBER_ID = "demo-test-user"


def _mine():
    return [x for x in data_store._demo_reflections if x["member_id"] == NORMAL_MEMBER_ID]


def _others():
    return [x for x in data_store._demo_reflections if x["member_id"] != NORMAL_MEMBER_ID]


def test_submit_reflection_multi_verse(user, csrf):
    token = csrf(user)
    r = user.post(
        "/reflections",
        data={"csrf_token": token, "verse_indexes": "0,2", "note": "我的測試領受"},
        follow_redirects=True,
    )
    assert r.status_code == 200
    mine = _mine()
    assert mine and mine[-1]["verse_indexes"] == [0, 2]
    assert mine[-1]["note"] == "我的測試領受"


def test_can_leave_multiple_reflections(user, csrf):
    token = csrf(user)
    user.post("/reflections", data={"csrf_token": token, "verse_indexes": "0", "note": "第一則"}, follow_redirects=True)
    user.post("/reflections", data={"csrf_token": token, "verse_indexes": "1", "note": "第二則"}, follow_redirects=True)
    notes = [x["note"] for x in _mine()]
    assert "第一則" in notes and "第二則" in notes


def test_read_only_has_no_verse(user, csrf):
    token = csrf(user)
    user.post("/reflections", data={"csrf_token": token, "read_only": "1"}, follow_redirects=True)
    assert _mine()[-1]["verse_indexes"] in (None, [])


def test_edit_own_reflection(user, csrf):
    token = csrf(user)
    user.post("/reflections", data={"csrf_token": token, "verse_indexes": "1", "note": "原本"}, follow_redirects=True)
    rid = _mine()[-1]["id"]
    user.post(
        f"/reflections/{rid}/edit",
        data={"csrf_token": token, "verse_indexes": "2", "note": "改過"},
        follow_redirects=True,
    )
    assert data_store.get_reflection_by_id(rid)["note"] == "改過"


def test_cannot_edit_others_reflection(user, csrf):
    rid = _others()[0]["id"]
    token = csrf(user)
    r = user.post(
        f"/reflections/{rid}/edit",
        data={"csrf_token": token, "verse_indexes": "0", "note": "我要改別人的"},
        follow_redirects=False,
    )
    assert r.status_code == 302
    assert data_store.get_reflection_by_id(rid)["note"] != "我要改別人的"


def test_delete_own_reflection(user, csrf):
    token = csrf(user)
    user.post("/reflections", data={"csrf_token": token, "note": "要刪的"}, follow_redirects=True)
    rid = _mine()[-1]["id"]
    user.post(f"/reflections/{rid}/remove", data={"csrf_token": token}, follow_redirects=True)
    assert data_store.get_reflection_by_id(rid) is None


def test_cannot_delete_others_reflection(user, csrf):
    rid = _others()[0]["id"]
    token = csrf(user)
    user.post(f"/reflections/{rid}/remove", data={"csrf_token": token}, follow_redirects=True)
    assert data_store.get_reflection_by_id(rid) is not None


def test_post_without_csrf_is_blocked(user):
    r = user.post("/reflections", data={"note": "沒有 csrf"})
    assert r.status_code == 400
