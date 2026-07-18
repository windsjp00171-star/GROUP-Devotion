import os
from calendar import monthrange
from datetime import date, datetime
import csv
import io
import json

import openpyxl
from dotenv import load_dotenv
from flask import Flask, Response, redirect, render_template, request, send_from_directory, url_for

import ai_guide
import local_time
from auth import auth_bp, admin_required, env_admin_required, get_user, is_admin, is_env_admin, login_required, require_login
from csrf import csrf_protect, csrf_token
from data_store import (
    DEFAULT_GUIDING_QUESTION,
    REACTION_KINDS,
    add_my_reflection,
    delete_reflection,
    export_passage,
    get_member_by_line_id,
    get_passage_by_date,
    get_passage_by_id,
    get_reactions_for_passage,
    get_reflection_by_id,
    get_reflections,
    get_today_passage,
    import_passages,
    list_members,
    list_passage_dates,
    set_member_leader,
    set_member_muted,
    set_nickname,
    set_passage_for_date,
    set_reaction,
    set_today_passage,
    update_reflection,
)
from plan_import import parse_plan_file
from scripture import BOOK_NAMES, get_scripture_with_labels, resolve_book_chapter

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
        "current_user_is_env_admin": is_env_admin(get_user().get("line_user_id", "")) if require_login() else False,
        "bible_actionbook_url": BIBLE_ACTIONBOOK_URL,
        "csrf_token": csrf_token,
        "reaction_kinds": REACTION_KINDS,
    }


def _actionbook_deep_link(reference: str) -> str:
    """深度閱讀連結：能配出書卷＋章的話，直接跳到 bible-actionbook 那一章，
    不然退回它的首頁自己選書（例如手動貼經文那條路，reference 是自由格式）。"""
    if not BIBLE_ACTIONBOOK_URL:
        return ""
    resolved = resolve_book_chapter(reference)
    if not resolved:
        return BIBLE_ACTIONBOOK_URL
    book, chapter = resolved
    return f"{BIBLE_ACTIONBOOK_URL.rstrip('/')}/read/{book}/{chapter}"


def _current_member():
    if not require_login():
        return None
    return get_member_by_line_id(get_user()["line_user_id"])


def _current_member_id():
    member = _current_member()
    return member["id"] if member else None


def _current_member_is_muted() -> bool:
    member = _current_member()
    return bool(member and member.get("is_muted"))


def _sort_param() -> str:
    return "desc" if request.args.get("sort") == "desc" else "asc"


def _with_reactions(reflections: list[dict], my_member_id: str | None) -> list[dict]:
    """幫每一則領受附上底下的反應，一次查完不要每一則各自查一次。
    順便算出 my_reaction_kind：我自己對這則領受留了哪一種反應（沒有就是 None），
    畫面上才知道要把哪個反應按鈕畫成「已選」的樣子。
    """
    reactions_by_reflection = get_reactions_for_passage([r["id"] for r in reflections], my_member_id)
    for r in reflections:
        reactions = reactions_by_reflection.get(r["id"], [])
        r["reactions"] = reactions
        mine = next((x for x in reactions if x["mine"]), None)
        r["my_reaction_kind"] = mine["kind"] if mine else None
    return reflections


@app.route("/healthz")
def healthz():
    """部署平台的健康檢查用，刻意不用登入，不碰資料庫。"""
    return "ok"


@app.route("/offline")
def offline():
    """PWA 離線時 service worker 顯示的頁面，不用登入（離線時也不可能驗證）。"""
    return render_template("offline.html")


@app.route("/sw.js")
def service_worker():
    """Service worker 一定要從網站根目錄的路徑提供，不能放在 /static/ 底下——
    瀏覽器預設把 SW 的控制範圍（scope）限制在它所在的資料夾，放在 /static/sw.js
    的話 scope 會變成 /static/，永遠管不到 / 這些真正的頁面，等於整個白做。
    """
    return send_from_directory("static", "sw.js", mimetype="application/javascript")


