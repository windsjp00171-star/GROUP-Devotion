"""解析輔導上傳的 xlsx 讀經計畫：date / book / range / guiding_question 四欄
（跟天父日記的 plan.xlsx 同一種欄位，方便你把既有的計畫表拿來改一改就能用）。

`guiding_question` 欄位可以留空，留空就在排定的時候用 AI 生一句
（有設定 GROQ_API_KEY / GEMINI_API_KEY / ANTHROPIC_API_KEY 才會生，
都沒設定就退回預設的那句「哪一句話，也讓你想停下腳步？」）。
"""

from datetime import date, datetime

import openpyxl

from scripture import get_scripture

REQUIRED_COLUMNS = {"date", "book", "range"}


def parse_plan_file(file_stream) -> tuple[list[dict], list[str]]:
    """回傳 (可以排的列, 錯誤訊息)。單一列格式不對只跳過那一列，不會擋掉整批。"""
    try:
        workbook = openpyxl.load_workbook(file_stream, data_only=True)
    except Exception as exc:  # noqa: BLE001 - 檔案本身壞掉，整批都不能排
        return [], [f"讀不了這個檔案：{exc}"]

    sheet = workbook.active
    rows_iter = sheet.iter_rows(min_row=1, max_row=1)
    header_row = next(rows_iter, None)
    if header_row is None:
        return [], ["空白檔案，沒有任何欄位"]

    header = [str(cell.value).strip().lower() if cell.value is not None else "" for cell in header_row]
    missing = REQUIRED_COLUMNS - set(header)
    if missing:
        return [], [f"缺少欄位：{'、'.join(sorted(missing))}（需要 date / book / range，guiding_question 選填）"]

    col_index = {name: i for i, name in enumerate(header)}
    rows: list[dict] = []
    errors: list[str] = []

    for row_num, row in enumerate(sheet.iter_rows(min_row=2), start=2):
        values = [cell.value for cell in row]
        if all(v is None or str(v).strip() == "" for v in values):
            continue

        raw_date = values[col_index["date"]]
        book = str(values[col_index["book"]] or "").strip()
        rng = str(values[col_index["range"]] or "").strip()
        guiding_question = ""
        if "guiding_question" in col_index:
            guiding_question = str(values[col_index["guiding_question"]] or "").strip()

        if not raw_date or not book or not rng:
            errors.append(f"第 {row_num} 列缺少 date / book / range，跳過")
            continue

        if isinstance(raw_date, (datetime, date)):
            date_str = raw_date.strftime("%Y-%m-%d")
        else:
            date_str = str(raw_date).strip()

        verses = get_scripture(book, rng)
        if not verses:
            errors.append(f"第 {row_num} 列（{date_str} {book} {rng}）找不到經文，跳過")
            continue

        rows.append(
            {
                "date": date_str,
                "reference": f"{book} {rng}",
                "verses": verses,
                "guiding_question": guiding_question,
            }
        )

    return rows, errors
