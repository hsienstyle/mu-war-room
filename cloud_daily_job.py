#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
☁️ 美股記憶體 (MU / MUU) 與 2059 川湖 — GitHub Actions 雲端每日全自動戰情腳本
功能：
1. 自動抓取 Yahoo Finance 最新收盤價、高低點與漲跌幅 (MU, MUU, 2059.TW, NVDA, AMD)
2. 自動抓取 Google News 繁體中文最新新聞 + Yahoo Finance 英文外電 (美光 MU / HBM / 2059 川湖)
3. 自動呼叫 Gemini (gemini-2.5-flash) 翻譯外電並結合當日股價與持倉撰寫繁體中文戰情洞察
4. 自動更新 iOS 戰情室 (index.html 與 MU_MUU_Widget.js) 基準數據
5. 自動透過 LINE Messaging API 發送每日早晨戰情推播至手機
"""

import json
import os
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta

TW_TZ = timezone(timedelta(hours=8))
NOW_TW = datetime.now(TW_TZ)
TODAY_STR = NOW_TW.strftime("%Y-%m-%d")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "portfolio_config.json")
INDEX_PATH = os.path.join(BASE_DIR, "index.html")
WIDGET_PATH = os.path.join(BASE_DIR, "MU_MUU_Widget.js")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
}


def fetch_yahoo_quote(symbol, fallback):
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(symbol)}?interval=1d&range=5d"
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        result = data["chart"]["result"][0]
        meta = result["meta"]
        quotes = result["indicators"]["quote"][0]
        closes = [c for c in quotes.get("close", []) if c is not None]
        highs = [h for h in quotes.get("high", []) if h is not None]
        lows = [l for l in quotes.get("low", []) if l is not None]

        price = float(meta.get("regularMarketPrice") or closes[-1])
        prev_close = float(closes[-2]) if len(closes) >= 2 else float(meta.get("chartPreviousClose", price))
        day_high = float(meta.get("regularMarketDayHigh") or (highs[-1] if highs else price))
        day_low = float(meta.get("regularMarketDayLow") or (lows[-1] if lows else price))
        change_pct = ((price - prev_close) / prev_close) * 100.0 if prev_close else 0.0

        return {
            "price": round(price, 2),
            "prev_close": round(prev_close, 2),
            "high": round(day_high, 2),
            "low": round(day_low, 2),
            "change_pct": round(change_pct, 2),
        }
    except Exception as e:
        print(f"[WARN] Yahoo quote failed for {symbol}: {e}")
        return fallback


def fetch_google_news_tw(query, max_items=3):
    rss_url = f"https://news.google.com/rss/search?q={urllib.parse.quote(query)}&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"
    try:
        req = urllib.request.Request(rss_url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=10) as resp:
            xml_bytes = resp.read()
        root = ET.fromstring(xml_bytes)
        items = []
        for item in root.findall("./channel/item")[:max_items]:
            title = item.findtext("title") or ""
            title_clean = re.sub(r"\s*-\s*[^-]+$", "", title).strip()
            link = item.findtext("link") or ""
            if title_clean:
                items.append({"title": title_clean, "link": link})
        return items
    except Exception as e:
        print(f"[WARN] Google News RSS failed for {query}: {e}")
        return []


def fetch_yahoo_us_rss(symbols="MU,NVDA,AMD", max_items=3):
    rss_url = f"https://feeds.finance.yahoo.com/rss/2.0/headline?s={symbols}&region=US&lang=en-US"
    try:
        req = urllib.request.Request(rss_url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=10) as resp:
            xml_bytes = resp.read()
        root = ET.fromstring(xml_bytes)
        items = []
        for item in root.findall("./channel/item")[:max_items]:
            title = (item.findtext("title") or "").strip()
            link = item.findtext("link") or ""
            if title:
                items.append({"title": title, "link": link})
        return items
    except Exception as e:
        print(f"[WARN] Yahoo US RSS failed: {e}")
        return []


def generate_gemini_summary(mu, muu, tw2059, news_items, cfg):
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        return None

    headlines_text = "\n".join([f"- {n['title']}" for n in news_items]) if news_items else "無最新標題"
    p_muu = cfg["muu"]
    prompt = f"""你是專業的美股記憶體 (MU/MUU) 雙層戰情分析師。請根據以下今日最新市場數據與外電標題，用繁體中文撰寫 3 點精簡扼要（每點約 45~65 字）的晨間分析（不要加開場白）：
