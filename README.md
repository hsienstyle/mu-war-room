# 美股記憶體 投資研究專案

這是一個專注於美股記憶體產業與相關標的的投資研究工作區。

## 📌 目前核心標的
- **`MUU`** — Direxion Daily MU Bull 2X Shares（追蹤 `MU` 單日 200% 報酬之槓桿 ETF）
- **`MU`** — Micron Technology, Inc.（美光科技，底層正股）

## 📂 目錄結構
- [GEMINI.md](GEMINI.md)：專案專屬 AI 規則（當此資料夾設為 Project 時，AI 會自動載入此規範）。
- [watchlist.md](watchlist.md)：核心追蹤清單與觀察指標。
- [notes/MUU_overview.md](notes/MUU_overview.md)：`MUU` 與底層 `MU` 的基本檔案、催化劑與槓桿風險筆記。
- [portfolio/trades.csv](portfolio/trades.csv)：部位與交易紀錄表範本。


## 🖥️ NAS 儀表板（DS925+）
- [scripts/nas_dashboard.py](scripts/nas_dashboard.py)：只用 Python 標準庫，不需要 Docker。每次執行會在同目錄產生 `scripts/index.html`。
- **DSM 設定**：控制台 → 任務排程表 → 新增 → 排程的任務 → 使用者定義的指令碼
  - 排程：週二～週六 06:30（美股收盤後）
  - 指令：`python3 /volume1/<共用資料夾>/美股記憶體/scripts/nas_dashboard.py`
- **查看方式**：用 File Station 或 Synology Drive 直接打開同目錄下的 `index.html`；也可以用 Web Station 架成內網網頁。
