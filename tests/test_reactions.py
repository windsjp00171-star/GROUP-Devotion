"""反應：固定種類、切換、無效種類擋掉、AJAX 回 JSON。"""

import data_store

NORMAL_MEMBER_ID = "demo-test-user"


def _a_reflection_id():
    return data_store._demo_reflections[0]["id"]


def _my_reactions(rid):
    return [r for r in data_store.get_reactions_for_passage([rid], NORMAL_MEMBER_ID).get(rid, []) if r["mine"]]


def test_set_and_toggle_reaction(user, csrf):
    token = csrf(user)
    rid = _a_reflection_id()
    user.post(f"/reflections/{rid}/react", data={"csrf_token": token, "kind": "resonate"}, follow_redirects=True)
    assert any(r["kind"] == "resonate" for r in _my_reactions(rid))
    # 再送空的 kind = 取消
    user.post(f"/reflections/{rid}/react", data={"csrf_token": token, "kind": ""}, follow_redirects=True)
    assert _my_reactions(rid) == []


def test_switch_reaction_kind(user, csrf):
    token = csrf(user)
    rid = _a_reflection_id()
    user.post(f"/reflections/{rid}/react", data={"csrf_token": token, "kind": "resonate"}, follow_redirects=True)
    user.post(f"/reflections/{rid}/react", data={"csrf_token": token, "kind": "pray"}, follow_redirects=True)
    mine = _my_reactions(rid)
    assert len(mine) == 1 and mine[0]["kind"] == "pray"


def test_invalid_kind_ignored(user, csrf):
    token = csrf(user)
    rid = _a_reflection_id()
    user.post(f"/reflections/{rid}/react", data={"csrf_token": token, "kind": "'; DROP TABLE"}, follow_redirects=True)
    assert _my_reactions(rid) == []


def test_ajax_reaction_returns_json(user, csrf):
    token = csrf(user)
    rid = _a_reflection_id()
    r = user.post(
        f"/reflections/{rid}/react",
        data={"csrf_token": token, "kind": "pray"},
        headers={"X-Requested-With": "XMLHttpRequest"},
    )
    assert r.is_json
    body = r.get_json()
    assert body["my_reaction_kind"] == "pray"
    assert any(x["kind"] == "pray" for x in body["reactions"])
