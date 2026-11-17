# 美股記憶體 (US Memory Semiconductors) 專案規則

## 1. 專案定位與核心標的
本工作區專門用於追蹤與分析**美股記憶體產業（DRAM、NAND Flash、HBM 高頻寬記憶體）**及 AI 伺服器供應鏈相關投資標的。

- **目前美股核心操作標的**：`MUU`（Direxion Daily MU Bull 2X Shares，美光科技每日 2 倍做多主動型/槓桿 ETF）
- **底層連動標的**：`MU`（Micron Technology, Inc. 美光科技）
- **台股 AI 伺服器持倉標的**：`2059.TW`（川湖 King Slide，AI 伺服器導軌龍頭）
- **同業與供應鏈參考**：SK Hynix（SK 海力士）、Samsung Electronics（三星電子）、Western Digital (`WDC`) / SanDisk (`SNDK`)、輝達 (`NVDA`)、超微 (`AMD`) 等 AI 算力需求端。

---

## 2. AI 助手分析準則（六大維度全方位機構級分析架構）
1. **語言與格式**：一律使用**繁體中文**回答，重要數據與比較優先使用 Markdown 表格整理。
2. **六大維度全方位分析視角**：
   - **① 技術面 (Technical Analysis)**：K 線型態、均線結構（5/10/20/50/200MA）、跳空缺口、成交量價結構、RSI/MACD 動能與關鍵支撐壓力位。
   - **② 基本面 (Fundamental Analysis)**：聚焦底層資產 **`MU`（美光）** 之營收、毛利率、HBM3E/HBM4 產能與良率、DRAM/NAND 現貨與合約報價週期、法說會指引（Guidance）與估值（Forward P/E、P/B）；以及 **`2059.TW`（川湖）** 在 GB300 / Vera Rubin / ASIC 伺服器導軌之市佔、毛利率與 EPS 動能。
   - **③ 籌碼面 (Institutional & Flow Analysis)**：`MU` 機構法人持倉（13F）、空單餘額與回補天數（Short Interest）、內部人買賣、槓桿 ETF 申贖流向；`2059.TW` 三大法人（外資/投信/自營商）買賣超、融資融券、借券賣出與大戶持股動向。
   - **④ 消息與事件面 (News & Event Catalysts)**：輝達 (`NVDA`) / 博通 (`AVGO`) / 超微 (`AMD`) 財報與 AI 算力指引、四大 CSP 資本支出（CapEx）、同業動態（SK Hynix / Samsung / CXMT）、反壟斷訴訟、出口管制與關稅政策、川湖 CB 可轉債訂價與法說日程。
   - **⑤ 總體經濟與資金面 (Macro & Liquidity)**：美國 CPI / PPI / 非農就業數據、聯準會（Fed）利率政策與降息預期、10 年期美債殖利率（`US10Y`）、美元指數（`DXY`）與新台幣匯率、費城半導體指數（`SOX`）及 AI 硬體板塊資金輪動。
   - **⑥ 衍生品與量化微結構面 (Derivatives & Quantitative Microstructure)**：`MU` 選擇權隱含波動率（`IV` / `IV Rank`）、Put/Call Ratio、最大痛點（`Max Pain`）、造市商 Gamma 曝險（`GEX` / Gamma Wall 對沖助漲助跌效應），以及 **`MUU`（2倍槓桿 ETF）** 每日重設（Daily Reset）之波動率耗損（Volatility Decay / Beta Slippage）、內扣費用（1.01%）與尾盤再平衡（Rebalancing）微結構衝擊。
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
