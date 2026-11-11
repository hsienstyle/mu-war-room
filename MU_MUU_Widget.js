// Variables used by Scriptable.
// These must be at the very top of the file. Do not edit.
// icon-color: deep-blue; icon-glyph: microchip;

/**
 * 📱 美股記憶體 (MU / MUU) iOS 桌面即時戰情小工具 (含最新新聞頭條)
 * 點擊小工具可直接開啟 GitHub Pages 戰情室 App！
 */

const WAR_ROOM_URL = "https://hsienstyle.github.io/mu-war-room/";

const PORTFOLIO = {
  totalShares: 1250,          // MUU 總股數 (1100核心 + 150游擊)
  avgCost: 34.714,            // 整體實質均價 (USD)
  totalCost: 43392.20,        // 總投入淨成本 (USD)
  swingShares: 150,           // 游擊倉股數 (50股@24.49 + 100股@14.99)
  swingCost: 18.16,           // 游擊倉均價
  muDefense: 656.39,          // MU 11/05 低點防守線
  muResistance1: 780.00       // MU 缺口反壓
};

const FALLBACK_DATA = {
  MU: { price: 725.11, prevClose: 733.15, changePct: -1.1 },
  MUU: { price: 15.1, prevClose: 15.5, changePct: -2.58 },
  headline: "【即時新聞】美光(MU)預估本益比下殺至4.2倍！受惠AI記憶體需求，高盛重申目標價上看1250美元",
  lastPushDate: "2026-11-11"
};

async function fetchQuote(symbol, fallback) {
  try {
    const url = `https://query1.finance.yahoo.com/v8/finance/chart/${encodeURIComponent(symbol)}?interval=1d&range=5d`;
    const req = new Request(url);
    req.timeoutInterval = 5;
    const res = await req.loadJSON();
    const meta = res.chart.result[0].meta;
    const price = meta.regularMarketPrice;
    const prevClose = meta.chartPreviousClose || meta.previousClose;
    const changePct = ((price - prevClose) / prevClose) * 100;
    return { price, prevClose, changePct };
  } catch (e) {
    return fallback;
  }
}

async function fetchLatestHeadline() {
  try {
    const rss = "https://feeds.finance.yahoo.com/rss/2.0/headline?s=MU&region=US&lang=en-US";
    const req = new Request(`https://api.rss2json.com/v1/api.json?rss_url=${encodeURIComponent(rss)}`);
    req.timeoutInterval = 5;
    const res = await req.loadJSON();
    if (res && res.items && res.items.length > 0) {
      return res.items[0].title;
    }
  } catch (e) {}
  return FALLBACK_DATA.headline;
}

