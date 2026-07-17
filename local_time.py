"""這個工具服務的是台灣的青少年小組，「今天」要用台北時區算，不能用
伺服器系統時區——部署平台（Railway 等）預設常常是 UTC，比台灣慢 8 小時，
半夜到早上 8 點之間，系統時鐘還停在「昨天」，「今天這段」會整整晚 8 小時
才換過去。
"""

from datetime import date, datetime
from zoneinfo import ZoneInfo

TAIPEI = ZoneInfo("Asia/Taipei")


def today() -> date:
    return datetime.now(TAIPEI).date()
