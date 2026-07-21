"""測試共用設定。

最重要的一件事：這些環境變數一定要在 import app / data_store 之前設好，
把整套測試**強制跑在記憶體示範模式**（SUPABASE_URL 留空 → supabase_client.sb 是 None
→ data_store._demo_mode() 為真）。測試絕對不會連到、也不會寫到真實的 Supabase——
之前手動測試不小心寫進正式站的意外，測試套件從設計上就杜絕掉。
"""

import os

# ⚠️ 一定要在任何 import app 之前設。留空 = 記憶體示範模式，不碰真實資料庫。
os.environ["SUPABASE_URL"] = ""
os.environ["SUPABASE_SERVICE_ROLE_KEY"] = ""
os.environ["LINE_CHANNEL_ID"] = ""
os.environ["LINE_CHANNEL_SECRET"] = ""
os.environ["LINE_REDIRECT_URI"] = ""
# 測試用的永久管理員 LINE id（auth 在 import 當下就讀這個環境變數）。
os.environ["ADMIN_LINE_USER_IDS"] = "test-admin"
os.environ["FLASK_SECRET_KEY"] = "test-secret-key-not-real"
os.environ.pop("FLASK_DEBUG", None)
os.environ.pop("RAILWAY_ENVIRONMENT", None)

import pytest  # noqa: E402

import data_store  # noqa: E402
from app import app as flask_app  # noqa: E402

# demo 模式下 member id 的格式是 f"demo-{line_user_id}"
NORMAL_MEMBER_ID = "demo-test-user"
ADMIN_MEMBER_ID = "demo-test-admin"


@pytest.fixture
def app():
    flask_app.config.update(TESTING=True, SESSION_COOKIE_SECURE=False)
    return flask_app


@pytest.fixture(autouse=True)
def reset_demo():
    """每個測試前重置記憶體示範資料，測試之間互不影響。
    seed_demo_data() 會把 groups / members / passages / reflections / reactions 全部重建。"""
    data_store.seed_demo_data()
    yield


@pytest.fixture
def client(app):
    return app.test_client()


def _login(client, line_user_id, display_name):
    with client.session_transaction() as sess:
        sess["user"] = {"line_user_id": line_user_id, "display_name": display_name, "picture_url": None}


@pytest.fixture
def user(client):
    """已登入的一般成員（member id = NORMAL_MEMBER_ID）。"""
    _login(client, "test-user", "測試")
    return client


@pytest.fixture
def admin(client):
    """已登入的永久管理員（line id 在 ADMIN_LINE_USER_IDS 裡）。"""
    _login(client, "test-admin", "輔導")
    return client


@pytest.fixture
def csrf():
    """回傳一個函式：GET 首頁觸發 csrf_token()，再從 session 讀出 token。"""

    def _csrf(a_client):
        a_client.get("/")
        with a_client.session_transaction() as sess:
            return sess.get("csrf_token")

    return _csrf


@pytest.fixture
def my_member_id():
    return NORMAL_MEMBER_ID
