"""LINE Login OAuth + 登入狀態管理。

授權碼流程、session 存法沿用天父日記 app.py 裡實際跑得動的寫法
（GROUP-Devotion 開工前確認過：專案簡報提到的 mark_core 共用套件目前
在帳號裡並不存在，兩個姊妹專案也都是各自 ad hoc 接 LINE OAuth，
沒有真的共用套件可以 import——這件事記在 CHANGELOG 跟 README 裡）。

跟姊妹專案不同的地方：這裡多寫了一個 `login_required` decorator
（姊妹專案是每個路由自己寫 `if not require_login(): ...`），因為
GROUP-Devotion 的專案規範明確要求要有這個 decorator。
"""

import os
import secrets
from functools import wraps

import requests
from flask import Blueprint, redirect, render_template, request, session, url_for

LINE_CHANNEL_ID = os.environ.get("LINE_CHANNEL_ID", "")
LINE_CHANNEL_SECRET = os.environ.get("LINE_CHANNEL_SECRET", "")
LINE_REDIRECT_URI = os.environ.get("LINE_REDIRECT_URI", "")
ADMIN_LINE_USER_IDS = {
    uid.strip() for uid in os.environ.get("ADMIN_LINE_USER_IDS", "").split(",") if uid.strip()
}
DEV_MODE = os.environ.get("FLASK_DEBUG", "").strip() == "1"

LINE_AUTH_BASE = "https://access.line.me/oauth2/v2.1/authorize"
LINE_TOKEN_URL = "https://api.line.me/oauth2/v2.1/token"
LINE_PROFILE_URL = "https://api.line.me/v2/profile"

auth_bp = Blueprint("auth", __name__)


def require_login() -> bool:
    return "user" in session


def get_user() -> dict:
    return session.get("user", {})


def is_admin() -> bool:
    uid = get_user().get("line_user_id", "")
    return bool(uid) and uid in ADMIN_LINE_USER_IDS


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not require_login():
            session["login_next"] = request.path
            return redirect(url_for("auth.login"))
        return view(*args, **kwargs)

    return wrapped


def admin_required(view):
    @wraps(view)
    @login_required
    def wrapped(*args, **kwargs):
        if not is_admin():
            return render_template("admin_forbidden.html", user=get_user()), 403
        return view(*args, **kwargs)

    return wrapped


@auth_bp.get("/login")
def login():
    if not (LINE_CHANNEL_ID and LINE_REDIRECT_URI):
        return render_template("login_unavailable.html"), 503

    state = secrets.token_urlsafe(16)
    session["line_state"] = state
    query = (
        "response_type=code"
        f"&client_id={LINE_CHANNEL_ID}"
        f"&redirect_uri={LINE_REDIRECT_URI}"
        f"&state={state}"
        "&scope=profile"
    )
    return redirect(f"{LINE_AUTH_BASE}?{query}")


@auth_bp.get("/line/callback")
def line_callback():
    code = request.args.get("code")
    state = request.args.get("state")
    if not code or state != session.get("line_state"):
        return "登入失敗，狀態不符，請重新登入", 400

    token_res = requests.post(
        LINE_TOKEN_URL,
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": LINE_REDIRECT_URI,
            "client_id": LINE_CHANNEL_ID,
            "client_secret": LINE_CHANNEL_SECRET,
        },
        timeout=20,
    )
    token_res.raise_for_status()
    access_token = token_res.json()["access_token"]

    profile_res = requests.get(
        LINE_PROFILE_URL,
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=20,
    )
    profile_res.raise_for_status()
    profile = profile_res.json()

    user = {
        "line_user_id": profile.get("userId"),
        "display_name": profile.get("displayName") or "",
        "picture_url": profile.get("pictureUrl"),
    }
    session.permanent = True
    session["user"] = user

    from data_store import upsert_member

    upsert_member(user)

    next_url = session.pop("login_next", None)
    return redirect(next_url or url_for("home"))


@auth_bp.get("/logout")
def logout():
    session.clear()
    return redirect(url_for("home"))


if DEV_MODE:

    @auth_bp.get("/dev/login")
    def dev_login():
        """本機測試專用：跳過 LINE，直接假登入。只有 FLASK_DEBUG=1 才會註冊這條路由。"""
        from data_store import upsert_member

        user = {
            "line_user_id": "dev-user",
            "display_name": "你（測試用）",
            "picture_url": None,
        }
        session.permanent = True
        session["user"] = user
        upsert_member(user)
        return redirect(url_for("home"))