async function createWidget() {
  const [mu, muu, headline] = await Promise.all([
    fetchQuote("MU", FALLBACK_DATA.MU),
    fetchQuote("MUU", FALLBACK_DATA.MUU),
    fetchLatestHeadline()
  ]);

  const w = new ListWidget();
  w.url = WAR_ROOM_URL; // 點擊小工具直接打開戰情室網頁 App

  const gradient = new LinearGradient();
  gradient.locations = [0, 1];
  gradient.colors = [new Color("#0B1120"), new Color("#111827")];
  w.backgroundGradient = gradient;
  w.setPadding(10, 13, 10, 13);

  // --- 頂部標題列 ---
  const headerStack = w.addStack();
  headerStack.layoutHorizontally();
  headerStack.centerAlignContent();

  const titleTxt = headerStack.addText("⚡ 美股記憶體戰情室");
  titleTxt.font = Font.boldSystemFont(11.5);
  titleTxt.textColor = new Color("#38BDF8");

  headerStack.addSpacer();

  const statusText = mu.price >= PORTFOLIO.muDefense ? "🛡️雙底守穩" : "⚠️破前低警戒";
  const marketVal = muu.price * PORTFOLIO.totalShares;
  const badgeTxt = headerStack.addText(`${statusText} | 市值 $${Math.round(marketVal).toLocaleString()}`);
  badgeTxt.font = Font.mediumSystemFont(9.5);
  badgeTxt.textColor = new Color("#94A3B8");

  w.addSpacer(6);

  // --- 中段：MU 與 MUU 雙欄核心報價 ---
  const mainStack = w.addStack();
  mainStack.layoutHorizontally();

  // 左欄：MU 底層正股
  const muCol = mainStack.addStack();
  muCol.layoutVertically();
  muCol.backgroundColor = new Color("#1E293B", 0.7);
  muCol.cornerRadius = 8;
  muCol.setPadding(6, 9, 6, 9);

  const muHeader = muCol.addStack();
  const muSym = muHeader.addText("MU ");
  muSym.font = Font.boldSystemFont(12);
  muSym.textColor = Color.white();
  const muSub = muHeader.addText(`守$${PORTFOLIO.muDefense}`);
  muSub.font = Font.systemFont(9.5);
  muSub.textColor = new Color("#94A3B8");

  muCol.addSpacer(2);
  const muPriceRow = muCol.addStack();
  muPriceRow.bottomAlignContent();
  const muPriceTxt = muPriceRow.addText(`$${mu.price.toFixed(2)}`);
  muPriceTxt.font = Font.boldRoundedSystemFont(15.5);
  muPriceTxt.textColor = Color.white();
  muPriceRow.addSpacer(4);

  const muColor = mu.changePct >= 0 ? new Color("#10B981") : new Color("#EF4444");
  const muChgTxt = muPriceRow.addText(`${mu.changePct >= 0 ? "▲" : "▼"}${Math.abs(mu.changePct).toFixed(2)}%`);
  muChgTxt.font = Font.boldSystemFont(10);
  muChgTxt.textColor = muColor;

  mainStack.addSpacer(8);

  // 右欄：MUU 2倍槓桿 ETF
  const muuCol = mainStack.addStack();
  muuCol.layoutVertically();
  muuCol.backgroundColor = new Color("#1E293B", 0.7);
  muuCol.cornerRadius = 8;
  muuCol.setPadding(6, 9, 6, 9);

  const swingPnlPct = ((muu.price - PORTFOLIO.swingCost) / PORTFOLIO.swingCost) * 100;
  const muuHeader = muuCol.addStack();
  const muuSym = muuHeader.addText("MUU ");
  muuSym.font = Font.boldSystemFont(12);
  muuSym.textColor = new Color("#F59E0B");
  const muuSub = muuHeader.addText(`游擊 ${swingPnlPct >= 0 ? "+" : ""}${swingPnlPct.toFixed(1)}%`);
  muuSub.font = Font.systemFont(9.5);
  muuSub.textColor = swingPnlPct >= 0 ? new Color("#34D399") : new Color("#FCA5A5");

  muuCol.addSpacer(2);
  const muuPriceRow = muuCol.addStack();
  muuPriceRow.bottomAlignContent();
  const muuPriceTxt = muuPriceRow.addText(`$${muu.price.toFixed(2)}`);
  muuPriceTxt.font = Font.boldRoundedSystemFont(15.5);
  muuPriceTxt.textColor = Color.white();
  muuPriceRow.addSpacer(4);

  const muuColor = muu.changePct >= 0 ? new Color("#10B981") : new Color("#EF4444");
  const muuChgTxt = muuPriceRow.addText(`${muu.changePct >= 0 ? "▲" : "▼"}${Math.abs(muu.changePct).toFixed(2)}%`);
  muuChgTxt.font = Font.boldSystemFont(10);
  muuChgTxt.textColor = muuColor;

  w.addSpacer(6);

  // --- 底部：最新新聞頭條列 ---
  const newsStack = w.addStack();
  newsStack.layoutHorizontally();
  newsStack.centerAlignContent();
  newsStack.backgroundColor = new Color("#0F172A", 0.85);
  newsStack.cornerRadius = 6;
  newsStack.setPadding(4, 7, 4, 7);

  const newsTxt = newsStack.addText(`📰 ${headline}`);
  newsTxt.font = Font.mediumSystemFont(9.5);
  newsTxt.textColor = new Color("#E2E8F0");
  newsTxt.lineLimit = 1;

  return w;
}

const widget = await createWidget();
if (config.runsInWidget) {
  Script.setWidget(widget);
} else {
  await widget.presentMedium();
}
Script.complete();
