# 美股記憶體 (US Memory Semiconductors) 專案規則

## 1. 專案定位與核心標的
本工作區專門用於追蹤與分析**美股記憶體產業（DRAM、NAND Flash、HBM 高頻寬記憶體）**及 AI 伺服器供應鏈相關投資標的。

- **目前美股核心操作標的**：`MUU`（Direxion Daily MU Bull 2X Shares，美光科技每日 2 倍做多主動型/槓桿 ETF）
- **底層連動標的**：`MU`（Micron Technology, Inc. 美光科技）
- **台股 AI 伺服器持倉標的**：`2059.TW`（川湖 King Slide，AI 伺服器導軌龍頭）
- **同業與供應鏈參考**：SK Hynix（SK 海力士）、Samsung Electronics（三星電子）、Western Digital (`WDC`) / SanDisk (`SNDK`)、輝達 (`NVDA`)、博通 (`AVGO`)、超微 (`AMD`) 等 AI 算力需求端。

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

## 3. 專屬快捷指令約定：`開會`（Antigravity 原生 Swarm 4-Agent 投資委員會）
- **觸發暗號**：當使用者在任何 Antigravity 對話中輸入 **`開會`**、**`深度開會`** 或 **`開會 <特定議題>`**（例如：`開會 今晚 OpEx 該留倉還是減碼`、`開會 美光財報前佈局`）時，**不需反問需求**，直接啟動 **Antigravity 原生 Swarm（多代理蜂群協作）**：
  1. 主對話 AI 擔任 **CIO 首席投資長（Coordinator）**，先讀取最新的 `portfolio_config.json`、`daily_macro_options.json`、`tw2059_chips.json` 掌握實盤持倉與雲端快照。
  2. 平行派出 **4 位獨立旗艦研究代理**（並依 `swarm` skill 規範搭配 `monitor`）：
     - **`macro-news`（🌐 總經與外電情報員）**：透過 `search_web` 查證最新美光/HBM/DRAM 外電、NVDA/AVGO/SK Hynix 同業動態、`US10Y`、`DXY`、`SOX` 與總經數據，給出 `-5 ~ +5` 評分。
     - **`tech-options`（🧮 技術與衍生品微結構師）**：整合 `MU`/`MUU` 最新收盤、均線結構、RSI、CBOE 選擇權 Max Pain / Put-Call Ratio / Call-Put OI 牆 / IV / Net GEX 與 `MUU` 槓桿耗損，給出 `-5 ~ +5` 評分。
     - **`tw2059-chips`（🏭 川湖籌碼與基本面專家）**：查證 `2059.TW` 最新三大法人連買賣、融資融券、借券賣出、當沖比、月營收與 CB 進度，給出 `-5 ~ +5` 評分。
     - **`risk-devil`（🛡️ 空頭魔鬼代言人 / 風控審查官）**：強制站在空方與風控立場，挑戰前面三位專家的樂觀假設，點出破位紅線、高 IV 陰跌陷阱與最壞劇本最大回撤，給出 `-5 ~ +5` 風險評分。
  3. 4 位專家於佈告欄交叉檢視後，由 Coordinator（CIO）彙整輸出**繁體中文 Markdown 表格版「4-Agent 投資委員會決議書」**（含總分 `/20`、多空衝突裁決、以及針對 `MUU` 核心/游擊倉與 `2059.TW` 的具體掛單劇本 A/B/C/D），並詢問是否同步寫入戰情室與筆記。
- **日常省配額模式**：若使用者僅詢問「分析今天最新戰情」或一般單一問題（未輸入 `開會`），則維持單人模式以節省 Antigravity 配額。
- **觸發暗號二：`跑量化` / `跑 Colab`（Google Colab 機構級量化實驗室自動執行與判讀）**：
  - 當使用者輸入 **`跑量化`**、**`跑 Colab`**、**`執行量化實驗室`** 或要求用 Colab 執行並分析時，**不需反問連結**，直接委派 `browser` subagent 開啟 Google Colab 專屬筆記本 `https://colab.research.google.com/drive/122LnxDw4vJf6cJwpxiy7ekcQKYOfvRiP`（本機對應 `notebooks/MU_WarRoom_Quant_Lab.ipynb`），點擊 **「全部執行 (Run all)」** 待 Cell 1～6 全部完成後，擷取最新 4 大量化模組結果（`MUU` 50,000 次蒙地卡羅波動耗損、`MU` 全到期日 GEX 剖面與 IV 期限結構、5 年急殺重啟游擊倉濾網回測、`2059.TW` 法人與融資籌碼圖），再由主對話結合六大維度與實盤持倉輸出操作分析與掛單劇本。

