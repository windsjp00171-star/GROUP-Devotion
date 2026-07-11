from datetime import datetime
import csv
import io
import json

from flask import Flask, Response, redirect, render_template, request, url_for

from data_store import (
    add_my_reflection,
    export_reflections,
    get_my_reflection,
    get_reflections,
    get_today_passage,
)

app = Flask(__name__)


@app.route("/")
def home():
    passage = get_today_passage()
    mine = get_my_reflection()
    return render_template(
        "home.html",
        passage=passage,
        verses=list(enumerate(passage["verses"])),
        submitted=mine is not None,
    )


@app.route("/reflections", methods=["POST"])
def submit_reflection():
    verse_index = request.form.get("verse_index", type=int) or 0
    note = (request.form.get("note") or "").strip()
    add_my_reflection(verse_index, note)
    return redirect(url_for("home"))


@app.route("/collision")
def collision():
    passage = get_today_passage()
    return render_template("collision.html", passage=passage, reflections=get_reflections())


@app.route("/export/<fmt>")
def export(fmt):
    """Rule 14 數位遺囑模組起點：一鍵匯出 + 離線閱讀器。"""
    data = export_reflections()
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
    app.run(debug=True)
