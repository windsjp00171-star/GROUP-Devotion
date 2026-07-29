# CLAUDE.md

給所有在這個 repo 工作的 Claude session 看的**持久判斷原則**。

`README.md` 已經很完整地寫了「這個專案是什麼、怎麼跑、做了哪些功能」，**不要在這裡
重複它**——需要那些資訊就去讀 README。`CHANGELOG.md` 記錄開發過程的取捨。
這份檔案只寫一件事：**哪些東西不能動、動之前要先想什麼**。

## 專案是什麼（一句話）

給學青小組的群體共讀靈修工具。每天讀同一段經文、留一句領受、非同步看見彼此。
Flask + Jinja2 + 純 HTML/CSS，MIT 開源。

## 底線原則

### 1. 這個專案的價值在「刻意不做」的那些東西

**沒有打卡、沒有進度條、沒有排行榜、沒有催讀通知。** 這不是還沒做，是刻意不做——
沒有比較、沒有壓力，是這個工具存在的理由。看到「可以加個連續天數」「可以顯示本週
完成率」這類想法時，預設答案是不做，除非使用者親口要求。

具體已經踩過的線：
- `/history` 的月曆格子**只代表「那天有沒有排經文」，不標記「你有沒有寫」**。
  它不是完成率視覺化，不要把它改成那樣。
- 留過領受**不會鎖住表單**，可以再留一則、也可以編輯舊的。重讀有新的感動是正常的，
  不要為了「一天一則」的整齊而加限制。

### 2. 聖經的字句不由我們改

輔導後台排經文時，經文字句一律從和合本全文（`scripture/cuv.json`，1919 公有領域）
帶出來，**輔導不能自己打字或編輯字句**。可以加「主題副標」幫一段取主題，但那是加
標題，不動經文。任何讓人能直接編輯經文內容的功能都不要做。

### 3. 對別人領受的反應是固定選項，不是自由留言

🌼／💛／✨ 各自對應寫死的鼓勵語。這是為了避免比較和社交壓力。
不要「順手」把它做成留言框。

### 4. 多小組隔離是安全邊界，不是功能

同一個站台同時服務好幾個小組，靠加入碼各自獨立。**每一個查詢都必須以 `group_id`
為界**——`data_store.py` 裡所有查詢函式都帶 `group_id` 參數，這是貫穿設計。

新增任何查詢函式時，先問「這會不會讓 A 組看到 B 組的資料」。
`tests/test_groups.py` 是隔離測試，動到資料層一定要跑。

### 5. 沒有依賴共用框架，是刻意的

登入（LINE OAuth）、`@login_required` / `@admin_required`、CSRF 都是這個專案自己
從頭寫的最小實作（`auth.py`、`csrf.py`）。目的是讓想自己架站的人直接讀就懂，
不用先搞懂一個大框架。**不要為了「跟其他專案統一」把這裡換成共用套件**——
這個專案是 MIT 開源給別人接手的，可讀性優先於複用。

## 技術眉角

### 測試從設計上就碰不到正式資料庫

`tests/conftest.py` 在 import `app` / `data_store` **之前**把 `SUPABASE_URL` 等環境
變數清空，強制整套跑在記憶體示範模式。這是因為**以前手動測試不小心寫進正式站過**。

⚠️ 新增測試檔時不要自己 `import app` 在 conftest 之外的地方先跑，也不要在測試裡
自行設回 `SUPABASE_URL`。要跑就是：

```bash
pip install -r requirements-dev.txt
pytest
```

### 三種執行模式由 .env 自動決定，不改程式碼

1. `.env` 完全沒填 → 記憶體示範模式（重啟就重置，`/login` 顯示「尚未設定」）
2. `FLASK_DEBUG=1` → 多開 `GET /dev/login` 跳過 LINE 假登入。**正式站不要開**
3. 填了 Supabase／LINE → 真的存資料庫／真的 LINE 登入（兩者分開生效）

### schema.sql 是完整結構，但正式站要手動 migration

`schema.sql` 給新部署用。正式站的資料庫已經在跑，**新增欄位不會自動套用**，
要手動到 Supabase SQL Editor 補。改 schema 時記得同時給出 ALTER 語句。

### Supabase upsert 的欄位相容處理

`data_store.py` 有 `_upsert_with_fallback()` / `_insert_reflection_with_fallback()`，
用意是正式站資料庫可能還沒有某些新欄位時，自動退掉那些 optional key 再試一次。
**這不是多餘的防禦，是上面那條「手動 migration」的必然結果**，不要把它簡化掉。

## 部署現況（重要，容易搞混）

repo 裡同時有三套部署設定，實際狀況是：

| 檔案 | 狀態 |
|------|------|
| `railway.json` | ✅ **目前正式站跑這個**（Railway，`web-production-c1d3c.up.railway.app`）|
| `Procfile` | Railway / Render 通用的啟動指令，跟 railway.json 的 startCommand 一致 |
| `fly.toml` + `Dockerfile` | ⏳ 2026-07-28 新增，**準備搬到 Fly.io 但尚未切換** |

動部署設定前先確認要動的是哪一套。搬到 Fly.io 完成後，記得回來更新這一段，
並清掉不再需要的設定檔。

健康檢查路由：`/healthz`（Railway 和 fly.toml 都指向它）。

## Git 工作流程

squash merge 會讓本地分支跟遠端產生假分岔。**每次 PR 合併後，開始下一個改動前先重建分支**：

```bash
git fetch origin main -q
git checkout -B <工作分支> origin/main -q
# ...改動、commit...
git push --force-with-lease -u origin <工作分支>
```

## 跟其他專案的關係

- **bibile-actionbook**：設了 `BIBLE_ACTIONBOOK_URL` 環境變數，首頁會出現「深度閱讀
  這段」連結跳過去。沒設就不顯示——這是選用的鬆耦合，不要做成硬依賴。
- **tianfu-diary**：同樣是靈修日記性質，但那是個人日記（提交後永久鎖定），
  這裡是小組共讀（可編輯、可重留）。**設計理念相反，不要互相看齊**。
- `scripture/cuv.json` 這份和合本全文在 4 個 repo 各有一份副本
  （另有 tianfu-diary、bibile-actionbook、Church-Management-System-demo）。
  改動這個檔案前先想：其他三份要不要一起改？