---

## 4. 雲端全自動化架構（v5.2）與跨平台（Windows / macOS）檔案結構
本專案已升級為 **零月費、免開機、24/7 雲端全自動架構**（GitHub 儲存庫：`https://github.com/hsienstyle/mu-war-room`，iOS PWA 戰情室：`https://hsienstyle.github.io/mu-war-room/`，Google Apps Script 專案：`美股記憶體與川湖_雲端排程`），支援 **Windows** 與 **macOS** 雙平台無縫同步操作，**一律使用專案相對路徑，禁止寫死單一作業系統之絕對路徑**：

### 核心雲端與本機檔案對照
| 相對路徑 | 檔案功能說明 |
| :--- | :--- |
| `GEMINI.md` | 專案核心規則、`開會` Swarm 指令約定與跨平台同步準則（Windows / Mac 共用） |
| `portfolio_config.json` | **單一真相設定檔**：記錄 `MUU` 總股數/核心/游擊/均價、`2059.TW` 持倉、關鍵支撐壓力位與盤中警報規則 `alerts`（改此檔全端自動生效） |
| `portfolio/trades.csv` | 歷史交易與做 T 明細帳本（可由 LINE 雙向機器人 `買/賣` 指令自動追加） |
| `watchlist.md` | 核心標的與產業鏈觀察清單 |
| `notes/` | 技術面關鍵價位分析 (`notes/MU_MUU_technical_analysis.md`) 與歷日戰情筆記 |
| `index.html` / `dashboard.html` | **iOS PWA 戰情室主頁與 120 日量化儀表板**（Tab 1 即時戰情、Tab 2 自動更新 3 張情報卡、Tab 3 部位與川湖籌碼卡） |
| `MU_MUU_Widget.js` | **iOS Scriptable 桌面即時小工具腳本** |
| `cloud_daily_job.py` | **美股 08:00 六維度晨報 & 4-Agent 委員會主程式**（純標準庫：CNBC/Stooq/Yahoo/TWSE + CBOE 官方選擇權 Max Pain/GEX/IV + MUU 耗損 + 3 專家 `gemini-3.6-flash` 並行 → CIO `gemini-3.7-flash` 裁決 + 更新 Tab 1/Tab 2 與 LINE 推播） |
| `cloud_tw2059_chips.py` | **川湖 16:35 盤後籌碼專報主程式**（純標準庫：TWSE 5 大官方 API 三大法人/融資券/借券/當沖 + `gemini-3.6-flash` 判讀 + 更新 Tab 2/Tab 3 與 LINE 推播） |
| `daily_macro_options.json` | 每日雲端快照：總經、同業共振、CBOE `MU` 選擇權、MUU 耗損與 4-Agent 委員會紀錄 |
| `tw2059_chips.json` | 川湖近 30 個交易日盤後籌碼歷史資料庫 |
| `.github/workflows/` | `daily_war_room.yml`（08:00 美股晨報）與 `tw2059_chips.yml`（16:35 川湖籌碼）雙排程設定 |
| `google_apps_script_trigger.gs` | **Google Apps Script 總指揮中心（v5.2，置於本機根目錄且已列於 `.gitignore`）**：每 5 分鐘巡檢（08:00 晨報、08:05 & 16:40 Google Drive 含原生 Google Doc 自動同步、09:05~13:35 川湖盤中狙擊、16:35 川湖籌碼、21:00~05:15 美股盤前/盤中狙擊）＋ **LINE 雙向機器人 Web App**（`報價`/`倉位`/`算T`/`籌碼`/`選擇權`/`警報`/`買賣記帳`/`同步`/`問`/`開會` 4-Agent `gemini-3.6-flash` 並行） |
| `notebooks/MU_WarRoom_Quant_Lab.ipynb` | **Google Colab 機構級量化實驗室**（直開連結：`https://colab.research.google.com/drive/122LnxDw4vJf6cJwpxiy7ekcQKYOfvRiP`）：`MUU` 50,000 次蒙地卡羅耗損模擬、`MU` 全到期日 GEX / IV 期限結構、5 年急殺重啟游擊倉回測與 `2059.TW` 籌碼疊圖 |

