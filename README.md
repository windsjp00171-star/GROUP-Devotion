# GROUP-Devotion

一個給學青（國高中到社青）的群體共讀靈修工具——團體版的天父日記。

每天小組讀同一段經文，留下一句領受，非同步看見彼此的領受，在小夥伴腳邊長出一叢屬於這個小組的花園。

視覺與互動節奏參考「以馬忤斯路上」原型，但用 Flask + Jinja2 + 純 HTML/CSS 從頭實作，不是原型程式碼的搬移。

## 授權與開源說明

這個專案以 **MIT 授權**開源（見 [`LICENSE`](LICENSE)），歡迎自己架來用、改成自己教會／團契的樣子。幾件想先講清楚的事：

- **這是個人作品／非商業專案**：不賣資料、不放廣告、沒有商業模式。開源是為了讓人放心看見它到底怎麼運作，也方便別人自己接手架設。
- **聖經全文（和合本 1919）屬公有領域（public domain）**：這份和合本全文本身沒有版權問題，可以自由使用。程式碼是 MIT，聖經文本是公有領域，兩者分開看。
- **金鑰不在程式碼裡**：所有 LINE／Supabase／AI 的金鑰都靠 `.env`（已被 `.gitignore` 排除），git 歷史裡從頭到尾沒有任何憑證。你要自己架，就照 `.env.example` 填自己的。
- **多小組隔離（加入碼）**：同一個部署站台可以同時服務好幾個小組，每一組靠一組加入碼各自獨立——你只會看到自己這一組的經文與領受，看不到別組的。登入後還沒加入任何組的人會被導去 `/onboarding` 選「用加入碼加入」或「自己開一組」。所有查詢都以「你目前這一組」為界（見 `data_store` 裡貫穿各查詢的 `group_id` 與 `test_groups.py` 的隔離測試）。

## 本地執行

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # 先不填任何值也能跑，見下方「三種執行模式」
python app.py
```

開啟 http://127.0.0.1:5000

## 測試

```bash
pip install -r requirements-dev.txt
pytest
```

測試靠 `tests/conftest.py` 在 import app 之前把 `SUPABASE_URL` 清空，**強制整套跑在
記憶體示範模式**，所以：不需要任何金鑰、跑很快、而且**絕對不會連到或寫到真實的
Supabase**（之前手動測試不小心寫進正式站的意外，測試套件從設計上就杜絕）。
每次 push／PR 也會在 GitHub Actions 自動跑一遍（`.github/workflows/tests.yml`）。

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
static/manifest.json       PWA manifest
static/sw.js               Service worker（用 /sw.js 這個路由提供，見 app.py 的說明）
```

## 目前做了什麼（第一版範圍）

- 多小組（加入碼）：同一個站台可以同時有好幾個小組，每一組靠加入碼各自獨立、互相看不到。任何登入的人都能自助建組（建組的人自動是那一組的輔導、拿到一組可分享的加入碼），也可以用別人給的加入碼加入既有小組。所有經文／領受查詢都以「你目前這一組」為界（每查詢隔離）
- 首頁：今天這段經文（有節號的話會顯示在前面）、可以同時點好幾句標記（各自獨立切換，不是只能選一句）、可留一句領受（文字選填，不寫也可以），下面直接接著「同一段路上」——小組每個人在這段經文的領受，不用另外開頁面、不用點開才看得到。留過的領受不會鎖住表單，可以再留一則（重讀有新的感動）、也可以編輯舊的那一則
- 對別人的領受可以留固定反應（🌼／💛／✨…，各自對應寫死的鼓勵語，不是自由留言），一人一則領受只能留一種，可以換、可以取消
- 輔導後台 `/admin`：兩種排經文的方式，經文字句一律從和合本全文帶出來，輔導不能自己打／改字句（聖經的字句不由我們改）
  - 書卷＋章節（選書卷、填章節，自動從和合本全文帶出經文；可加「主題副標」幫這段取個主題，只加標題、不動經文）
  - 批次匯入 xlsx（跟天父日記的 `plan.xlsx` 同一種欄位：`date / book / range / guiding_question`，一次排好接下來好幾天，`/admin/template` 可下載空白範本）
  - 引導問題留空會用 AI 生一句（`GROQ_API_KEY` / `GEMINI_API_KEY` / `ANTHROPIC_API_KEY` 擇一設定即可，優先順序 Groq → Gemini → Anthropic）
  - 都可以同時種頭香（留自己的第一句領受，只對「今天」有效）
