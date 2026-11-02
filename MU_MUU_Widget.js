// Variables used by Scriptable.
// These must be at the very top of the file. Do not edit.
// icon-color: deep-blue; icon-glyph: microchip;

/**
 * 📱 美股記憶體 (MU / MUU) iOS 桌面即時戰情小工具 (Scriptable)
 * 
 * 【安裝步驟】：
 * 1. 在 iPhone App Store 免費下載「Scriptable」App
 * 2. 打開 Scriptable -> 點擊右上角「+」新增腳本
 * 3. 將本檔案全部程式碼複製貼上，點擊左上角「Done」，並將腳本命名為「MU戰情室」
 * 4. 回到 iPhone 桌面 -> 長按空白處進入編輯模式 -> 點擊左上角「+」搜尋「Scriptable」
 * 5. 選擇「中型 (Medium)」小工具加入桌面 -> 長按該小工具點選「編輯小工具」：
 *    - Script 選擇「MU戰情室」
 *    - When Interacting 選擇「Run Script」
 */

// ================= 1. 持倉與關鍵價位參數設定 =================
const PORTFOLIO = {
  totalShares: 1150,          // MUU 總股數 (1100核心 + 50游擊)
  avgCost: 36.429,            // 整體實質均價 (USD)
  totalCost: 41893.20,        // 總投入淨成本 (USD)
  swingShares: 50,            // 游擊倉股數
  swingCost: 24.49,           // 游擊倉買入價 (10/30 低接)
  swingTargetMin: 25.80,      // 游擊倉停利區下緣
  swingTargetMax: 26.80,      // 游擊倉停利區上緣
  muSupport1: 861.59,         // MU 十字星低點支撐
  muDefense: 856.49,          // MU 10/22 波段前低防守線
  muResistance1: 915.00       // MU 頸線反壓
};

// 預設離線快照數據（當無網路或 API 異常時自動降級使用）
const FALLBACK_DATA = {
  MU: { price: 884.74, prevClose: 934.27, changePct: -5.30, low: 861.59, high: 906.54 },
  MUU: { price: 24.08, prevClose: 27.00, changePct: -10.82, low: 22.76, high: 25.43 },
  TW2059: { price: 9880, prevClose: 10150, changePct: -2.66 }
};

// ================= 2. 抓取 Yahoo Finance 即時報價 =================
async function fetchQuote(symbol, fallback) {
  try {
    const url = `https://query1.finance.yahoo.com/v8/finance/chart/${encodeURIComponent(symbol)}?interval=1d&range=5d`;
    const req = new Request(url);
    req.timeoutInterval = 6;
    const res = await req.loadJSON();
    const meta = res.chart.result[0].meta;
    const price = meta.regularMarketPrice;
    const prevClose = meta.chartPreviousClose || meta.previousClose;
    const changePct = ((price - prevClose) / prevClose) * 100;
    return {
      price: price,
      prevClose: prevClose,
      changePct: changePct,
      low: meta.regularMarketDayLow || fallback.low,
      high: meta.regularMarketDayHigh || fallback.high
    };
  } catch (e) {
    return fallback;
  }
}