### 資安紅線（嚴格遵守）
- **零明文密鑰**：嚴禁於任何 `.py`、`.gs`、`.html`、`.json` 或公開 Repo 中硬編碼任何 Token / API Key。
- 所有密鑰均存放於 **GitHub Secrets**（`LINE_CHANNEL_ACCESS_TOKEN`、`LINE_USER_ID`、`GEMINI_API_KEY`）與 **GAS 指令碼屬性（Script Properties）**（另含最小權限 Fine-grained PAT `GITHUB_TOKEN`，僅授權 `hsienstyle/mu-war-room` 之 `Actions` 與 `Contents` 讀寫）。

---

## 5. 跨平台日常維護與 GitHub / Google Drive 同步 SOP

1. **全天候 24/7 自動運行（可完全關機）**：
   - 美股 08:00 六維度晨報、川湖 16:35 盤後籌碼專報、盤中雙市場狙擊警報、LINE 雙向互動與 Google Drive 每日 08:05 / 16:40 自動同步，均在雲端全自動完成，**無須開啟本地電腦或 NAS**。
2. **當使用者在本機通報「持倉變動（買賣做 T）」或「更新戰情室功能」時**：
   - 依序同步更新相關檔案（`portfolio/trades.csv`、`portfolio_config.json`、`index.html`、`MU_MUU_Widget.js`、`notes/MU_MUU_technical_analysis.md`、`watchlist.md`）。
   - 執行跨平台標準 Git 同步指令推送至 GitHub 雲端：
     ```bash
     git pull --rebase origin main
     git add <changed_files>
     git commit -m "Update portfolio / war room data"
     git push origin main
     ```
   - **同步更新至 Google Drive 遠端資料夾（`美股記憶體_MU戰情室`，Folder ID: `1p5GbcMqrLPI-UBqIyfB0BEOd-o_iNIE6`）**：
     平日由 GAS 於 `08:05` 與 `16:40` 自動同步（亦可在 LINE 傳 `同步` 立即執行）；本機即時同步時使用 `gdrive mutate update <FILE_ID> <本地相對路徑>` 原地更新以下對應檔案（保持 File ID 與連結不變，方便手機版 Gemini App 透過 `@Google Drive` 隨時讀取）：
     - `美股記憶體_MU_MUU_最新戰情與持倉總表`（原生 Google Doc）：`1S7W8Fc-HI3ktSXhtiONS_VhopwrAlz5hDfsZxxEfjTg`
     - `美股記憶體_MU_MUU_最新戰情與持倉總表.md`：`1vipUsK_S6Q5m2CipwbZ0g0uR2h2PgL4F`
     - `GEMINI.md`：`1lMTaJGDD0cqGSPyNugqskuyk6LZsWsGw`
     - `portfolio_config.json`：`1qfrGmv2p12Gfa2l39onRbE6anHEmgRtr`
     - `portfolio/trades.csv`：`1AGh_oeMfeJQ9KNeyjEoVTyGikdGMLDAI`
     - `notes/MU_MUU_technical_analysis.md`：`1J3ChomcsZXKIwzP1c9d49rGTUc3doBYE`
     - `watchlist.md`：`1pt_0NWLGS-99Mu5NSaB5U8lWO4ebS1iI`
     - `index.html`：`1-HrZXMTmu_B_G_UG6zMSrA5ktf3okTeX`
     - `MU_MUU_Widget.js`：`1jb12a3El1k6USIykBzNnuAd7CM-C3u4X`
     - `MU_WarRoom_Quant_Lab.ipynb`（Google Colab 量化實驗室）：`122LnxDw4vJf6cJwpxiy7ekcQKYOfvRiP`
     - *(另由 GAS 自動維護於同資料夾內之即時快照：`tw2059_chips.json`、`daily_macro_options.json` 與原生 Google Doc `美股記憶體_MU_MUU_最新戰情與持倉總表`)*
