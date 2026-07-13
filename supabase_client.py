"""Supabase client 初始化。

寫法沿用 bibile-actionbook / tianfu-diary 兩個 repo實際使用的作法：
`create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)`，用 service role key、
只有後端會用到，前端不會直接打 Supabase，所以沒有另外開 anon key。

沒設定環境變數就是 None，呼叫端一律用 `if sb:` 檢查再用——這樣在還沒拿到
Supabase 專案金鑰之前，整個 app 也能先跑在記憶體示範模式。
"""

import os

from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_SERVICE_ROLE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")

sb = (
    create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
    if SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY
    else None
)