// ================= 3. 建立 iOS 桌面 Widget 視覺介面 =================
async function createWidget() {
  const [mu, muu] = await Promise.all([
    fetchQuote("MU", FALLBACK_DATA.MU),
    fetchQuote("MUU", FALLBACK_DATA.MUU)
  ]);

  const w = new ListWidget();
  
  // 深色科技感漸層背景
  const gradient = new LinearGradient();
  gradient.locations = [0, 1];
  gradient.colors = [new Color("#0B1120"), new Color("#111827")];
  w.backgroundGradient = gradient;
  w.setPadding(12, 14, 12, 14);

  // --- 頂部標題列 ---
  const headerStack = w.addStack();
  headerStack.layoutHorizontally();
  headerStack.centerAlignContent();

  const titleTxt = headerStack.addText("⚡ 美股記憶體戰情室");
  titleTxt.font = Font.boldSystemFont(12);
  titleTxt.textColor = new Color("#38BDF8");

  headerStack.addSpacer();

  // 槓桿耗損 / 雙底狀態標籤
  const expectedMuuPct = mu.changePct * 2;
  const slippage = muu.changePct - expectedMuuPct;
  const statusText = mu.price >= PORTFOLIO.muDefense ? "🛡️雙底守穩" : "⚠️破前低警戒";
  const badgeTxt = headerStack.addText(`${statusText} | 2x差 ${slippage >= 0 ? "+" : ""}${slippage.toFixed(2)}%`);
  badgeTxt.font = Font.mediumSystemFont(10);
  badgeTxt.textColor = new Color("#94A3B8");

  w.addSpacer(8);

  // --- 中段：MU 與 MUU 雙欄核心報價 ---
  const mainStack = w.addStack();
  mainStack.layoutHorizontally();

  // 左欄：MU 底層正股
  const muCol = mainStack.addStack();
  muCol.layoutVertically();
  muCol.backgroundColor = new Color("#1E293B", 0.7);
  muCol.cornerRadius = 8;
  muCol.setPadding(8, 10, 8, 10);

  const muHeader = muCol.addStack();
  const muSym = muHeader.addText("MU ");
  muSym.font = Font.boldSystemFont(13);
  muSym.textColor = Color.white();
  const muSub = muHeader.addText("美光正股");
  muSub.font = Font.systemFont(10);
  muSub.textColor = new Color("#94A3B8");

  muCol.addSpacer(2);
  const muPriceRow = muCol.addStack();
  muPriceRow.bottomAlignContent();
  const muPriceTxt = muPriceRow.addText(`$${mu.price.toFixed(2)}`);
  muPriceTxt.font = Font.boldRoundedSystemFont(17);
  muPriceTxt.textColor = Color.white();
  muPriceRow.addSpacer(5);

  const muColor = mu.changePct >= 0 ? new Color("#10B981") : new Color("#EF4444");
  const muChgTxt = muPriceRow.addText(`${mu.changePct >= 0 ? "▲" : "▼"}${Math.abs(mu.changePct).toFixed(2)}%`);
  muChgTxt.font = Font.boldSystemFont(11);
  muChgTxt.textColor = muColor;

  muCol.addSpacer(3);
  const muKeyTxt = muCol.addText(`守 $${PORTFOLIO.muDefense} | 壓 $${PORTFOLIO.muResistance1}`);
  muKeyTxt.font = Font.systemFont(9.5);
  muKeyTxt.textColor = new Color("#CBD5E1");

  mainStack.addSpacer(8);

  // 右欄：MUU 2倍槓桿 ETF
  const muuCol = mainStack.addStack();
  muuCol.layoutVertically();
  muuCol.backgroundColor = new Color("#1E293B", 0.7);
  muuCol.cornerRadius = 8;
  muuCol.setPadding(8, 10, 8, 10);

  const muuHeader = muuCol.addStack();
  const muuSym = muuHeader.addText("MUU ");
  muuSym.font = Font.boldSystemFont(13);
  muuSym.textColor = new Color("#F59E0B");
  const muuSub = muuHeader.addText("2X 做多");
  muuSub.font = Font.systemFont(10);
  muuSub.textColor = new Color("#94A3B8");

  muuCol.addSpacer(2);
  const muuPriceRow = muuCol.addStack();
  muuPriceRow.bottomAlignContent();
  const muuPriceTxt = muuPriceRow.addText(`$${muu.price.toFixed(2)}`);
  muuPriceTxt.font = Font.boldRoundedSystemFont(17);
  muuPriceTxt.textColor = Color.white();
  muuPriceRow.addSpacer(5);

  const muuColor = muu.changePct >= 0 ? new Color("#10B981") : new Color("#EF4444");
  const muuChgTxt = muuPriceRow.addText(`${muu.changePct >= 0 ? "▲" : "▼"}${Math.abs(muu.changePct).toFixed(2)}%`);
  muuChgTxt.font = Font.boldSystemFont(11);
  muuChgTxt.textColor = muuColor;

  // 計算 50 股游擊倉即時損益
  const swingPnlPct = ((muu.price - PORTFOLIO.swingCost) / PORTFOLIO.swingCost) * 100;
  muuCol.addSpacer(3);
  const muuKeyTxt = muuCol.addText(`游擊50股(@${PORTFOLIO.swingCost}): ${swingPnlPct >= 0 ? "+" : ""}${swingPnlPct.toFixed(1)}%`);
  muuKeyTxt.font = Font.systemFont(9.5);
  muuKeyTxt.textColor = swingPnlPct >= 0 ? new Color("#34D399") : new Color("#FCA5A5");

  w.addSpacer(8);

  // --- 底部：持倉市值與操作提示列 ---
  const marketVal = muu.price * PORTFOLIO.totalShares;
  const totalPnl = marketVal - PORTFOLIO.totalCost;
  const totalPnlPct = (totalPnl / PORTFOLIO.totalCost) * 100;

  const footerStack = w.addStack();
  footerStack.layoutHorizontally();
  footerStack.centerAlignContent();

  const posTxt = footerStack.addText(
    `持倉 ${PORTFOLIO.totalShares}股(均$${PORTFOLIO.avgCost.toFixed(2)}) | 市值 $${Math.round(marketVal).toLocaleString()} (${totalPnlPct.toFixed(1)}%)`
  );
  posTxt.font = Font.mediumSystemFont(10);
  posTxt.textColor = new Color("#94A3B8");

  footerStack.addSpacer();

  const now = new Date();
  const timeStr = `${String(now.getHours()).padStart(2, "0")}:${String(now.getMinutes()).padStart(2, "0")}`;
  const timeTxt = footerStack.addText(`更新 ${timeStr}`);
  timeTxt.font = Font.systemFont(9);
  timeTxt.textColor = new Color("#64748B");

  return w;
}

const widget = await createWidget();
if (config.runsInWidget) {
  Script.setWidget(widget);
} else {
  await widget.presentMedium();
}
Script.complete();
