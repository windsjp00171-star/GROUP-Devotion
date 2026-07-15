"""AI 生成引導問題：給一段經文，生成一句低門檻、非考題、沒有標準答案的引導問題。

Provider 偵測與系統提示語照抄天父日記 app.py 裡驗證過會動的做法（優先 Groq、
沒有就 Gemini、都沒有就 Anthropic），只是天父日記那邊一次生 2-3 題列表，
這裡改成只生一題——接我們畫面上「引導問題」只有一句話的樣子。

三個都沒設定 API key 就直接回傳 None，呼叫端退回預設的引導問題，不會壞掉。

事故記錄：一開始沒設 max_retries/timeout，Groq 被打到 429 之後，SDK 內建的
重試機制會 sleep 等下一次重試，一路睡到超過 gunicorn 的 worker timeout，
被 gunicorn 從外面強制 kill worker（SystemExit），這種來自外部訊號的中斷
不會被任何 try/except 接住，整個 request 直接掛掉。所以這裡每個 client
都關掉 SDK 自己的重試、加短逾時，讓失敗快速回傳，不要用 sleep 卡住 worker。
"""

import os
from typing import List, Optional

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

# 短逾時、不重試——寧可這次沒生出問題、退回預設那句，也不要卡住 gunicorn worker。
_TIMEOUT_SECONDS = 12.0

_groq_client = None
if GROQ_API_KEY:
    try:
        from groq import Groq

        _groq_client = Groq(api_key=GROQ_API_KEY, max_retries=0, timeout=_TIMEOUT_SECONDS)
    except Exception:
        _groq_client = None

_gemini_model = None
if GEMINI_API_KEY:
    try:
        import google.generativeai as genai

        genai.configure(api_key=GEMINI_API_KEY)
        _gemini_model = genai.GenerativeModel("gemini-2.0-flash")
    except Exception:
        _gemini_model = None

_anthropic_client = None
if ANTHROPIC_API_KEY:
    try:
        import anthropic

        _anthropic_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY, max_retries=0, timeout=_TIMEOUT_SECONDS)
    except Exception:
        _anthropic_client = None

SYSTEM_PROMPT = (
    "你是一位陪伴一群學生（國高中到社青）一起靈修的屬靈朋友。"
    "請完全使用繁體中文回答，不可夾雜任何其他語言的文字。"
    "根據下方的經文，提出剛好一個引導問題，幫助這群學生在讀這段經文的時候，"
    "留意到一句也讓自己想停下腳步的話。"
    "問題必須直接根據這段經文的情境，不能是通用問題。"
    "門檻要低到誰都能答，不能是考題、不能有標準答案。"
    "語言要真誠、溫暖，貼近日常生活，不要學術神學術語，也不要刻意迴避靈性的語言。"
    "只輸出這一個問題本身，不加編號、引號或任何其他說明。"
)


def is_configured() -> bool:
    return bool(_groq_client or _gemini_model or _anthropic_client)


def generate_guiding_question(reference: str, verses: List[str]) -> Optional[str]:
    """回傳一句引導問題；沒有設定任何 AI key，或呼叫失敗，回傳 None。"""
    if not verses:
        return None

    content = f"【今天這段】{reference}\n" + "\n".join(verses)

    try:
        if _groq_client:
            resp = _groq_client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": content},
                ],
                max_tokens=120,
            )
            return resp.choices[0].message.content.strip()

        if _gemini_model:
            resp = _gemini_model.generate_content(
                f"{SYSTEM_PROMPT}\n\n{content}",
                request_options={"timeout": _TIMEOUT_SECONDS},
            )
            return resp.text.strip()

        if _anthropic_client:
            resp = _anthropic_client.messages.create(
                model="claude-haiku-4-5",
                max_tokens=120,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": content}],
            )
            return resp.content[0].text.strip()
    except Exception:
        return None

    return None