@app.route("/settings", methods=["GET", "POST"])
@login_required
def settings():
    # 只接受站內相對路徑，避免變成 open redirect。
    next_url = request.values.get("next") or ""
    if next_url and not next_url.startswith("/"):
        next_url = ""

    if request.method == "POST":
        nickname = (request.form.get("nickname") or "").strip()
        set_nickname(_current_member_id(), nickname)
        return redirect(next_url or url_for("settings", saved=1))

    member = get_member_by_line_id(get_user()["line_user_id"]) or {}
    return render_template(
        "settings.html",
        member=member,
        saved=request.args.get("saved") == "1",
        first_login=request.args.get("first") == "1",
        next_url=next_url,
    )


@app.route("/")
@login_required
def home():
    passage = get_today_passage()
    if not passage:
        return render_template("no_passage.html")

    my_member_id = _current_member_id()
    sort = _sort_param()
    reflections = _with_reactions(get_reflections(passage["id"], my_member_id, sort=sort), my_member_id)
    my_reflection_count = sum(1 for r in reflections if r["mine"])

    return render_template(
        "home.html",
        passage=passage,
        verses=list(enumerate(passage["verses"])),
        reflections=reflections,
        my_reflection_count=my_reflection_count,
        sort=sort,
        is_muted=_current_member_is_muted(),
        bible_actionbook_url=_actionbook_deep_link(passage["reference"]),
    )


@app.route("/reflections", methods=["POST"])
@login_required
def submit_reflection():
    # 禁言：不是封鎖帳號，還是能讀、能看動態牆，只是不能再留新的領受——
    # 安靜擋掉，不用一個大大的錯誤頁面告訴他「你被禁言了」。
    if _current_member_is_muted():
        passage_date = request.form.get("passage_date")
        if passage_date:
            return redirect(url_for("history_day", passage_date=passage_date))
        return redirect(url_for("home"))

    # 回顧頁：針對指定（過去）的那一段經文留領受，可以標記好幾句、可以寫字，
    # 跟首頁「留下我的領受」是同一件事——只是忙到今天才回來補，不代表當初沒有真的
    # 停下來讀，回頭補的領受一樣是真的領受。
    passage_id = request.form.get("passage_id")
    if passage_id:
        verse_indexes = [int(x) for x in request.form.get("verse_indexes", "").split(",") if x.strip().isdigit()]
        note = (request.form.get("note") or "").strip()
        add_my_reflection(passage_id, _current_member_id(), verse_indexes, note)
        passage_date = request.form.get("passage_date")
        if passage_date:
            return redirect(url_for("history_day", passage_date=passage_date))
        return redirect(url_for("history"))

    passage = get_today_passage()
    if not passage:
        return redirect(url_for("home"))

    # 「我也讀了」：完全沒標記哪一句，也沒寫字，純粹只是「我在這裡」。
    if request.form.get("read_only") == "1":
        add_my_reflection(passage["id"], _current_member_id(), None, "")
        return redirect(url_for("home"))

    # 沒特別標記哪一句就是空陣列，不要偷偷歸給第 0 句——
    # 動態牆才不會引用一句他根本沒選的經文。可以同時選好幾句，逗號分隔的索引清單。
    verse_indexes = [int(x) for x in request.form.get("verse_indexes", "").split(",") if x.strip().isdigit()]
    note = (request.form.get("note") or "").strip()
    add_my_reflection(passage["id"], _current_member_id(), verse_indexes, note)
    return redirect(url_for("home"))


@app.route("/reflections/<reflection_id>/delete", methods=["POST"])
@admin_required
def admin_delete_reflection(reflection_id):
    """輔導移除過激或不當的領受。安靜移除，不公開標記、不通知當事人——
    這是牧養上的處理，不是公開的懲罰或公審。"""
    delete_reflection(reflection_id)
    next_url = request.form.get("next") or ""
    if next_url.startswith("/"):
        return redirect(next_url)
    return redirect(url_for("home"))


@app.route("/reflections/<reflection_id>/react", methods=["POST"])
@login_required
def submit_reaction(reflection_id):
    """對一則領受留固定反應（不是自由留言）。再點一次已經留過的那個反應就是取消。"""
    kind = request.form.get("kind") or None
    set_reaction(reflection_id, _current_member_id(), kind)
    next_url = request.form.get("next") or ""
    if next_url.startswith("/"):
        return redirect(next_url)
    return redirect(url_for("home"))


