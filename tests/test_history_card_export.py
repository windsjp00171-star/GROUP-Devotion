"""回顧、金句圖卡、匯出、其他頁面。"""

import json
import re

import data_store
import local_time

NORMAL_MEMBER_ID = "demo-test-user"


# ---------- 回顧 ----------


def test_history_calendar_ok(user):
    assert user.get("/history").status_code == 200


def test_future_date_blocked(user):
    r = user.get("/history/2099-01-01", follow_redirects=False)
    assert r.status_code == 302
    assert r.headers["Location"].endswith("/history")


def test_today_redirects_home(user):
    today = local_time.today().isoformat()
    r = user.get(f"/history/{today}", follow_redirects=False)
    assert r.status_code == 302
    assert r.headers["Location"].endswith("/")


def test_invalid_date_redirects(user):
    r = user.get("/history/not-a-date", follow_redirects=False)
    assert r.status_code == 302


# ---------- 金句圖卡 ----------


def _my_latest_id():
    mine = [x for x in data_store._demo_reflections if x["member_id"] == NORMAL_MEMBER_ID]
    return mine[-1]["id"]


def test_card_for_own_reflection(user, csrf):
    token = csrf(user)
    user.post(
        "/reflections",
        data={"csrf_token": token, "verse_indexes": "0", "note": "卡片內容測試"},
        follow_redirects=True,
    )
    rid = _my_latest_id()
    r = user.get(f"/reflections/{rid}/card")
    assert r.status_code == 200
    html = r.data.decode()
    assert 'id="card-canvas"' in html and "card.js" in html
    m = re.search(r'card-data" type="application/json">(.*?)</script>', html, re.S)
    payload = json.loads(m.group(1))
    assert payload["note"] == "卡片內容測試"
    assert payload["verse"]  # 有帶出經文


def test_card_ownership_blocked(user):
    others = [x for x in data_store._demo_reflections if x["member_id"] != NORMAL_MEMBER_ID]
    r = user.get(f"/reflections/{others[0]['id']}/card", follow_redirects=False)
    assert r.status_code == 302


def test_card_empty_read_only_redirects(user, csrf):
    token = csrf(user)
    user.post("/reflections", data={"csrf_token": token, "read_only": "1"}, follow_redirects=True)
    rid = _my_latest_id()
    r = user.get(f"/reflections/{rid}/card", follow_redirects=False)
    assert r.status_code == 302


# ---------- 匯出 / 其他頁面 ----------


def test_export_formats(user):
    assert user.get("/export/json").mimetype == "application/json"
    assert "text/csv" in user.get("/export/csv").content_type
    assert user.get("/export/html").status_code == 200


def test_my_reflections_page(user):
    assert user.get("/me").status_code == 200


def test_settings_page(user):
    assert user.get("/settings").status_code == 200
