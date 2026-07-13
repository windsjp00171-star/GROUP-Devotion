import os
from datetime import datetime
import csv
import io
import json

from dotenv import load_dotenv
from flask import Flask, Response, redirect, render_template, request, url_for

from auth import auth_bp, admin_required, get_user, is_admin, login_required, require_login
from csrf import csrf_protect, csrf_token
from data_store import (
    add_my_reflection,
    export_passage,
    get_member_by_line_id,
    get_reflections,
    get_today_passage,
    set_today_passage,
)

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-only-not-for-production")
app.register_blueprint(auth_bp)
app.before_request(csrf_protect)

BIBLE_ACTIONBOOK_URL = os.environ.get("BIBLE_ACTIONBOOK_URL", "")


@app.context_processor
def inject_globals():
    return {
        "current_user": get_user() if require_login() else None,
        "current_user_is_admin": is_admin(),
        "bible_actionbook_url": BIBLE_ACTIONBOOK_URL,
        "csrf_token": csrf_token,
    }


def _current_member_id():
    if not require_login():
        return None
    member = get_member_by_line_id(get_user()["line_user_id"])
    return member["id"] if member else None


@app.route("/healthz")
def healthz():
    """部署平台的健康檢查用，刻意不用登入，不碰資料庫。"""
    return "ok"


@app.route("/")
@login_required
def home():
    passage = get_today_passage()
    if not passage:
        return render_template("no_passage.html")

    my_member_id = _current_member_id()
    mine = next((r for r in get_reflections(passage["id"], my_member_id) if r["mine"]), None)

    return render_template(
        "home.html",
        passage=passage,
        verses=list(enumerate(passage["verses"])),
        submitted=mine is not None,
    )


@app.route("/reflections", methods=["POST"])
@login_required
def submit_reflection():
    passage = get_today_passage()
    if not passage:
        return redirect(url_for("home"))

    verse_index = request.form.get("verse_index", type=int) or 0
    note = (request.form.get("note") or "").strip()
    add_my_reflection(passage["id"], _current_member_id(), verse_index, note)
    return redirect(url_for("home"))


@app.route("/collision")
@login_required
def collision():
    passage = get_today_passage()
    if not passage:
        return render_template("no_passage.html")

    reflections = get_reflections(passage["id"], _current_member_id())
    return render_template("collision.html", passage=passage, reflections=reflections)


@app.route("/admin", methods=["GET", "POST"])
@admin_required
def admin():
    if request.method == "POST":
        reference = (request.form.get("reference") or "").strip()
        verses_raw = request.form.get("verses") or ""
        verses = [line.strip() for line in verses_raw.splitlines() if line.strip()]
        guiding_question = (request.form.get("guiding_question") or "").strip()
        leader_note = (request.form.get("leader_note") or "").strip()

        leader_member_id = _current_member_id()
        passage = set_today_passage(reference, verses, guiding_question, leader_member_id)

        if leader_note:
            add_my_reflection(passage["id"], leader_member_id, 0, leader_note)

        return redirect(url_for("admin", saved=1))

    passage = get_today_passage()
    return render_template(
        "admin.html",
        passage=passage,
        user=get_user(),
        saved=request.args.get("saved") == "1",
    )


@app.route("/export/<fmt>")
@login_required
def export(fmt):
    """Rule 14 數位遺囑模組：一鍵匯出 + 離線閱讀器。"""
    passage = get_today_passage()
    if not passage:
        return Response("今天還沒有經文，沒有東西可以匯出", status=404)

    data = export_passage(passage["id"])
    stamp = datetime.now().strftime("%Y%m%d")

    if fmt == "json":
        body = json.dumps(data, ensure_ascii=False, indent=2)
        return Response(
            body,
            mimetype="application/json",
            headers={"Content-Disposition": f"attachment; filename=devotion_{stamp}.json"},
        )

    if fmt == "csv":
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(["name", "verse", "note"])
        for r in data["reflections"]:
            writer.writerow([r["name"], data["passage"]["verses"][r["verse_index"]], r["note"]])
        return Response(
            buf.getvalue(),
            mimetype="text/csv",
            headers={"Content-Disposition": f"attachment; filename=devotion_{stamp}.csv"},
        )

    if fmt == "html":
        return render_template("offline_reader.html", **data)

    return Response("unsupported export format", status=400)


if __name__ == "__main__":
    app.run(debug=os.environ.get("FLASK_DEBUG", "").strip() == "1")
