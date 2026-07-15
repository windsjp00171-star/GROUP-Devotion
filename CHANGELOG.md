# CHANGELOG

本文件記錄 GROUP-Devotion 的重要變更，時間由新到舊排列。

## [Unreleased] - 2026-07-15

### 修正
- 正式站 `/admin/import` 500：Groq 被 rate limit（429）後，SDK 內建重試機制 sleep 到超過 gunicorn worker timeout，被外部訊號強制 kill worker，不是一般的 Python 例外，先前的 try/except 防呆完全接不住。修法：Groq／Anthropic client 關掉 SDK 自己的重試、加 12 秒短逾時；Gemini 呼叫加逾時；批次匯入時 AI 第一次失敗就不再繼續打，其餘列直接用預設引導問題；gunicorn 加 `--timeout 45` 當最後一道防線。

## [Unreleased] - 2026-07-14

### 新增
- 和合本聖經全文（`scripture/cuv.json`，跟天父日記共用同一份資料，從公版 iBibles 資料建出來）＋ `scripture.py` 查詢層：輔導排經文可以直接選書卷＋章節，自動帶出經文，不用自己貼。
- 批次匯入：`/admin/import` 上傳 xlsx，欄位 `date / book / range / guiding_question`，跟天父日記的 `plan.xlsx` 同一種格式，一次排好接下來好幾天；`/admin/template` 可以下載空白範本。
- AI 生成引導問題（`ai_guide.py`）：排經文時引導問題留空，就用 AI 生一句——provider 偵測跟系統提示語照抄天父日記驗證過會動的做法，優先 Groq、沒有就 Gemini、都沒有就 Anthropic；三個都沒設定就退回預設那句，不會壞掉。
- `/admin` 後台重新設計成三種排經文的方式並存：書卷＋章節（新，推薦）、批次匯入（新）、手動貼經文（原本就有，當備案）。

### 事故記錄（誠實面對）
本機測試新功能時，誤以為會走記憶體示範模式，實際上因為 `.env` 已經有正式的 Supabase 金鑰，測試直接寫進了正式站資料庫（一筆假的今日排程、一個假帳號 `dev-user`、一則假領受）。發現後已手動清除乾淨，確認過沒有動到任何真實使用者資料。之後對正式站跑測試會更小心。

## [Unreleased] - 2026-07-13

### 新增
- 真正的資料層：接了 Supabase 就存真資料（`groups` / `members` / `daily_passages` / `reflections`，見 `schema.sql`），沒接就自動退回記憶體示範模式——兩條路走同一套程式碼，行為一致，不是兩套邏輯。
- LINE Login OAuth 骨架（`auth.py`）：`/login`、`/line/callback`、`/logout`，寫法沿用天父日記 app.py 裡實際跑得動的授權碼流程。還沒有 LINE Channel 憑證之前，`/login` 會顯示「尚未設定」而不是報錯。
- `@login_required`、`@admin_required` decorator，還有本機測試專用的 `/dev/login`（只在 `FLASK_DEBUG=1` 時才會註冊，正式站不會出現）。
- 輔導後台 `/admin`：排定今天這段經文（出處／經文／引導問題），可以同時留下輔導自己的第一句領受（種頭香，冷啟動解法之一）。
- 最小可用的 session-based CSRF 保護（`csrf.py`），套用在所有 POST 路由。
- 首頁新增「到 bibile-actionbook 深度閱讀這段」連結（沿用天父日記已經在用、也驗證過可行的做法：連到部署好的網站，不是程式碼依賴）。

### 重要發現：`mark_core` 目前不存在
開工前照北極星文件把 bibile-actionbook、tianfu-diary 兩個姊妹 repo 加進來核對，發現專案簡報裡提到的「`mark_core` 共用套件」（`supabase_client` / `auth` / `csrf` / `notification_queue` / `@login_required` / 統一 API 回傳格式）**在帳號裡完全不存在**，兩個姊妹專案也都是各自 ad hoc 接 Supabase／LINE OAuth，並沒有真的共用套件可以 import。`vendor/bible_actionbook/` 這個目錄也只有兩個空的 `.gitkeep`，不是真的依賴機制。

這一版做法：把姊妹專案裡「真的在跑」的模式抄過來（`create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)`、LINE OAuth 授權碼流程、session 存 user），`@login_required` decorator、CSRF、統一 API 回傳格式則是 GROUP-Devotion 自己第一次真的寫出來——不是「沿用」，是「補上」。`notification_queue` 涉及催討式通知，剛好也是北極律文件明訂的鐵律不做，這一版沒有實作、也不打算實作。

### 待辦（卡在需要外部資源，先不做）
- 接 Supabase 專案（帳號免費額度已被兩個既有專案佔滿，等你另開帳號給金鑰）。
- 接真正的 LINE Channel 憑證（`LINE_CHANNEL_ID` / `LINE_CHANNEL_SECRET` / `LINE_REDIRECT_URI`，等你提供）。
- 天父日記的每日經文排程後台目前是「照做一份自己的」，不是共用同一張表——沒有共用 Supabase 專案，這件事現階段做不到。
- 圖鑑系統、多小組並行、co-op RPG、正式美術素材——北極星文件明訂的第二階段，這一版刻意不做。

## [Unreleased] - 2026-07-11

### 新增
- 專案初始化：Flask + Jinja2 + 純 HTML/CSS 骨架。
- 首頁「今天這段，一起讀讀看」：顯示當日經文、可點選標記最有感的一句、可留一句領受（文字選填，不寫也可以）。
- 碰撞畫面「同一段路上」：小夥伴腳邊的小花園，聚集小組每個人在這段經文的領受記號（花／果／蝶／石），點擊可看見內容；沒有多寫字的領受一樣被溫柔顯示，不強迫、不標記為「空白」。
- Rule 14 數位遺囑模組起點：`/export/json`、`/export/csv` 一鍵匯出，`/export/html` 產生可離線閱讀、不需伺服器的靜態頁面。
- Rule 15 教學按鈕：畫面右上角「？」，`data-tour` 綁定當前畫面的簡短說明。
- Rule 16：建立本 CHANGELOG。

### 視覺與體驗參考
- 以「以馬忤斯路上 Prototype11」原型的視覺、文案、互動節奏為參照重新實作，不沿用其程式碼結構。
- 修正原型已知問題：領受記號改為聚集在小夥伴腳邊成一叢花園，不再散落飄浮於畫面各處。

### 待辦（第二版或依賴外部模組，先不做）
- 接 Supabase 作為真正的資料儲存（目前為記憶體內的示範資料，重啟伺服器會重置）。
- 接 LINE Login OAuth 與 `mark_core` 共用模組（`supabase_client` / `auth` / `csrf` / `notification_queue` / `@login_required`）。
- 接天父日記的每日經文排程後台、bible-actionbook 的閱讀層與註釋引擎（共用模組方式引入，不 fork）。
- 圖鑑系統、多小組並行、co-op RPG、正式美術素材——北極星文件明訂的第二階段，這一版刻意不做。