@app.route("/reflections/<reflection_id>/edit", methods=["GET", "POST"])
@login_required
def edit_reflection(reflection_id):
    """改自己留過的某一則領受，不是留新的一則——想留新的一則就直接在首頁／回顧
    再送出一次表單，同一段經文本來就可以留好幾則。"""
    reflection = get_reflection_by_id(reflection_id)
    my_member_id = _current_member_id()
    if not reflection or reflection.get("member_id") != my_member_id:
        return redirect(url_for("home"))

    # 禁言的人不能編輯舊的領受，不然等於繞過禁言直接改內容——GET／POST 都擋，
    # 不要讓他打開編輯頁打了字送出才發現沒用。
    if _current_member_is_muted():
        return redirect(url_for("home"))

    passage = get_passage_by_id(reflection["passage_id"])
    if not passage:
        return redirect(url_for("home"))

    next_url = request.values.get("next") or ""
    if next_url and not next_url.startswith("/"):
        next_url = ""

    if request.method == "POST":
        verse_indexes = [int(x) for x in request.form.get("verse_indexes", "").split(",") if x.strip().isdigit()]
        note = (request.form.get("note") or "").strip()
        update_reflection(reflection_id, my_member_id, verse_indexes, note)
        return redirect(next_url or url_for("home"))

    # 舊資料只有單一 verse_index，跟 get_reflections 一樣的退回邏輯。
    verse_indexes = reflection.get("verse_indexes") or (
        [reflection["verse_index"]] if reflection.get("verse_index") is not None else []
    )
    reflection = {**reflection, "verse_indexes": verse_indexes}
    selected_text = "／".join(passage["verses"][i] for i in verse_indexes if i < len(passage["verses"]))

    return render_template(
        "edit_reflection.html",
        reflection=reflection,
        passage=passage,
        verses=list(enumerate(passage["verses"])),
        selected_text=selected_text,
        next_url=next_url,
    )


@app.route("/history")
@login_required
def history():
    """回顧：往回翻小組排過的日子，不是完成率月曆——格子只用來導覽，
    不會標記「你今天有沒有寫」，每個人看到的每一格意義都一樣。"""
    today = local_time.today()
    year = request.args.get("year", type=int) or today.year
    month = request.args.get("month", type=int) or today.month

    # 不能滑到「今天所在月份」之後——回顧是往回看，還沒發生的排程不該在這裡看到。
    if (year, month) > (today.year, today.month):
        year, month = today.year, today.month

    first_weekday, days_in_month = monthrange(year, month)  # monthrange: 星期一 = 0
    start_date = date(year, month, 1).isoformat()
    end_date = date(year, month, days_in_month).isoformat()
    scheduled = list_passage_dates(start_date, end_date)

    today_str = today.isoformat()
    leading_blanks = (first_weekday + 1) % 7  # 轉成台灣慣例的星期日排第一欄
    weeks: list[list[dict | None]] = []
    week: list[dict | None] = [None] * leading_blanks
    for day in range(1, days_in_month + 1):
        d = date(year, month, day).isoformat()
        # 同一個月裡，今天之後的日子就算已經排過經文（例如批次匯入先排了下個月），
        # 也不能在回顧點進去——回顧是往回看，不是提前偷看還沒發生的排程。
        has_passage = d in scheduled and d <= today_str
        week.append({"day": day, "date": d, "has_passage": has_passage, "is_today": d == today_str})
        if len(week) == 7:
            weeks.append(week)
            week = []
    if week:
        weeks.append(week + [None] * (7 - len(week)))

    prev_year, prev_month = (year - 1, 12) if month == 1 else (year, month - 1)
    next_year, next_month = (year + 1, 1) if month == 12 else (year, month + 1)

    return render_template(
        "history.html",
        year=year,
        month=month,
        weeks=weeks,
        prev_year=prev_year,
        prev_month=prev_month,
        next_year=next_year,
        next_month=next_month,
        has_next=(year, month) < (today.year, today.month),
    )


