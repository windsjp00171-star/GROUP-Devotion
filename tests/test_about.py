"""安心使用聲明頁 /about：不用登入就能看（想試用的人先讀完再決定）。"""


def test_about_is_public(client):
    # 完全沒登入也看得到——這樣才能把連結貼出去給還沒登入的人先讀。
    r = client.get("/about")
    assert r.status_code == 200
    body = r.data.decode()
    assert "安心使用聲明" in body
    assert "資安管控" in body


def test_about_reachable_when_logged_in(user):
    assert user.get("/about").status_code == 200
