# GROUP-Devotion

一個給學青（國高中到社青）的群體共讀靈修工具——團體版的天父日記。

每天小組讀同一段經文，留下一句領受，非同步看見彼此的領受，在小夥伴腳邊長出一叢屬於這個小組的花園。

視覺與互動節奏參考「以馬忤斯路上」原型，但用 Flask + Jinja2 + 純 HTML/CSS 從頭實作，不是原型程式碼的搬移。

## 本地執行

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # 先不填任何值也能跑，見下方「三種執行模式」
python app.py
```

開啟 http://127.0.0.1:5000

### 三種執行模式

這個 app 會自動依照 `.env` 有沒有填值，決定自己跑在哪種模式，不用改程式碼：

1. **完全沒填**：記憶體示範模式。畫面看得到、能點、能留領受，但重啟伺服器資料就重置，也沒有真的 LINE 登入（`/login` 會顯示「尚未設定」）。
2. **本機測試登入**：把 `.env` 的 `FLASK_DEBUG` 設成 `1`，會多開放 `GET /dev/login`——跳過 LINE，直接假登入一個測試用身分，方便本機走完整個「登入 → 排經文 → 留領受」流程。正式站不要開這個。
3. **接了 Supabase／LINE**：`.env` 填了 `SUPABASE_URL` / `SUPABASE_SERVICE_ROLE_KEY` 之後，資料真的存進資料庫；再填 `LINE_CHANNEL_ID` / `LINE_CHANNEL_SECRET` / `LINE_REDIRECT_URI` 之後，`/login` 會是真的 LINE 登入。兩個是分開生效的，只接 Supabase 不接 LINE 也可以先跑。

## 專案結構

```
app.py                    Flask 路由
auth.py                   LINE Login OAuth、@login_required / @admin_required
csrf.py                   最小可用的 session-based CSRF 保護
supabase_client.py        Supabase client 初始化（沒填環境變數就是 None）
data_store.py             資料層：接了 Supabase 存真資料，沒接就退回記憶體示範資料
scripture.py              和合本查詢層：書卷＋章節 → 逐句經文陣列
ai_guide.py                AI 生成引導問題（Groq → Gemini → Anthropic，都沒設定就回 None）
plan_import.py            解析輔導上傳的 xlsx 讀經計畫
scripture/cuv.json         和合本聖經全文（跟天父日記共用同一份資料）
schema.sql                Supabase 資料庫結構
templates/                 Jinja2 樣板
static/css/style.css       視覺樣式（暖色、圓角、無壓力感）
static/js/                 純 JS，只處理畫面上的小互動（標記一句、教學導覽），不是前端框架
```

## 目前做了什麼（第一版範圍）

- 首頁：今天這段經文、可點一句標記、可留一句領受（文字選填，不寫也可以），下面直接接著「同一段路上」——小組每個人在這段經文的領受，不用另外開頁面、不用點開才看得到
- 輔導後台 `/admin`：三種排經文的方式
  - 書卷＋章節（選書卷、填章節，自動從和合本全文帶出經文）
  - 批次匯入 xlsx（跟天父日記的 `plan.xlsx` 同一種欄位：`date / book / range / guiding_question`，一次排好接下來好幾天，`/admin/template` 可下載空白範本）
  - 手動貼經文（沒有這卷書，或想自己改字句時的備案）
  - 引導問題留空會用 AI 生一句（`GROQ_API_KEY` / `GEMINI_API_KEY` / `ANTHROPIC_API_KEY` 擇一設定即可，優先順序 Groq → Gemini → Anthropic）
  - 都可以同時種頭香（留自己的第一句領受，只對「今天」有效）
- LINE Login OAuth 骨架、`@login_required` / `@admin_required`、最小可用的 CSRF 保護
- 首頁「到 bibile-actionbook 深度閱讀這段」連結
- Rule 14 數位遺囑模組起點：一鍵匯出 + 離線閱讀器（見下）
- Rule 15 教學按鈕（右上角「？」）
- Rule 16 CHANGELOG.md

## 關於「沿用 mark_core」：這個套件目前不存在

開工前把 bibile-actionbook、tianfu-diary 兩個姊妹 repo 加進來核對過，專案簡報裡提到的
`mark_core` 共用套件（`supabase_client` / `auth` / `csrf` / `notification_queue` /
`@login_required` / 統一 API 回傳格式）**目前在帳號裡並不存在**，兩個姊妹專案也都是
各自 ad hoc 接 Supabase／LINE，沒有真的共用套件可以 import。細節記在 `CHANGELOG.md`。

這一版的做法：把姊妹專案裡「真的在跑」的模式抄過來（Supabase client 初始化方式、
LINE OAuth 授權碼流程），`@login_required`、CSRF 則是這個專案自己第一次寫出來，
不是「沿用」而是「補上」——之後如果真的要建一個共用套件，這裡會是第一個可以抽出去的地方。

## 資料庫異動（migration）

`schema.sql` 是完整結構，但正式站的資料庫已經在跑，新增欄位要手動補：

```sql
-- 2026-07-16：verse_index 改成可以是 null（「我也讀了」不標記任何一句）
alter table reflections alter column verse_index drop not null;

-- 2026-07-17：members 加 is_leader（後台可以指定誰是輔導）
alter table members add column if not exists is_leader boolean not null default false;

-- 2026-07-17：members 加 nickname（可以設定不是本名的暱稱）
alter table members add column if not exists nickname text;
```

到 Supabase 專案的 SQL Editor 貼上執行一次就好，既有資料不受影響。

## 還沒做的事（卡在需要外部資源，先不做）

- 天父日記的每日經文排程後台，目前是「照做一份自己的」，不是共用同一張表
- 圖鑑系統、多小組、co-op RPG、正式美術素材——這些是北極星文件裡明訂的第二階段，這一版不做

## Rule 14：如果這個服務有一天收掉了

這個工具存的是一整個小組對神的領受，服務停掉不能讓這些記憶跟著蒸發。現在就可以：

1. **一鍵匯出**：開啟 `/export/json` 或 `/export/csv`，下載今天這段經文的所有領受。
2. **離線閱讀器**：開啟 `/export/html`，會產生一頁不需要伺服器、不需要網路就能打開的靜態頁面，另存新檔存到自己電腦就可以。
3. **非技術交接**：只要能打開瀏覽器、能存檔案，不需要懂程式，就能把這些領受留下來、交給下一個接手的人。
