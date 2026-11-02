# 美股記憶體 (US Memory Semiconductors) 專案規則

## 1. 專案定位與核心標的
本工作區專門用於追蹤與分析**美股記憶體產業（DRAM、NAND Flash、HBM 高頻寬記憶體）**及 AI 伺服器供應鏈相關投資標的。

- **目前美股核心操作標的**：`MUU`（Direxion Daily MU Bull 2X Shares，美光科技每日 2 倍做多主動型/槓桿 ETF）
- **底層連動標的**：`MU`（Micron Technology, Inc. 美光科技）
- **台股 AI 伺服器持倉標的**：`2059.TW`（川湖 King Slide，AI 伺服器導軌龍頭）
- **同業與供應鏈參考**：SK Hynix（SK 海力士）、Samsung Electronics（三星電子）、Western Digital (`WDC`) / SanDisk (`SNDK`)、輝達 (`NVDA`)、超微 (`AMD`) 等 AI 算力需求端。

---

## 2. AI 助手分析準則
1. **語言與格式**：一律使用**繁體中文**回答，重要數據與比較優先使用 Markdown 表格整理。
2. **雙層分析視角（MU 基本面 + MUU 槓桿特性）**：
   - 分析產業與基本面時，聚焦於底層資產 **`MU`（美光）** 的營收、毛利率、HBM 產能與良率、DRAM/NAND 合約價與現貨價週期、法說會指引（Guidance）。
   - 討論操作與部位管理時，必須考慮 **`MUU`（2倍槓桿 ETF）** 的每日重設（Daily Reset）特性、波動率耗損（Volatility Decay / Beta Slippage）以及約 1.01% 的內扣費用，提醒盤整震盪期的耗損風險。
3. **外部資訊查詢原則**：
   - 在 Antigravity 對話中查詢最新美股收盤價、高低點與新聞時，**一律優先使用內建 `search_web` 工具**，切勿在對話中臨時撰寫爬蟲腳本抓取外部網頁。

---

## 3. 雲端全自動化架構與跨平台（Windows / macOS）檔案結構
本專案已升級為 **GitHub 雲端全自動架構**（儲存庫：`https://github.com/hsienstyle/mu-war-room`，iOS 戰情室網址：`https://hsienstyle.github.io/mu-war-room/`），支援在 **Windows** 與 **macOS** 雙平台無縫同步操作，**一律使用專案相對路徑，禁止寫死單一作業系統之絕對路徑**：

| 相對路徑 | 檔案功能說明 |
| :--- | :--- |
| `GEMINI.md` | 專案核心規則與跨平台同步準則（Windows / Mac 共用） |
| `portfolio_config.json` | **雲端推播與持倉核心設定檔**（記錄 `MUU` 總股數、核心/游擊倉、均價、`2059.TW` 持倉與關鍵支撐壓力位） |
| `portfolio/trades.csv` | 歷史交易與做 T 明細紀錄表 |
| `watchlist.md` | 核心標的與產業鏈觀察清單 |
| `notes/` | 技術面關鍵價位分析 (`notes/MU_MUU_technical_analysis.md`) 與歷日戰情筆記 |
| `index.html` / `manifest.json` | **iOS PWA 戰情室主程式**（含即時戰情、最新情報、部位做 T 試算器與 App 內改倉功能） |
| `MU_MUU_Widget.js` | **iOS Scriptable 桌面即時小工具腳本** |
| `cloud_daily_job.py` | **GitHub Actions 雲端每日執行腳本**（自動抓 Yahoo Finance 報價 + 外電/台股新聞 + 呼叫 `gemini-2.5-flash` 生成洞察 + 發送 LINE 推播 + 更新網頁） |
| `.github/workflows/daily_war_room.yml` | **GitHub Actions 定時排程設定檔**（台灣時間週二至週六早上 `08:00` / `UTC 00:00` 自動於雲端執行，無須開啟本地電腦或 NAS） |

---

## 4. 跨平台日常維護與 GitHub 同步 SOP（Windows & Mac 通用）

1. **每日早晨戰情與 LINE 推播（已由 GitHub 雲端全自動接管）**：
   - 每日早晨戰情更新、Gemini AI 新聞摘要、LINE 推播及 GitHub Pages 戰情室更新，均由 GitHub Actions 在雲端自動完成，**無須在 Windows 本機或 NAS 啟用本地定時排程**。
   - 若使用者在對話中主動要求「手動查詢今日最新戰情或發送測試推播」，則使用 `search_web` 取得最新行情與新聞，更新筆記與網頁後推送至 GitHub（或觸發 GitHub Actions workflow）。

2. **當使用者通報「持倉變動（買賣做 T）」或「更新戰情室功能」時**：
   - 依序同步更新以下檔案（確保本地與雲端數據一致）：
     1. `portfolio/trades.csv`（新增交易明細並計算最新實質總成本與均價）
     2. `portfolio_config.json`（更新 `total_shares`、`core_shares`、`swing_shares`、`total_cost_usd`、`avg_cost_usd` 等欄位，供雲端 LINE 推播讀取）
     3. `index.html` 與 `MU_MUU_Widget.js`（更新預設持倉狀態 `DEFAULT_PORTFOLIO` / `STATE` / `PORTFOLIO`）
     4. `notes/MU_MUU_technical_analysis.md` 與 `watchlist.md`
   - 完成檔案更新後，執行跨平台標準 Git 指令同步至 GitHub 雲端：
     ```bash
     git pull --rebase origin main
     git add .
     git commit -m "Update portfolio / war room data"
     git push origin main
     ```