1. 【行情與外電重點】：結合今日 MU 走勢與最新外電/台股新聞提煉關鍵驅動因素。
2. 【技術面關鍵價位】：評估 MU 收盤 (${mu['price']}) 相對於波段前低防守線 (${cfg['levels']['mu_defense']}) 與第一頸線壓力 ($905~$920) 的多空強弱。
3. 【MUU 做T與游擊倉建議】：針對目前持有的 {p_muu['total_shares']} 股 MUU（實質均價 ${p_muu['avg_cost_usd']}，含 {p_muu['swing_shares']} 股 @${p_muu['swing_cost']} 游擊倉）給出今日明確操作建議。

今日數據：
- MU 收盤：${mu['price']} ({mu['change_pct']:+.2f}%)，盤中高 ${mu['high']} / 低 ${mu['low']}
- MUU 收盤：${muu['price']} ({muu['change_pct']:+.2f}%)，盤中高 ${muu['high']} / 低 ${muu['low']}
- 川湖 (2059.TW) 收盤：{tw2059['price']} 元 ({tw2059['change_pct']:+.2f}%)
- 最新國內外新聞標題：
{headlines_text}
"""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.3, "maxOutputTokens": 450}
    }
    try:
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=20) as resp:
            res_data = json.loads(resp.read().decode("utf-8"))
        text = res_data["candidates"][0]["content"]["parts"][0]["text"].strip()
        return text
    except Exception as e:
        print(f"[WARN] Gemini API call skipped/failed: {e}")
        return None


def build_tactical_commentary(mu, muu, cfg):
    defense = cfg["levels"]["mu_defense"]
    res1_min = cfg["levels"]["mu_res1_min"]
    if mu["price"] >= res1_min:
        return f"👉 MU 成功站上 ${res1_min:.0f} 頸線反壓區！短線多頭動能轉強，游擊 {cfg['muu']['swing_shares']} 股 (@${cfg['muu']['swing_cost']}) 可於 $25.80~$26.80 擇機分批獲利收割。"
    elif mu["price"] >= defense:
        return f"👉 MU 低點守穩波段防守線 (${defense}) 之上，底層雙底結構完整，拉回不破前低皆以續抱與游擊倉等待反彈 ($905~$920) 為主。"
    else:
        return f"⚠️ MU 收盤跌破 ${defense} 波段前低防守線，短線技術面轉弱，請嚴格執行風險控管並暫停加碼，靜待止跌訊號。"


def update_frontend_files(mu, muu, headline):
    if os.path.exists(INDEX_PATH):
        with open(INDEX_PATH, "r", encoding="utf-8") as f:
            html = f.read()

        html = re.sub(r"muPrice:\s*[\d.]+", f"muPrice: {mu['price']}", html)
        html = re.sub(r"muPrevClose:\s*[\d.]+", f"muPrevClose: {mu['prev_close']}", html)
        html = re.sub(r"muuPrice:\s*[\d.]+", f"muuPrice: {muu['price']}", html)
        html = re.sub(r"muuPrevClose:\s*[\d.]+", f"muuPrevClose: {muu['prev_close']}", html)
        html = re.sub(r'id="mu-price">\$[\d.]+<', f'id="mu-price">${mu["price"]:.2f}<', html)
        html = re.sub(r'id="muu-price">\$[\d.]+<', f'id="muu-price">${muu["price"]:.2f}<', html)

        with open(INDEX_PATH, "w", encoding="utf-8") as f:
            f.write(html)

    if os.path.exists(WIDGET_PATH):
        with open(WIDGET_PATH, "r", encoding="utf-8") as f:
            js = f.read()

        js = re.sub(
            r"MU:\s*\{[^}]+\}",
            f"MU: {{ price: {mu['price']}, prevClose: {mu['prev_close']}, changePct: {mu['change_pct']} }}",
            js
        )
        js = re.sub(
            r"MUU:\s*\{[^}]+\}",
            f"MUU: {{ price: {muu['price']}, prevClose: {muu['prev_close']}, changePct: {muu['change_pct']} }}",
            js
        )
        if headline:
            safe_hl = headline.replace('"', '\\"')
            js = re.sub(r'headline:\s*"[^"]*"', f'headline: "{safe_hl}"', js)

        with open(WIDGET_PATH, "w", encoding="utf-8") as f:
            f.write(js)


def send_line_push(message_text):
    token = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN", "").strip()
    user_id = os.environ.get("LINE_USER_ID", "").strip()
    if not token or not user_id:
        print("[WARN] LINE_CHANNEL_ACCESS_TOKEN or LINE_USER_ID not set. Skipping LINE push.")
        return False

    url = "https://api.line.me/v2/bot/message/push"
    payload = {
        "to": user_id,
        "messages": [{"type": "text", "text": message_text[:4900]}]
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json; charset=utf-8"
        },
        method="POST"
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        res_body = resp.read().decode("utf-8")
        print(f"[OK] LINE Push succeeded: {res_body}")
        return True


def main():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        cfg = json.load(f)

    mu = fetch_yahoo_quote("MU", {"price": 884.74, "prev_close": 934.27, "high": 906.54, "low": 861.59, "change_pct": -5.30})
    muu = fetch_yahoo_quote("MUU", {"price": 24.08, "prev_close": 27.00, "high": 25.35, "low": 22.76, "change_pct": -10.82})
    tw2059 = fetch_yahoo_quote("2059.TW", {"price": 9880.0, "prev_close": 10150.0, "high": 9950.0, "low": 9720.0, "change_pct": -2.66})

    mu_news = fetch_google_news_tw("美光 MU OR HBM 記憶體", max_items=2)
    tw_news = fetch_google_news_tw("2059 川湖", max_items=1)
    us_news = fetch_yahoo_us_rss("MU,NVDA,AMD", max_items=2)
    all_news = mu_news + tw_news + us_news

    top_headline = mu_news[0]["title"] if mu_news else "美光大幅調升2027 HBM合約價！花旗上調MU目標價至$1300"

    update_frontend_files(mu, muu, top_headline)

    p_muu = cfg["muu"]
    mkt_val = round(muu["price"] * p_muu["total_shares"], 2)
    unrealized_usd = round(mkt_val - p_muu["total_cost_usd"], 2)
    unrealized_pct = round((unrealized_usd / p_muu["total_cost_usd"]) * 100.0, 2)

    swing_diff_pct = round(((muu["price"] - p_muu["swing_cost"]) / p_muu["swing_cost"]) * 100.0, 2)
    swing_diff_usd = round((muu["price"] - p_muu["swing_cost"]) * p_muu["swing_shares"], 2)

    tactical_line = build_tactical_commentary(mu, muu, cfg)
    gemini_insight = generate_gemini_summary(mu, muu, tw2059, all_news, cfg)

    if gemini_insight:
        news_block = gemini_insight
    elif all_news:
        news_block = "\n".join([f"{i+1}. {n['title']}" for i, n in enumerate(all_news[:4])])
    else:
        news_block = "1. 美光 2026 HBM 全數售罄並調漲 2027 長約價，花旗看多目標價 $1,300。\n2. 川湖 (2059) 啟動百億 CB 募資擴建全球最大導軌廠。"

    line_msg = f"""☀️【MU / MUU 雲端 AI 戰情日報】
