"""後台排經文：經文一律從正版帶出，輔導不能自己打／改字句。"""

import data_store


def test_admin_is_get_only(admin, csrf):
    # 舊的「手動貼經文」自由文字 POST 路徑已經拿掉了（帶 csrf 過關後才會到 405，
    # 證明是「這個路由不收 POST」，不是被 csrf 擋掉）。
    token = csrf(admin)
    assert admin.post("/admin", data={"csrf_token": token}).status_code == 405


def test_no_free_text_verses_field(admin):
    html = admin.get("/admin").data.decode()
    assert 'name="verses"' not in html  # 沒有自由打經文的欄位
    assert 'name="subtitle"' in html  # 只能加主題副標


def test_schedule_by_range_pulls_canonical(admin, csrf):
    token = csrf(admin)
    admin.post(
        "/admin/schedule_by_range",
        data={"csrf_token": token, "book": "路加福音", "range": "24:13-17", "subtitle": "以馬忤斯路上"},
        follow_redirects=True,
    )
    p = data_store.get_today_passage()
    assert p["reference"] == "路加福音 24:13-17 · 以馬忤斯路上"
    assert p["verses"][0].startswith("正當那日")  # 正版和合本，不是輔導打的
    assert p["verse_labels"][0] == "24:13"


def test_schedule_bad_range_reports_error(admin, csrf):
    token = csrf(admin)
    r = admin.post(
        "/admin/schedule_by_range",
        data={"csrf_token": token, "book": "路加福音", "range": "亂打的章節"},
        follow_redirects=False,
    )
    assert r.status_code == 302
    assert "err=" in r.headers["Location"]


def test_preview_valid(admin):
    d = admin.get("/admin/preview", query_string={"book": "詩篇", "range": "23:1-3"}).get_json()
    assert d["ok"] is True
    assert len(d["verses"]) == 3
    assert d["verses"][0]["label"] == "23:1"


def test_preview_invalid(admin):
    d = admin.get("/admin/preview", query_string={"book": "沒有這卷", "range": "1:1"}).get_json()
    assert d["ok"] is False
    assert "error" in d