- 各組輔導可以禁言自己組內的成員（平台方不可能一個人管所有組，所以這個權限下放到各組輔導）：不是封鎖帳號，還是能讀、能看動態牆，只是不能再留新的領受。永久管理員（`ADMIN_LINE_USER_IDS`）則是跨組的最高權限，留給平台級的安全處理
- `/history`：回顧月曆，往回翻小組排過的日子，點進去可以完整寫領受（不只是唯讀）；格子只代表「那天有沒有排經文」，不標記「你有沒有寫」，不是完成率視覺化
- LINE Login OAuth 骨架、`@login_required` / `@admin_required`、最小可用的 CSRF 保護
- 首頁「到 bibile-actionbook 深度閱讀這段」連結：會直接跳到今天這段對應的書卷／章節，不是固定連到首頁
- 真的 PWA：可以「加入主畫面」變成看起來像原生 app、有 service worker、離線時顯示 `/offline` 而不是瀏覽器的錯誤頁
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

-- 2026-07-19：daily_passages 加 verse_labels（每句對應的節號，畫面上顯示節號用）
alter table daily_passages add column if not exists verse_labels jsonb;

-- 2026-07-19：reflections 加 verse_indexes（可以同時針對好幾句經文，不是只能選一句）
alter table reflections add column if not exists verse_indexes int[];

-- 2026-07-19（晚）：reflections 拿掉 (passage_id, member_id) 唯一限制，
-- 同一段經文可以留好幾則不同時間點的領受，不會因為留過一次就被鎖住
do $$
declare
  con record;
begin
  for con in
    select conname from pg_constraint
    where conrelid = 'reflections'::regclass
      and contype = 'u'
      and array_length(conkey, 1) = 2
  loop
    execute format('alter table reflections drop constraint %I', con.conname);
  end loop;
end $$;

-- 2026-07-19（更晚）：members 加 is_muted（禁言，只有永久管理員能操作）
alter table members add column if not exists is_muted boolean not null default false;

-- 2026-07-19（最晚）：新增 reflection_reactions，可以對別人的領受留固定幾種反應
-- （不是自由留言，避免引發論戰），一人對一則領受只能留一種反應
create table if not exists reflection_reactions (
  id uuid primary key default gen_random_uuid(),
  reflection_id uuid not null references reflections(id) on delete cascade,
  member_id uuid not null references members(id) on delete cascade,
  kind text not null check (kind in ('resonate', 'comfort', 'light')),
  created_at timestamptz not null default now(),
  unique (reflection_id, member_id)
);
create index if not exists idx_reflection_reactions_reflection on reflection_reactions (reflection_id);
alter table reflection_reactions enable row level security;

-- 2026-07-20：反應種類多加了幾種（🙏 想為你禱告／🌱 謝謝你的分享／💫 也被觸動了／
-- 🕊️ 跟你一起阿們）。原本的 CHECK 只認得舊的三種，會擋掉新的，直接把 CHECK 拿掉，
-- 合法值改成一律由程式端（data_store.REACTION_KINDS）把關，以後加新反應不用再改資料庫。
alter table reflection_reactions drop constraint if exists reflection_reactions_kind_check;

-- 2026-07-21：最小版多小組（加入碼）。groups 加 join_code（別人靠這串短碼加入你這一組），
-- members.group_id 放寬成可為 null（剛登入還沒加入任何組的人），並給既有那一組補一組加入碼。
alter table groups add column if not exists join_code text;
create unique index if not exists idx_groups_join_code on groups (join_code);
alter table members alter column group_id drop not null;

-- 給既有的（單一）小組補一組加入碼，這樣原本的成員完全不受影響、繼續留在原組，
-- 輔導也能到 /admin 看到這組的加入碼分享出去。只補還沒有加入碼的組。
update groups
set join_code = upper(substr(replace(gen_random_uuid()::text, '-', ''), 1, 6))
where join_code is null;
```

到 Supabase 專案的 SQL Editor 貼上執行一次就好，既有資料不受影響（既有成員都留在原本那一組）。

## 還沒做的事（卡在需要外部資源，先不做）

- 天父日記的每日經文排程後台，目前是「照做一份自己的」，不是共用同一張表
- 圖鑑系統、co-op RPG、正式美術素材——這些是北極星文件裡明訂的第二階段，這一版不做
- 多小組目前是「最小版」：一人只屬於一組、加入碼沒有到期或人數上限、也還沒有「換組／退出」的畫面（要換組目前得從資料庫改）。夠一個站台服務好幾個小組，但還不是完整的組織管理

## Rule 14：如果這個服務有一天收掉了

這個工具存的是一整個小組對神的領受，服務停掉不能讓這些記憶跟著蒸發。現在就可以：

1. **一鍵匯出**：開啟 `/export/json` 或 `/export/csv`，下載今天這段經文的所有領受。
2. **離線閱讀器**：開啟 `/export/html`，會產生一頁不需要伺服器、不需要網路就能打開的靜態頁面，另存新檔存到自己電腦就可以。
3. **非技術交接**：只要能打開瀏覽器、能存檔案，不需要懂程式，就能把這些領受留下來、交給下一個接手的人。
