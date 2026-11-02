# 美股記憶體 (US Memory Semiconductors) 專案規則

## 專案定位與核心標的
本工作區專門用於追蹤與分析**美股記憶體產業（DRAM、NAND Flash、HBM 高頻寬記憶體）**及相關投資標的。

- **目前核心操作標的**：`MUU`（Direxion Daily MU Bull 2X Shares，美光科技每日 2 倍做多主動型/槓桿 ETF）
- **底層連動標的**：`MU`（Micron Technology, Inc. 美光科技）
- **同業與供應鏈參考**：SK Hynix（SK 海力士）、Samsung Electronics（三星電子）、Western Digital (`WDC`) / SanDisk (`SNDK`)、輝達 (`NVDA`) 等 AI 伺服器需求端。

## AI 助手分析準則
1. **語言與格式**：一律使用**繁體中文**回答，重要數據與比較優先使用 Markdown 表格整理。
2. **雙層分析視角（MU 基本面 + MUU 槓桿特性）**：
   - 分析產業與基本面時，聚焦於底層資產 **`MU`（美光）** 的營收、毛利率、HBM 產能與良率、DRAM/NAND 合約價與現貨價週期、法說會指引（Guidance）。
   - 討論操作與部位管理時，必須考慮 **`MUU`（2倍槓桿 ETF）** 的每日重設（Daily Reset）特性、波動率耗損（Volatility Decay / Beta Slippage）以及約 1.01% 的內扣費用，提醒盤整震盪期的耗損風險。
3. **資料維護**：
   - 觀察清單維護於 `watchlist.md`
   - 標的深度筆記存放於 `notes/`
   - 交易與部位紀錄存放於 `portfolio/trades.csv`
4. **每日早晨戰情更新與 LINE 推播自動化 SOP**：
   - 當收到「每日早晨戰情更新與 LINE 推播任務」時，依序執行：
     1. 讀取 `portfolio/trades.csv` 與 `notes/MU_MUU_technical_analysis.md` 確認目前持倉股數與實質均價。
     2. 使用 `search_web` 查詢最新美股交易日之 `MU` 與 `MUU` 收盤價、漲跌幅、高低價與關鍵新聞（**切勿使用腳本抓取外部網頁，一律使用內建 `search_web` 工具**）。
     3. 更新 `notes/MU_MUU_technical_analysis.md` 與當日戰情日報，並將推播文案寫入 `latest_line_message.txt`。
     4. 發送 LINE 推播時，**直接透過 `run_command` 執行以下指令**：
        `powershell -ExecutionPolicy Bypass -File "c:\Users\joshwu\.gemini\antigravity\scratch\美股記憶體\scripts\send_line.ps1"`
     5. **同步更新 iOS 戰情室 App 並推送至 GitHub Pages**：
        - 將當日最新收盤價、支撐壓力價位、最新持倉數據與繁體中文重點新聞解讀同步更新至 `ios_app/index.html` 與 `ios_app/MU_MUU_Widget.js`。
        - 執行 `powershell -ExecutionPolicy Bypass -File "c:\Users\joshwu\.gemini\antigravity\scratch\美股記憶體\ios_app\deploy_pages.ps1"`（或 `git -C ios_app` 提交並推送至 `origin main`），確保 `https://hsienstyle.github.io/mu-war-room/` 每日早晨自動呈現最新戰情。
