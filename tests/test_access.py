"""登入／權限：誰能進哪裡。"""

from app import _csv_safe, PORTFOLIO_URL


def test_home_requires_login(client):
    r = client.get("/")
    assert r.status_code in (301, 302)
    assert "/login" in r.headers["Location"]


def test_healthz_no_login(client):
    assert client.get("/healthz").data == b"ok"


def test_offline_and_sw_no_login(client):
    assert client.get("/offline").status_code == 200
    sw = client.get("/sw.js")
    assert sw.status_code == 200 and "javascript" in sw.content_type


def test_portfolio_redirects_no_login(client):
    r = client.get("/portfolio")
    assert r.status_code in (301, 302)
    assert r.headers["Location"] == PORTFOLIO_URL


def test_admin_forbidden_for_normal_user(user):
    assert user.get("/admin").status_code == 403
    assert user.get("/admin/leaders").status_code == 403


def test_admin_ok_for_admin(admin):
    assert admin.get("/admin").status_code == 200
    assert admin.get("/admin/leaders").status_code == 200


def test_preview_needs_admin(user):
    r = user.get("/admin/preview", query_string={"book": "詩篇", "range": "23:1"})
    assert r.status_code == 403


def test_mute_needs_env_admin(user, csrf):
    # 一般成員（非永久管理員）不能禁言，就算帶了 csrf 也是 403
    token = csrf(user)
    r = user.post("/admin/leaders/mute", data={"csrf_token": token, "member_id": "x", "is_muted": "1"})
    assert r.status_code == 403


def test_csv_formula_injection_guard():
    assert _csv_safe("=1+1") == "'=1+1"
    assert _csv_safe("+x") == "'+x"
    assert _csv_safe("-x") == "'-x"
    assert _csv_safe("@x") == "'@x"
    assert _csv_safe("正常內容") == "正常內容"
    assert _csv_safe("") == ""
    assert _csv_safe(None) == ""