@app.route("/history/<passage_date>")
@login_required
def history_day(passage_date):
    try:
        datetime.strptime(passage_date, "%Y-%m-%d")
    except ValueError:
        return redirect(url_for("history"))

    today_str = local_time.today().isoformat()
    # 回顧是往回看，不是提前偷看還沒發生的排程——即使直接打網址帶未來日期也擋掉，
    # 不能只靠月曆畫面沒有連結這件事（那只是不好按到，不是真的擋住）。
    if passage_date > today_str:
        return redirect(url_for("history"))

    # 今天本來就有自己的首頁，不需要在回顧底下長出另一個長得不一樣的「今天」，
    # 兩個網址看到同一天卻不一樣的畫面只會讓人搞混。
    if passage_date == today_str:
        return redirect(url_for("home"))

    passage = get_passage_by_date(passage_date)
    if not passage:
        return redirect(url_for("history"))
    passage = dict(passage)
    passage["guiding_question"] = passage.get("guiding_question") or DEFAULT_GUIDING_QUESTION

    my_member_id = _current_member_id()
    sort = _sort_param()
    reflections = _with_reactions(get_reflections(passage["id"], my_member_id, sort=sort), my_member_id)
    my_reflection_count = sum(1 for r in reflections if r["mine"])

    return render_template(
        "history_day.html",
        passage=passage,
        passage_date=passage_date,
        verses=list(enumerate(passage["verses"])),
        reflections=reflections,
        my_reflection_count=my_reflection_count,
        sort=sort,
        is_muted=_current_member_is_muted(),
        bible_actionbook_url=_actionbook_deep_link(passage["reference"]),
    )


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
            add_my_reflection(passage["id"], leader_member_id, [0], leader_note)

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
        today=local_time.today().isoformat(),
    )


@app.route("/admin/schedule_by_range", methods=["POST"])
@admin_required
def admin_schedule_by_range():
    passage_date = (request.form.get("date") or local_time.today().isoformat()).strip()
    book = (request.form.get("book") or "").strip()
    verse_range = (request.form.get("range") or "").strip()

    labeled = get_scripture_with_labels(book, verse_range)
    if not labeled:
        return redirect(url_for("admin", saved=0, err=f"找不到「{book} {verse_range}」，檢查一下書卷名稱跟章節格式"))
    verse_labels = [label for label, _ in labeled]
    verses = [text for _, text in labeled]

    reference = f"{book} {verse_range}"
    guiding_question = (request.form.get("guiding_question") or "").strip()
    leader_member_id = _current_member_id()
    passage = set_passage_for_date(
        passage_date, reference, verses, guiding_question, leader_member_id, verse_labels=verse_labels
    )

    leader_note = (request.form.get("leader_note") or "").strip()
    if leader_note and passage_date == local_time.today().isoformat():
        add_my_reflection(passage["id"], leader_member_id, [0], leader_note)

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


@app.route("/admin/leaders")
@admin_required
def admin_leaders():
    members = list_members()
    for m in members:
        m["is_env_admin"] = is_env_admin(m["line_user_id"])
    return render_template("admin_leaders.html", members=members, current_member_id=_current_member_id())


@app.route("/admin/leaders/toggle", methods=["POST"])
@admin_required
def admin_toggle_leader():
    member_id = request.form.get("member_id")
    make_leader = request.form.get("is_leader") == "1"
    # 不能改自己：避免手滑把自己踢出去、後台從此進不去。
    if member_id and member_id != _current_member_id():
        set_member_leader(member_id, make_leader)
    return redirect(url_for("admin_leaders"))


@app.route("/admin/leaders/mute", methods=["POST"])
@env_admin_required
def admin_toggle_mute():
    """禁言：只有永久管理員（最高權限）能操作，不是任何一個輔導都可以。
    不是封鎖帳號，禁言的人還是能登入、能讀、能看動態牆，只是不能再留新的領受。"""
    member_id = request.form.get("member_id")
    make_muted = request.form.get("is_muted") == "1"
    if member_id and member_id != _current_member_id():
        set_member_muted(member_id, make_muted)
    return redirect(url_for("admin_leaders"))


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
            verse = "／".join(data["passage"]["verses"][i] for i in r["verse_indexes"])
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
    # threaded=True：本機測試時瀏覽器會同時打好幾個請求（頁面＋CSS＋JS＋
    # service worker），Werkzeug 預設單執行緒會擋到偶爾連線被重置。
    # 正式站是 gunicorn 在跑，不受這個影響，這裡只是讓本機測試穩定一點。
    app.run(debug=os.environ.get("FLASK_DEBUG", "").strip() == "1", threaded=True)