📅 日期：{TODAY_STR}（GitHub + Gemini 自動結算）
━━━━━━━━━━━━━━
📈 美股最新收盤行情：
• MU 收盤：${mu['price']:.2f} ({mu['change_pct']:+.2f}%) 高${mu['high']:.2f} / 低${mu['low']:.2f}
• MUU收盤：${muu['price']:.2f} ({muu['change_pct']:+.2f}%) 高${muu['high']:.2f} / 低${muu['low']:.2f}
{tactical_line}

🧠 Gemini AI 晨間戰情與新聞洞察：
{news_block}

💼 您的最新持倉結算（共 {p_muu['total_shares']:,} 股）：
• 核心倉 {p_muu['core_shares']:,} 股 + 游擊倉 {p_muu['swing_shares']} 股 (@${p_muu['swing_cost']:.2f})
• 實質總成本：${p_muu['total_cost_usd']:,.2f} (均價 ${p_muu['avg_cost_usd']:.3f})
• 最新總市值：${mkt_val:,.2f} USD
• 總未實現損益：{unrealized_usd:+,.2f} USD ({unrealized_pct:+.2f}%)
• ⚡ 游擊{p_muu['swing_shares']}股損益：{swing_diff_usd:+.2f} USD ({swing_diff_pct:+.2f}%，停利目標 $25.8~$26.8)
• 🏭 川湖 (2059.TW)：收盤 {tw2059['price']:,.0f} 元 ({tw2059['change_pct']:+.2f}%)｜持有 {cfg['tw2059']['shares']} 股 (均價 {cfg['tw2059']['avg_cost_twd']:,.0f} 元)

📱 iOS 戰情室已同步更新：
https://hsienstyle.github.io/mu-war-room/"""

    print(line_msg)
    send_line_push(line_msg)


if __name__ == "__main__":
    main()
