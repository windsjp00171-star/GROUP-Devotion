import os
from datetime import date, datetime
import csv
import io
import json

import openpyxl
from dotenv import load_dotenv
from flask import Flask, Response, redirect, render_template, request, url_for

import ai_guide
from auth import auth_bp, admin_required, get_user, is_admin, login_required, require_login
from csrf import csrf_protect, csrf_token
from data_store import (
    add_my_reflection,
    export_passage,
    get_member_by_line_id,
    get_reflections,
    get_today_passage,
    import_passages,
    set_passage_for_date,
    set_today_passage,
)
from plan_import import parse_plan_file
from scripture import BOOK_NAMES, get_scripture

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

    # 「我也讀了」：完全沒標記哪一句，也沒寫字，純粹只是「我在這裡」。
    if request.form.get("read_only") == "1":
        add_my_reflection(passage["id"], _current_member_id(), None, "")
        return redirect(url_for("home"))

    # 沒特別標記哪一句就留 None，不要偷偷歸給第 0 句——
    # 之後在碰撞畫面才不會引用一句他根本沒選的經文。
    verse_index = request.form.get("verse_index", type=int)
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
        # 留空不在這裡打 AI——等真的被打開那天才生一次、存回去（見 data_store._resolve_guiding_question）。
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
        imported=request.args.get("imported"),
        import_errors=request.args.getlist("err"),
        book_names=BOOK_NAMES,
        ai_configured=ai_guide.is_configured(),
        today=date.today().isoformat(),
    )


@app.route("/admin/schedule_by_range", methods=["POST"])
@admin_required
def admin_schedule_by_range():
    passage_date = (request.form.get("date") or date.today().isoformat()).strip()
    book = (request.form.get("book") or "").strip()
    verse_range = (request.form.get("range") or "").strip()

    verses = get_scripture(book, verse_range)
    if not verses:
        return redirect(url_for("admin", saved=0, err=f"找不到「{book} {verse_range}」，檢查一下書卷名稱跟章節格式"))

    reference = f"{book} {verse_range}"
    guiding_question = (request.form.get("guiding_question") or "").strip()
    leader_member_id = _current_member_id()
    passage = set_passage_for_date(passage_date, reference, verses, guiding_question, leader_member_id)

    leader_note = (request.form.get("leader_note") or "").strip()
    if leader_note and passage_date == date.today().isoformat():
        add_my_reflection(passage["id"], leader_member_id, 0, leader_note)

    return redirect(url_for("admin", saved=1))


@app.route("/admin/import", methods=["POST"])
@admin_required
def admin_import():
    file = request.files.get("plan_file")
    if not file or not file.filename:
        return redirect(url_for("admin", saved=0, err="沒有選擇檔案"))

    try:
        rows, parse_errors = parse_plan_file(file.stream)
        # 引導問題留空的列，這裡不打 AI——等那一天真的被打開才生一次、存回去
        # （見 data_store._resolve_guiding_question）。一次匯入好幾天，不該在
        # 同一個請求裡連續打好幾次 AI，那是拖垮 gunicorn worker timeout 的元兇。
        leader_member_id = _current_member_id()
        ok_count, save_errors = import_passages(rows, leader_member_id)
        errors = parse_errors + save_errors
    except Exception as exc:  # noqa: BLE001 - 上傳檔案格式什麼都可能發生，這裡絕不能整頁 500
        return redirect(url_for("admin", saved=0, err=f"匯入失敗：{exc}"))

    return redirect(url_for("admin", imported=ok_count, **({"err": errors} if errors else {})))


@app.route("/admin/template")
@admin_required
def admin_template():
    """下載空白的讀經計畫範本（跟天父日記的 plan.xlsx 同一種欄位）。"""
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.append(["date", "book", "range", "guiding_question"])
    sheet.append(["2026-08-01", "路加福音", "24:13-17", ""])
    sheet.append(["2026-08-02", "路加福音", "24:18-27", ""])

    buf = io.BytesIO()
    workbook.save(buf)
    buf.seek(0)
    return Response(
        buf.read(),
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=plan_template.xlsx"},
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
            verse = data["passage"]["verses"][r["verse_index"]] if r["verse_index"] is not None else ""
            writer.writerow([r["name"], verse, r["note"]])
        return Response(
            buf.getvalue(),
            mimetype="text/csv",
            headers={"Content-Disposition": f"attachment; filename=devotion_{stamp}.csv"},
        )

    if fmt == "html":
        return render_template("offline_reader.html", **data)

    return Response("unsupported export format", status=400)


@app.errorhandler(500)
def handle_server_error(exc):
    """最後一道防線：任何沒被個別路由接住的例外，都顯示暖色系的錯誤頁，
    不要讓使用者看到裸的 Flask 錯誤堆疊。實際錯誤內容還是會印進伺服器 log。"""
    app.logger.exception("Unhandled error: %s", exc)
    return render_template("error.html"), 500


if __name__ == "__main__":
    app.run(debug=os.environ.get("FLASK_DEBUG", "").strip() == "1")
