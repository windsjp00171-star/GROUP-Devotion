"""簡單的 session-based CSRF 保護。

專案規範說 CSRF 要用 mark_core.csrf，但那個套件實際上不存在（見 CHANGELOG、
README 的說明）。這裡先寫一個最小可用的版本：session 存一組 token，表單帶著
送回來，兩邊對不上就擋掉。
"""

import secrets

from flask import abort, request, session


def csrf_token() -> str:
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_urlsafe(32)
    return session["csrf_token"]


def csrf_protect() -> None:
    if request.method != "POST":
        return
    expected = session.get("csrf_token")
    submitted = request.form.get("csrf_token")
    if not expected or not submitted or not secrets.compare_digest(expected, submitted):
        abort(400, "表單過期了，重新整理頁面再試一次")
