#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
☁️ 美股記憶體 (MU / MUU) 與 2059 川湖 — GitHub Actions 雲端每日全自動戰情腳本 (v3 六維度機構級版)
升級項目：
1. 報價三重備援：CNBC JSON API + Stooq CSV + Yahoo query2（美股）＋ TWSE OpenAPI / MIS（台股）
2. 宏觀與同業共振掃描：US10Y（10年美債）、DXY（美元指數）、USD/TWD 匯率（自動換算跨市場總淨值）、
   SOX（費半）、NVDA、WDC、SK Hynix (000660.KS)
3. 衍生品與量化微結構：MU 最近到期選擇權（Put/Call Ratio、Max Pain、最大 Call/Put OI 牆、ATM IV）
   ＋ MUU 實測 5日 / 20日 2X 槓桿波動率耗損（Beta Slippage）＋ MU 5MA / 20MA / RSI(14)
4. 自動更新 iOS 戰情室 (index.html、MU_MUU_Widget.js、dashboard.html) 與 daily_macro_options.json 並發送 LINE 推播
5. 支援 --dry-run 本機測試模式（不發 LINE、不覆蓋網站檔案）
"""

import argparse
import csv
import http.cookiejar
import io
import json
import os
import re
import ssl
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

TW_TZ = timezone(timedelta(hours=8))
NOW_TW = datetime.now(TW_TZ)
TODAY_STR = NOW_TW.strftime("%Y-%m-%d")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "portfolio_config.json")
INDEX_PATH = os.path.join(BASE_DIR, "index.html")
WIDGET_PATH = os.path.join(BASE_DIR, "MU_MUU_Widget.js")
LAST_RUN_PATH = os.path.join(BASE_DIR, "last_run_date.txt")
MACRO_JSON_PATH = os.path.join(BASE_DIR, "daily_macro_options.json")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
    "Accept": "application/json,text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

SSL_CTX = ssl.create_default_context()


def http_get_text(url, timeout=12, extra_headers=None):
    hdrs = dict(HEADERS)
    if extra_headers:
        hdrs.update(extra_headers)
    req = urllib.request.Request(url, headers=hdrs)
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=SSL_CTX) as resp:
            return resp.read().decode("utf-8", errors="ignore")
    except (ssl.SSLError, urllib.error.URLError) as e:
        if isinstance(e, ssl.SSLError) or isinstance(getattr(e, "reason", None), ssl.SSLError):
            unverified = ssl._create_unverified_context()
            with urllib.request.urlopen(req, timeout=timeout, context=unverified) as resp:
                return resp.read().decode("utf-8", errors="ignore")
        raise


def to_float(val, default=0.0):
    if val is None:
        return default
    s = str(val).strip().replace(",", "").replace("%", "").replace("+", "")
    if not s or s in ("--", "-", "N/A", "UNCH"):
        return default
    try:
        return float(s)
    except ValueError:
        return default


def fetch_cnbc_quote(symbol):
    """來源 1：CNBC 即時報價 JSON API（不擋 GitHub Actions 雲端 IP）"""
    url = (
        "https://quote.cnbc.com/quote-html-webservice/restQuote/symbolType/symbol"
        f"?symbols={urllib.parse.quote(symbol)}&requestMethod=itv&noform=1&partnerId=2&fund=1&exthrs=1&output=json"
    )
    data = json.loads(http_get_text(url, timeout=10))
    q = data["FormattedQuoteResult"]["FormattedQuote"][0]
    price = to_float(q.get("last"))
    if price <= 0:
        raise ValueError(f"CNBC invalid price for {symbol}")
    prev_close = to_float(q.get("previous_day_closing"), price)
    high = to_float(q.get("high"), price)
    low = to_float(q.get("low"), price)
    raw_chg_pct = q.get("change_pct")
    if raw_chg_pct is not None and str(raw_chg_pct).strip() not in ("", "--", "N/A"):
        change_pct = to_float(raw_chg_pct, 0.0)
        if abs(price - prev_close) < 1e-6 and abs(change_pct) > 1e-6:
            prev_close = price / (1.0 + change_pct / 100.0)
    else:
        change_pct = ((price - prev_close) / prev_close) * 100.0 if prev_close else 0.0
    return {
        "price": round(price, 3 if price < 10 else 2),
        "prev_close": round(prev_close, 3 if prev_close < 10 else 2),
        "high": round(high, 2),
        "low": round(low, 2),
        "change_pct": round(change_pct, 2),
    }


def fetch_stooq_quote(stooq_sym):
    """來源 2：Stooq 歷史日線 CSV（穩定免金鑰）"""
    url = f"https://stooq.com/q/d/l/?s={urllib.parse.quote(stooq_sym)}&i=d"
    text = http_get_text(url, timeout=10)
    rows = list(csv.DictReader(io.StringIO(text)))
    if len(rows) < 2:
        raise ValueError("Stooq insufficient rows")
    last = rows[-1]
    prev = rows[-2]
    price = float(last["Close"])
    prev_close = float(prev["Close"])
    high = float(last["High"])
    low = float(last["Low"])
    change_pct = ((price - prev_close) / prev_close) * 100.0 if prev_close else 0.0
    return {
        "price": round(price, 2),
        "prev_close": round(prev_close, 2),
        "high": round(high, 2),
        "low": round(low, 2),
        "change_pct": round(change_pct, 2),
    }


def fetch_yahoo_quote(symbol):
    """來源 3：Yahoo Finance query2 端點"""
    url = f"https://query2.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(symbol)}?interval=1d&range=5d"
    data = json.loads(http_get_text(url, timeout=10))
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
        "price": round(price, 3 if price < 10 else 2),
        "prev_close": round(prev_close, 3 if prev_close < 10 else 2),
        "high": round(day_high, 2),
        "low": round(day_low, 2),
        "change_pct": round(change_pct, 2),
    }


def fetch_twse_daily(stock_no):
    """台股來源 1：證交所 OpenAPI 最新交易日收盤"""
    rows = json.loads(http_get_text("https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL", timeout=15))
    row = next(r for r in rows if r.get("Code") == stock_no)
    price = to_float(row["ClosingPrice"])
    change = to_float(row.get("Change"), 0.0)
    prev_close = price - change
    return {
        "price": round(price, 2),
        "prev_close": round(prev_close, 2),
        "high": round(to_float(row["HighestPrice"], price), 2),
        "low": round(to_float(row["LowestPrice"], price), 2),
        "change_pct": round((change / prev_close) * 100.0, 2) if prev_close else 0.0,
    }


def fetch_twse_quote(stock_no):
    """台股來源 2：臺灣證交所官方即時報價 API"""
    url = f"https://mis.twse.com.tw/stock/api/getStockInfo.jsp?ex_ch=tse_{stock_no}.tw&json=1&delay=0"
    data = json.loads(http_get_text(url, timeout=10))
    info = data["msgArray"][0]
    prev_close = float(info["y"])
    last = info.get("z", "-")
    price = float(last) if last not in ("-", "", None) else prev_close
    high = float(info["h"]) if info.get("h") not in ("-", "", None) else price
    low = float(info["l"]) if info.get("l") not in ("-", "", None) else price
    change_pct = ((price - prev_close) / prev_close) * 100.0 if prev_close else 0.0
    return {
        "price": round(price, 2),
        "prev_close": round(prev_close, 2),
        "high": round(high, 2),
        "low": round(low, 2),
        "change_pct": round(change_pct, 2),
    }


def fetch_quote_multi(symbol, stooq_sym, fallback):
    if symbol.endswith(".TW"):
        try:
            q = fetch_twse_daily(symbol.replace(".TW", ""))
            print(f"[OK] TWSE daily close for {symbol}: {q['price']} ({q['change_pct']:+.2f}%)")
            return q
        except Exception as e:
            print(f"[WARN] TWSE daily failed for {symbol}: {e}")
        try:
            q = fetch_twse_quote(symbol.replace(".TW", ""))
            print(f"[OK] TWSE quote for {symbol}: {q['price']} ({q['change_pct']:+.2f}%)")
            return q
        except Exception as e:
            print(f"[WARN] TWSE failed for {symbol}: {e}")

    if not symbol.endswith(".TW"):
        try:
            q = fetch_cnbc_quote(symbol)
            print(f"[OK] CNBC quote for {symbol}: {q['price']} ({q['change_pct']:+.2f}%)")
            return q
        except Exception as e:
            print(f"[WARN] CNBC failed for {symbol}: {e}")

    if stooq_sym:
        try:
            q = fetch_stooq_quote(stooq_sym)
            print(f"[OK] Stooq quote for {symbol}: {q['price']} ({q['change_pct']:+.2f}%)")
            return q
        except Exception as e:
            print(f"[WARN] Stooq failed for {symbol}: {e}")

    try:
        q = fetch_yahoo_quote(symbol)
        print(f"[OK] Yahoo quote for {symbol}: {q['price']} ({q['change_pct']:+.2f}%)")
        return q
    except Exception as e:
        print(f"[WARN] Yahoo failed for {symbol}: {e}")
        return fallback


def fetch_macro_and_peers():
    """抓取總經指標 (US10Y, DXY, USD/TWD) 與同業共振 (SOX, NVDA, WDC, STX/AVGO)"""
    specs = [
        ("us10y", "US10Y", "^TNX", 0.1),     # Yahoo ^TNX 為 10 倍 (50.9 -> 5.09%)
        ("dxy", ".DXY", "DX-Y.NYB", 1.0),
        ("usdtwd", "TWD=", "TWD=X", 1.0),
        ("sox", ".SOX", "^SOX", 1.0),
        ("nvda", "NVDA", "NVDA", 1.0),
        ("wdc", "WDC", "WDC", 1.0),
        ("avgo", "AVGO", "AVGO", 1.0),
    ]
    out = {}
    for key, cnbc_sym, yahoo_sym, y_scale in specs:
        got = None
        try:
            got = fetch_cnbc_quote(cnbc_sym)
            if key == "us10y" and got["price"] > 20:
                got["price"] = round(got["price"] / 10.0, 3)
                got["prev_close"] = round(got["prev_close"] / 10.0, 3)
        except Exception:
            try:
                got = fetch_yahoo_quote(yahoo_sym)
                if y_scale != 1.0:
                    got["price"] = round(got["price"] * y_scale, 3)
                    got["prev_close"] = round(got["prev_close"] * y_scale, 3)
            except Exception as e2:
                print(f"[WARN] Macro/Peer failed for {key}: {e2}")
        if got:
            out[key] = got
            print(f"[OK] Macro/Peer {key}: {got['price']} ({got['change_pct']:+.2f}%)")
    return out


def fetch_daily_closes(symbol, days=35):
    """抓取近期日線收盤價（CNBC 3M Harmony API 優先 -> Yahoo -> Stooq 備援）"""
    try:
        url = f"https://ts-api.cnbc.com/harmony/app/charts/3M.json?symbol={urllib.parse.quote(symbol)}"
        data = json.loads(http_get_text(url, timeout=12))
        bars = data.get("barData", {}).get("priceBars") or []
        by_date = {}
        for b in bars:
            tt = str(b.get("tradeTime", ""))
            c = to_float(b.get("close"), 0.0)
            if len(tt) >= 8 and c > 0:
                d_str = f"{tt[0:4]}-{tt[4:6]}-{tt[6:8]}"
                by_date[d_str] = c
        pairs = [(d, by_date[d]) for d in sorted(by_date.keys())]
        if len(pairs) >= 10:
            return pairs[-days:]
    except Exception as e:
        print(f"[WARN] CNBC 3M history failed for {symbol}: {e}")

    try:
        url = f"https://query2.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(symbol)}?interval=1d&range=3mo"
        data = json.loads(http_get_text(url, timeout=10))
        res = data["chart"]["result"][0]
        ts = res.get("timestamp") or []
        closes = res["indicators"]["quote"][0].get("close") or []
        pairs = []
        for t, c in zip(ts, closes):
            if c is not None:
                d_str = datetime.fromtimestamp(t, tz=timezone.utc).strftime("%Y-%m-%d")
                pairs.append((d_str, float(c)))
        if len(pairs) >= 10:
            return pairs[-days:]
    except Exception as e:
        print(f"[WARN] Yahoo history failed for {symbol}: {e}")

    try:
        stooq_sym = f"{symbol.lower()}.us"
        text = http_get_text(f"https://stooq.com/q/d/l/?s={stooq_sym}&i=d", timeout=10)
        rows = list(csv.DictReader(io.StringIO(text)))
        pairs = [(r["Date"], float(r["Close"])) for r in rows if r.get("Close")]
        if len(pairs) >= 10:
            return pairs[-days:]
    except Exception as e:
        print(f"[WARN] Stooq history failed for {symbol}: {e}")
    return []


def compute_mu_tech_and_slippage():
    """計算 MU 5MA / 20MA / RSI(14) 以及 MUU 實測 5日 / 20日 2X 波動率耗損"""
    mu_hist = fetch_daily_closes("MU", days=35)
    muu_hist = fetch_daily_closes("MUU", days=35)
    res = {}

    if len(mu_hist) >= 15:
        closes = [c for _, c in mu_hist]
        res["mu_ma5"] = round(sum(closes[-5:]) / 5.0, 2)
        if len(closes) >= 20:
            res["mu_ma20"] = round(sum(closes[-20:]) / 20.0, 2)
        # 計算 Wilder 14 日 RSI
        deltas = [closes[i] - closes[i - 1] for i in range(1, len(closes))]
        gains = [max(d, 0.0) for d in deltas[-14:]]
        losses = [max(-d, 0.0) for d in deltas[-14:]]
        avg_g = sum(gains) / 14.0
        avg_l = sum(losses) / 14.0
        rsi14 = 100.0 if avg_l == 0 else (100.0 - 100.0 / (1.0 + avg_g / avg_l))
        res["mu_rsi14"] = round(rsi14, 1)

    # 對齊共同日期計算 5日 / 20日 2X 槓桿耗損
    mu_map = dict(mu_hist)
    muu_map = dict(muu_hist)
    common_dates = sorted(set(mu_map.keys()) & set(muu_map.keys()))
    for win in (5, 20):
        if len(common_dates) > win:
            d0 = common_dates[-1 - win]
            d1 = common_dates[-1]
            mu_ret = ((mu_map[d1] - mu_map[d0]) / mu_map[d0]) * 100.0
            muu_ret = ((muu_map[d1] - muu_map[d0]) / muu_map[d0]) * 100.0
            ideal_2x = mu_ret * 2.0
            slippage = muu_ret - ideal_2x
            res[f"slippage_{win}d"] = {
                "from_date": d0,
                "to_date": d1,
                "mu_ret_pct": round(mu_ret, 2),
                "ideal_2x_pct": round(ideal_2x, 2),
                "muu_ret_pct": round(muu_ret, 2),
                "slippage_pct": round(slippage, 2),
            }
    if res:
        print(f"[OK] MU tech & MUU slippage computed: {json.dumps(res, ensure_ascii=False)}")
    return res


def fetch_mu_options_microstructure(spot_price):
    """抓取 MU 最近有效到期選擇權鏈（CBOE 官方免費公開 API，零 429 風險）
    計算 Put/Call Ratio、Max Pain、Call/Put OI 牆、ATM IV 與淨 Gamma Exposure (Net GEX)
    """
    try:
        url = "https://cdn.cboe.com/api/global/delayed_quotes/options/MU.json"
        data = json.loads(http_get_text(url, timeout=20))
        all_opts = data.get("data", {}).get("options") or []
        if not all_opts:
            return None

        # 依到期日分組（解析 OCC 代碼如 MU261120C00700000）
        pat = re.compile(r"^MU(\d{6})([CP])(\d{8})$")
        today_us = (NOW_TW - timedelta(hours=13)).strftime("%Y-%m-%d")
        by_exp = {}
        for o in all_opts:
            m = pat.match(str(o.get("option", "")))
            if not m:
                continue
            yymmdd, side, strike_raw = m.group(1), m.group(2), m.group(3)
            exp_iso = f"20{yymmdd[0:2]}-{yymmdd[2:4]}-{yymmdd[4:6]}"
            if exp_iso < today_us:
                continue
            strike = int(strike_raw) / 1000.0
            rec = {
                "strike": strike,
                "oi": int(o.get("open_interest") or 0),
                "vol": int(o.get("volume") or 0),
                "iv": float(o.get("iv") or 0.0),
                "gamma": float(o.get("gamma") or 0.0),
            }
            bucket = by_exp.setdefault(exp_iso, {"C": [], "P": []})
            bucket[side].append(rec)

        # 選擇最近一個且具足夠 OI (>= 1000) 的主流週/月選到期日
        target_exp = None
        for exp_iso in sorted(by_exp.keys()):
            tot_oi = sum(x["oi"] for x in by_exp[exp_iso]["C"]) + sum(x["oi"] for x in by_exp[exp_iso]["P"])
            if tot_oi >= 1000:
                target_exp = exp_iso
                break
        if not target_exp and by_exp:
            target_exp = sorted(by_exp.keys())[0]
        if not target_exp:
            return None

        calls = by_exp[target_exp]["C"]
        puts = by_exp[target_exp]["P"]
        call_vol = sum(c["vol"] for c in calls)
        put_vol = sum(p["vol"] for p in puts)
        call_oi = sum(c["oi"] for c in calls)
        put_oi = sum(p["oi"] for p in puts)

        vol_pcr = round(put_vol / call_vol, 2) if call_vol > 0 else None
        oi_pcr = round(put_oi / call_oi, 2) if call_oi > 0 else None

        low_b, high_b = spot_price * 0.75, spot_price * 1.25
        near_calls = [c for c in calls if low_b <= c["strike"] <= high_b] or calls
        near_puts = [p for p in puts if low_b <= p["strike"] <= high_b] or puts
        top_call = max(near_calls, key=lambda x: x["oi"])
        top_put = max(near_puts, key=lambda x: x["oi"])

        # 計算 Max Pain（最小買方總內含價值）
        strikes = sorted({x["strike"] for x in calls + puts if x["oi"] > 0})
        best_strike = None
        min_payout = None
        for k in strikes:
            payout = 0.0
            for c in calls:
                if k > c["strike"] and c["oi"] > 0:
                    payout += (k - c["strike"]) * c["oi"]
            for p in puts:
                if k < p["strike"] and p["oi"] > 0:
                    payout += (p["strike"] - k) * p["oi"]
            if min_payout is None or payout < min_payout:
                min_payout = payout
                best_strike = k

        # ATM 附近隱含波動率平均
        atm_ivs = []
        for item in sorted(calls, key=lambda x: abs(x["strike"] - spot_price))[:2]:
            if 0.05 < item["iv"] < 3.0:
                atm_ivs.append(item["iv"] * 100.0)
        for item in sorted(puts, key=lambda x: abs(x["strike"] - spot_price))[:2]:
            if 0.05 < item["iv"] < 3.0:
                atm_ivs.append(item["iv"] * 100.0)
        atm_iv = round(sum(atm_ivs) / len(atm_ivs), 1) if atm_ivs else None

        # 估算當期 Net GEX（造市商假設 Long Call / Short Put，單位：百萬美元 / 每 1% 波動）
        call_gex = sum(c["gamma"] * c["oi"] * 100.0 * spot_price * (spot_price * 0.01) for c in near_calls)
        put_gex = sum(p["gamma"] * p["oi"] * 100.0 * spot_price * (spot_price * 0.01) for p in near_puts)
        net_gex_m = round((call_gex - put_gex) / 1e6, 2)

        out = {
            "source": "CBOE",
            "expiration": target_exp,
            "max_pain": round(best_strike, 2) if best_strike is not None else None,
            "vol_pcr": vol_pcr,
            "oi_pcr": oi_pcr,
            "call_wall": {"strike": top_call["strike"], "oi": top_call["oi"]},
            "put_wall": {"strike": top_put["strike"], "oi": top_put["oi"]},
            "atm_iv_pct": atm_iv,
            "net_gex_m": net_gex_m,
            "call_oi_total": call_oi,
            "put_oi_total": put_oi,
        }
        print(
            f"[OK] CBOE MU Options ({target_exp}): MaxPain=${out['max_pain']} "
            f"P/C(Vol/OI)={vol_pcr}/{oi_pcr} IV={atm_iv}% NetGEX={net_gex_m:+.2f}M"
        )
        return out
    except Exception as e:
        print(f"[WARN] CBOE MU Options fetch failed: {e}")
        return None


def fetch_google_news_tw(query, max_items=3):
    rss_url = f"https://news.google.com/rss/search?q={urllib.parse.quote(query)}&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"
    try:
        xml_bytes = http_get_text(rss_url, timeout=10).encode("utf-8")
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


def _clean_gemini_plain_text(text):
    """清除 Markdown 粗體 ** 與標題前綴 #，保留乾淨繁體中文純文字"""
    if not text:
        return ""
    cleaned = str(text).replace("**", "")
    cleaned = re.sub(r"^\s*#+\s*", "", cleaned, flags=re.MULTILINE)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def call_gemini_text(api_key, prompt, max_tokens=1024, temperature=0.3):
    """統一呼叫 Gemini REST API：依序嘗試 gemini-2.5-flash -> gemini-2.5-flash-lite -> gemini-3-flash-preview"""
    if not api_key:
        return None

    model_specs = [
        ("gemini-2.5-flash", True),
        ("gemini-2.5-flash-lite", True),
        ("gemini-3-flash-preview", False),
    ]
    for model_name, use_thinking_zero in model_specs:
        gen_cfg = {
            "temperature": temperature,
            "maxOutputTokens": max_tokens,
        }
        if use_thinking_zero:
            gen_cfg["thinkingConfig"] = {"thinkingBudget": 0}
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": gen_cfg,
        }
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            try:
                with urllib.request.urlopen(req, timeout=25, context=SSL_CTX) as resp:
                    res_data = json.loads(resp.read().decode("utf-8"))
            except (ssl.SSLError, urllib.error.URLError) as ssl_err:
                if isinstance(ssl_err, ssl.SSLError) or isinstance(getattr(ssl_err, "reason", None), ssl.SSLError):
                    unverified = ssl._create_unverified_context()
                    with urllib.request.urlopen(req, timeout=25, context=unverified) as resp:
                        res_data = json.loads(resp.read().decode("utf-8"))
                else:
                    raise
            candidates = res_data.get("candidates") or []
            if not candidates:
                raise ValueError("Empty candidates in Gemini response")
            parts = (candidates[0].get("content") or {}).get("parts") or []
            raw_text = "".join(p.get("text", "") for p in parts).strip()
            clean_text = _clean_gemini_plain_text(raw_text)
            if clean_text:
                print(f"[OK] Gemini response generated using {model_name}")
                return clean_text
        except Exception as e:
            print(f"[WARN] {model_name} skipped/failed: {e}")
    return None


def _fmt_signed_score(score):
    return f"{score:+d}" if score != 0 else "0"


def _parse_agent_score_and_text(raw_text, default_score=0):
    """解析專職分析師回傳的 (-5 ~ +5) 分數與 60~80 字純文字分析"""
    cleaned = _clean_gemini_plain_text(raw_text)
    if not cleaned:
        return default_score, ""

    score = default_score
    m = re.search(r"(?:分數|評分|score)\s*[:：]?\s*([+-]?\s*\d+)", cleaned, flags=re.IGNORECASE)
    if m:
        try:
            score = int(m.group(1).replace(" ", ""))
        except ValueError:
            score = default_score
    else:
        m2 = re.search(r"([+-]\d+)\s*/\s*5|^\s*([+-]?\d+)\b", cleaned)
        if m2:
            val_s = m2.group(1) or m2.group(2)
            try:
                score = int(val_s)
            except ValueError:
                score = default_score
    score = max(-5, min(5, score))

    # 移除分數行，抽出乾淨分析文字
    lines = [ln.strip() for ln in cleaned.splitlines() if ln.strip()]
    body_lines = []
    for ln in lines:
        if re.match(r"^(?:分數|評分|score)\s*[:：]?\s*[+-]?\s*\d+(?:\s*/\s*5)?\s*$", ln, flags=re.IGNORECASE):
            continue
        ln = re.sub(r"^(?:分數|評分|score)\s*[:：]?\s*[+-]?\s*\d+(?:\s*/\s*5)?\s*[｜|，,。；;]?\s*", "", ln, flags=re.IGNORECASE)
        ln = re.sub(r"^(?:分析|觀點|結論|評論)\s*[:：]\s*", "", ln)
        if ln:
            body_lines.append(ln)
    analysis = " ".join(body_lines).strip() or cleaned
    return score, analysis


def generate_gemini_summary(mu, muu, tw2059, macro, tech_slip, options_info, news_items, cfg):
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        return None

    macro = macro or {}
    tech_slip = tech_slip or {}
    headlines_text = "\n".join([f"- {n['title']}" for n in news_items]) if news_items else "無最新標題"
    p_muu = cfg["muu"]

    macro_lines = []
    if macro.get("us10y"):
        macro_lines.append(f"US10Y 美債殖利率: {macro['us10y']['price']:.2f}% ({macro['us10y']['change_pct']:+.2f}%)")
    if macro.get("sox"):
        macro_lines.append(f"SOX 費半: {macro['sox']['price']:,.1f} ({macro['sox']['change_pct']:+.2f}%)")
    if macro.get("nvda"):
        macro_lines.append(f"NVDA: ${macro['nvda']['price']:.2f} ({macro['nvda']['change_pct']:+.2f}%)")
    if macro.get("wdc"):
        macro_lines.append(f"WDC: ${macro['wdc']['price']:.2f} ({macro['wdc']['change_pct']:+.2f}%)")
    if macro.get("avgo"):
        macro_lines.append(f"AVGO: ${macro['avgo']['price']:.2f} ({macro['avgo']['change_pct']:+.2f}%)")

    opt_line = "無最新選擇權數據"
    if options_info:
        opt_line = (
            f"到期 {options_info['expiration']}｜Max Pain ${options_info['max_pain']}｜"
            f"Vol P/C {options_info['vol_pcr']} / OI P/C {options_info['oi_pcr']}｜"
            f"Call牆 ${options_info['call_wall']['strike']} ({options_info['call_wall']['oi']:,}) / "
            f"Put牆 ${options_info['put_wall']['strike']} ({options_info['put_wall']['oi']:,})｜"
            f"ATM IV {options_info['atm_iv_pct']}%"
        )

    slip20 = tech_slip.get("slippage_20d")
    slip_line = (
        f"20日 MU {slip20['mu_ret_pct']:+.1f}% vs MUU {slip20['muu_ret_pct']:+.1f}% (槓桿耗損 {slip20['slippage_pct']:+.1f}%)"
        if slip20
        else "無"
    )

    prompt = f"""你是機構級美股記憶體 (MU/MUU) 與台股川湖 (2059.TW) 戰情分析師。請根據以下六大維度最新數據，用繁體中文純文字（不可使用 ** 或 # 符號）撰寫 4 點精簡扼要（每點 50~70 字）的晨間分析（不要加任何開場白）：
1. 【總經與同業共振】：結合 US10Y、SOX、NVDA、SK Hynix 與外電，判斷今日走勢是美光個股因素還是大盤/美債估值壓抑。
2. 【技術位階與動能】：結合 MU 收盤 (${mu['price']})、5MA/20MA/RSI(14) 與 200MA 防守線 (${cfg['levels']['mu_defense']}) 評估多空結構。
3. 【選擇權微結構與 MUU 耗損】：解讀 Max Pain、Call/Put OI 牆、P/C Ratio 與 MUU 20日波動率耗損對短線震盪的影響。
4. 【MUU 做T與風控建議】：針對持有 {p_muu['total_shares']} 股 MUU（實質均價 ${p_muu['avg_cost_usd']}，含 {p_muu['swing_shares']} 股 @${p_muu['swing_cost']} 游擊倉）給出今日具體執行與停利/停損紀律。

今日數據：
- MU：${mu['price']} ({mu['change_pct']:+.2f}%)，高 ${mu['high']} / 低 ${mu['low']}｜5MA ${tech_slip.get('mu_ma5', '--')} / 20MA ${tech_slip.get('mu_ma20', '--')} / RSI14 {tech_slip.get('mu_rsi14', '--')}
- MUU：${muu['price']} ({muu['change_pct']:+.2f}%)，高 ${muu['high']} / 低 ${muu['low']}｜{slip_line}
- 川湖 (2059.TW)：{tw2059['price']} 元 ({tw2059['change_pct']:+.2f}%)
- 宏觀與同業：{'｜'.join(macro_lines) if macro_lines else '暫缺'}
- MU 選擇權：{opt_line}
- 最新新聞標題：
{headlines_text}
"""
    return call_gemini_text(api_key, prompt, max_tokens=2048, temperature=0.3)


def generate_gemini_committee_summary(mu, muu, tw2059, macro, tech_slip, options_info, news_items, cfg):
    """雲端免費版 4-Agent 投資委員會：
    Stage 1 (ThreadPoolExecutor 平行 3 專家): macro_agent + quant_agent + bear_agent
    Stage 2 (Synthesizer): cio_agent 統整 3 專家觀點與實盤部位給出最終操作裁決
    回傳 (formatted_summary_text, committee_data_dict)
    """
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        print("[INFO] GEMINI_API_KEY not set; skipping 4-Agent Investment Committee.")
        return None, None

    macro = macro or {}
    tech_slip = tech_slip or {}
    news_items = news_items or []
    p_muu = cfg.get("muu", {})
    p_tw = cfg.get("tw2059", {})
    levels = cfg.get("levels", {})

    headlines_text = "\n".join([f"- {n['title']}" for n in news_items]) if news_items else "無最新新聞標題"

    macro_parts = []
    if macro.get("us10y"):
        macro_parts.append(f"US10Y {macro['us10y']['price']:.2f}% ({macro['us10y']['change_pct']:+.2f}%)")
    if macro.get("dxy"):
        macro_parts.append(f"DXY {macro['dxy']['price']:.2f} ({macro['dxy']['change_pct']:+.2f}%)")
    if macro.get("usdtwd"):
        macro_parts.append(f"USD/TWD {macro['usdtwd']['price']:.2f}")
    if macro.get("sox"):
        macro_parts.append(f"SOX {macro['sox']['price']:,.1f} ({macro['sox']['change_pct']:+.2f}%)")
    if macro.get("nvda"):
        macro_parts.append(f"NVDA ${macro['nvda']['price']:.2f} ({macro['nvda']['change_pct']:+.2f}%)")
    if macro.get("wdc"):
        macro_parts.append(f"WDC ${macro['wdc']['price']:.2f} ({macro['wdc']['change_pct']:+.2f}%)")
    if macro.get("avgo"):
        macro_parts.append(f"AVGO ${macro['avgo']['price']:.2f} ({macro['avgo']['change_pct']:+.2f}%)")
    macro_summary_str = "｜".join(macro_parts) if macro_parts else "宏觀與同業報價暫缺"

    if options_info:
        gex_val = options_info.get("net_gex_m")
        gex_str = f"{gex_val:+.2f}M" if gex_val is not None else "--"
        opt_summary_str = (
            f"到期 {options_info['expiration']}｜Max Pain ${options_info['max_pain']}｜"
            f"Vol P/C {options_info['vol_pcr']} / OI P/C {options_info['oi_pcr']}｜"
            f"Call OI 牆 ${options_info['call_wall']['strike']} ({options_info['call_wall']['oi']:,}) / "
            f"Put OI 牆 ${options_info['put_wall']['strike']} ({options_info['put_wall']['oi']:,})｜"
            f"ATM IV {options_info['atm_iv_pct']}%｜Net GEX {gex_str}"
        )
    else:
        opt_summary_str = "暫無最新 CBOE MU 選擇權數據"

    slip5 = tech_slip.get("slippage_5d")
    slip20 = tech_slip.get("slippage_20d")
    slip_parts = []
    if slip5:
        slip_parts.append(
            f"5日 MU {slip5['mu_ret_pct']:+.1f}% vs MUU {slip5['muu_ret_pct']:+.1f}% (耗損 {slip5['slippage_pct']:+.2f}%)"
        )
    if slip20:
        slip_parts.append(
            f"20日 MU {slip20['mu_ret_pct']:+.1f}% vs MUU {slip20['muu_ret_pct']:+.1f}% (耗損 {slip20['slippage_pct']:+.2f}%)"
        )
    slip_summary_str = "；".join(slip_parts) if slip_parts else "暫無耗損計算數據"

    tech_summary_str = (
        f"MU 收 ${mu['price']:.2f} ({mu['change_pct']:+.2f}%，高 ${mu['high']:.2f}/低 ${mu['low']:.2f})｜"
        f"5MA ${tech_slip.get('mu_ma5', '--')} / 20MA ${tech_slip.get('mu_ma20', '--')} / "
        f"200MA防守線 ${levels.get('mu_defense', '--')} / RSI14 {tech_slip.get('mu_rsi14', '--')}"
    )

    macro_prompt = f"""你是「🌐 總經與同業分析師」。請針對以下總體經濟、半導體同業與新聞標題，從資金與產業共振角度評估美光 (MU) 與川湖 (2059.TW)。
請嚴格以繁體中文純文字輸出兩行（禁止使用 **、# 或任何 Markdown 符號，不要開場白）：
分數：<整數 -5 到 +5，-5極空、0中性、+5極多，請帶正負號如 +2 或 -2>
分析：<60~80字精簡專業結論>

數據：
- MU：${mu['price']:.2f} ({mu['change_pct']:+.2f}%)｜MUU：${muu['price']:.2f} ({muu['change_pct']:+.2f}%)｜川湖 2059.TW：{tw2059['price']:.0f} ({tw2059['change_pct']:+.2f}%)
- 總經與同業：{macro_summary_str}
- 最新新聞標題：
{headlines_text}
"""

    quant_prompt = f"""你是「🧮 量化與微結構師」。請根據 MU 技術均線/動能、CBOE 選擇權微結構（Max Pain、P/C Ratio、Call/Put OI 牆、ATM IV、Net GEX）與 MUU 2X 槓桿耗損，評估短線籌碼與波動結構。
請嚴格以繁體中文純文字輸出兩行（禁止使用 **、# 或任何 Markdown 符號，不要開場白）：
分數：<整數 -5 到 +5，-5極空、0中性、+5極多，請帶正負號如 +2 或 -2>
分析：<60~80字精簡專業結論>

數據：
- 技術位階：{tech_summary_str}
- MUU 收盤：${muu['price']:.2f} ({muu['change_pct']:+.2f}%)｜槓桿耗損：{slip_summary_str}
- CBOE MU 選擇權：{opt_summary_str}
"""

    bear_prompt = f"""你是「🛡️ 空頭魔鬼代言人（強制風控反方）」。你的唯一職責是嚴格挑出下行風險、技術破位觸發點、高 IV 槓桿耗損陷阱，以及此刻「不應盲目加碼槓桿」的硬理由。
請嚴格以繁體中文純文字輸出兩行（禁止使用 **、# 或任何 Markdown 符號，不要開場白）：
分數：<整數 -5 到 +5，代表風險評分，負分越深風險越高如 -4，風險可控則近 0>
分析：<60~80字精簡犀利風控警示>

數據：
- 技術與防守線：{tech_summary_str}｜關鍵支撐1 ${levels.get('mu_support1', '--')}
- MUU：${muu['price']:.2f} ({muu['change_pct']:+.2f}%)｜槓桿耗損：{slip_summary_str}
- 總經與同業：{macro_summary_str}
- CBOE MU 選擇權：{opt_summary_str}
- 川湖 2059.TW：{tw2059['price']:.0f} ({tw2059['change_pct']:+.2f}%)
- 最新新聞標題：
{headlines_text}
"""

    specialist_specs = [
        ("macro", "🌐 總經與同業分析師", macro_prompt),
        ("quant", "🧮 量化與微結構師", quant_prompt),
        ("bear", "🛡️ 空頭魔鬼代言人", bear_prompt),
    ]

    def _run_specialist(key, role, prompt_text):
        try:
            raw = call_gemini_text(api_key, prompt_text, max_tokens=512, temperature=0.3)
            if not raw:
                return key, {"role": role, "score": 0, "analysis": "", "ok": False}
            sc, ana = _parse_agent_score_and_text(raw, default_score=0)
            return key, {"role": role, "score": sc, "analysis": ana, "ok": True}
        except Exception as e:
            print(f"[WARN] Committee specialist {key} failed: {e}")
            return key, {"role": role, "score": 0, "analysis": "", "ok": False}

    stage1 = {}
    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = {
            executor.submit(_run_specialist, key, role, ptxt): (key, role)
            for key, role, ptxt in specialist_specs
        }
        for fut, (key, role) in futures.items():
            try:
                k, res = fut.result()
                stage1[k] = res
            except Exception as e:
                print(f"[WARN] Committee future {key} exception: {e}")
                stage1[key] = {"role": role, "score": 0, "analysis": "", "ok": False}

    ok_count = sum(1 for v in stage1.values() if v.get("ok"))
    if ok_count == 0:
        print("[WARN] Stage 1 specialists all failed; falling back to single-call generate_gemini_summary.")
        fallback_text = generate_gemini_summary(mu, muu, tw2059, macro, tech_slip, options_info, news_items, cfg)
        return fallback_text, None

    # 補齊個別失敗專家的中性預設說明
    for key, role, _ in specialist_specs:
        if not stage1[key].get("analysis"):
            stage1[key]["analysis"] = f"{role}暫未取得模型回應，以盤面數據中性看待。"

    s_macro = stage1["macro"]["score"]
    s_quant = stage1["quant"]["score"]
    s_bear = stage1["bear"]["score"]
    total_score = s_macro + s_quant + s_bear
    stance = "偏多" if total_score >= 3 else ("偏空" if total_score <= -3 else "中性")
    score_header = (
        f"⚖️ 委員會多空總分：{_fmt_signed_score(total_score)}/15（{stance}）｜"
        f"總經 {_fmt_signed_score(s_macro)}・量化 {_fmt_signed_score(s_quant)}・風控 {_fmt_signed_score(s_bear)}"
    )

    cio_prompt = f"""你是「🏛️ 首席投資長 (CIO)」。你已聽取三位專職分析師的簡報，請結合投資人的真實持倉與關鍵防守價位，統整出今日最終晨間操作裁決。

【三位專職分析師報告】
- 總經與同業分析師（評分 {_fmt_signed_score(s_macro)}）：{stage1['macro']['analysis']}
- 量化與微結構師（評分 {_fmt_signed_score(s_quant)}）：{stage1['quant']['analysis']}
- 空頭魔鬼代言人（評分 {_fmt_signed_score(s_bear)}）：{stage1['bear']['analysis']}
- 委員會多空總分：{_fmt_signed_score(total_score)}/15（{stance}）

【投資人實盤部位與關鍵價位】
- MUU 總持股：{p_muu.get('total_shares', 1250):,} 股（核心 {p_muu.get('core_shares', 1100):,} 股 + 游擊 {p_muu.get('swing_shares', 150)} 股 @${p_muu.get('swing_cost', 16.42)}，實質均價 ${p_muu.get('avg_cost_usd', 34.547)}，現價 ${muu['price']:.2f}）
- 川湖 (2059.TW)：{p_tw.get('shares', 22)} 股（均價 {p_tw.get('avg_cost_twd', 10849.41):,.0f} 元，現價 {tw2059['price']:,.0f} 元）
- MU 關鍵價位：現價 ${mu['price']:.2f}｜200MA 防守線 ${levels.get('mu_defense', 715.0)}｜支撐1 ${levels.get('mu_support1', 716.38)}｜反壓區 ${levels.get('mu_res1_min', 780.0)}~${levels.get('mu_res1_max', 830.0)}｜50MA ${levels.get('mu_50ma', 983.23)}

【嚴格輸出格式要求】
1. 僅使用繁體中文純文字，絕對不可包含 **、#、項目符號或任何開場白/結語。
2. 不要重複輸出總分行（系統會自動加上），直接輸出以下 4 行編號內容（每點精簡 55~80 字）：
1. 【總經與同業】...
2. 【量化與微結構】...
3. 【空頭風控警示】...
4. 【CIO 最終操作裁決】...（務必針對 MUU {p_muu.get('total_shares', 1250):,} 股含 {p_muu.get('swing_shares', 150)} 股游擊倉 與 川湖 {p_tw.get('shares', 22)} 股給出今日具體執行、停利/減碼或觀望紀律）
"""

    cio_raw = call_gemini_text(api_key, cio_prompt, max_tokens=1536, temperature=0.3)
    cio_body = ""
    if cio_raw:
        cio_lines = []
        for ln in cio_raw.splitlines():
            s = ln.strip()
            if not s:
                continue
            if s.startswith("⚖️") or s.startswith("委員會多空總分"):
                continue
            cio_lines.append(s)
        cio_body = "\n".join(cio_lines).strip()

    if not cio_body:
        print("[WARN] Stage 2 CIO synthesis failed; falling back to single-call or rule-based committee synthesis.")
        fallback_single = generate_gemini_summary(mu, muu, tw2059, macro, tech_slip, options_info, news_items, cfg)
        if fallback_single:
            committee_data = {
                "total_score": total_score,
                "stance": stance,
                "summary_line": score_header,
                "macro": {"role": stage1["macro"]["role"], "score": s_macro, "analysis": stage1["macro"]["analysis"]},
                "quant": {"role": stage1["quant"]["role"], "score": s_quant, "analysis": stage1["quant"]["analysis"]},
                "bear": {"role": stage1["bear"]["role"], "score": s_bear, "analysis": stage1["bear"]["analysis"]},
                "cio": {"role": "🏛️ 首席投資長", "verdict": fallback_single, "fallback": True},
            }
            return fallback_single, committee_data

        tactical_fallback = build_tactical_commentary(mu, muu, cfg)
        cio_body = "\n".join([
            f"1. 【總經與同業】{stage1['macro']['analysis']}",
            f"2. 【量化與微結構】{stage1['quant']['analysis']}",
            f"3. 【空頭風控警示】{stage1['bear']['analysis']}",
            f"4. 【CIO 最終操作裁決】{tactical_fallback}",
        ])

    final_text = f"{score_header}\n{cio_body}"
    committee_data = {
        "total_score": total_score,
        "stance": stance,
        "summary_line": score_header,
        "macro": {"role": stage1["macro"]["role"], "score": s_macro, "analysis": stage1["macro"]["analysis"]},
        "quant": {"role": stage1["quant"]["role"], "score": s_quant, "analysis": stage1["quant"]["analysis"]},
        "bear": {"role": stage1["bear"]["role"], "score": s_bear, "analysis": stage1["bear"]["analysis"]},
        "cio": {"role": "🏛️ 首席投資長", "verdict": cio_body, "full_text": final_text},
    }
    print(f"[OK] 4-Agent Investment Committee completed: {score_header}")
    return final_text, committee_data


def build_tactical_commentary(mu, muu, cfg):
    defense = cfg["levels"]["mu_defense"]
    res1_min = cfg["levels"]["mu_res1_min"]
    if mu["price"] >= res1_min:
        return f"👉 MU 成功站上 ${res1_min:.0f} 反壓區！短線多頭動能轉強，游擊 {cfg['muu']['swing_shares']} 股 (@${cfg['muu']['swing_cost']}) 可於劇本 A/B 區間分批獲利收割。"
    elif mu["price"] >= defense:
        return f"👉 MU 站回 200MA 防守線 (${defense}) 之上，留意放量突破前高加速破底翻，依劇本 A ($15.50~$16.50) 準備收割 50 股。"
    else:
        return f"⚠️ MU 收盤 (${mu['price']:.2f}) 暫壓於 ${defense} 年線下方（低點 ${mu['low']:.2f}），高 IV 震盪期嚴禁無腦加碼槓桿，靜待站回 ${defense} 之上再積極操作！"


def update_frontend_files(mu, muu, tw2059, headline, news_block=None, macro=None, tech_slip=None, options_info=None, tactical_line=None, cfg=None):
    if os.path.exists(INDEX_PATH):
        with open(INDEX_PATH, "r", encoding="utf-8") as f:
            html = f.read()

        html = re.sub(r"muPrice:\s*[\d.]+", f"muPrice: {mu['price']}", html)
        html = re.sub(r"muPrevClose:\s*[\d.]+", f"muPrevClose: {mu['prev_close']}", html)
        html = re.sub(r"muLow:\s*[\d.]+", f"muLow: {mu['low']}", html)
        html = re.sub(r"muuPrice:\s*[\d.]+", f"muuPrice: {muu['price']}", html)
        html = re.sub(r"muuPrevClose:\s*[\d.]+", f"muuPrevClose: {muu['prev_close']}", html)
        html = re.sub(r"muuLow:\s*[\d.]+", f"muuLow: {muu['low']}", html)

        mu_arrow = "▲" if mu["change_pct"] >= 0 else "▼"
        muu_arrow = "▲" if muu["change_pct"] >= 0 else "▼"
        html = re.sub(r'id="mu-price">\$[\d.]+<', f'id="mu-price">${mu["price"]:.2f}<', html)
        html = re.sub(
            r'id="mu-change"[^>]*>[^<]+<',
            f'id="mu-change" class="text-xs font-bold px-1.5 py-0.5 rounded {"bg-emerald-500/20 text-emerald-400" if mu["change_pct"] >= 0 else "bg-rose-500/20 text-rose-400"}">{mu_arrow} {abs(mu["change_pct"]):.2f}%<',
            html,
        )
        html = re.sub(r'id="mu-range">[^<]+<', f'id="mu-range">低 ${mu["low"]:.2f}<', html)

        html = re.sub(r'id="muu-price">\$[\d.]+<', f'id="muu-price">${muu["price"]:.2f}<', html)
        html = re.sub(
            r'id="muu-change"[^>]*>[^<]+<',
            f'id="muu-change" class="text-xs font-bold px-1.5 py-0.5 rounded {"bg-emerald-500/20 text-emerald-400" if muu["change_pct"] >= 0 else "bg-rose-500/20 text-rose-400"}">{muu_arrow} {abs(muu["change_pct"]):.2f}%<',
            html,
        )
        html = re.sub(r'id="muu-range">[^<]+<', f'id="muu-range">低 ${muu["low"]:.2f}<', html)

        short_date = TODAY_STR[5:].replace("-", "/")
        html = re.sub(r'id="top-headline-date">[^<]+<', f'id="top-headline-date">{short_date} 最新<', html)
        if headline:
            html = re.sub(
                r'id="top-headline">\s*[\s\S]*?\s*</p>',
                f'id="top-headline">\n              {headline}\n            </p>',
                html,
            )
        if tw2059 and tw2059.get("price"):
            html = re.sub(
                r'id="tw2059-price">[^<]+<',
                f'id="tw2059-price">NT$ {int(round(tw2059["price"])):,}<',
                html,
            )
        html = re.sub(r'id="radar-current-label">[^<]+<', f'id="radar-current-label">現價 ${mu["price"]:.2f}<', html)

        if news_block:
            html = re.sub(
                r'id="gemini-insight-date">[^<]+<',
                f'id="gemini-insight-date">{TODAY_STR} 雲端結算<',
                html,
            )
            paragraphs = []
            for line in news_block.splitlines():
                line_s = line.strip()
                if line_s:
                    line_clean = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", line_s)
                    paragraphs.append(f"          <p>{line_clean}</p>")
            if paragraphs:
                inner_html = "\n".join(paragraphs)
                html = re.sub(
                    r'(<div id="gemini-insight-box"[^>]*>)[\s\S]*?(</div>)',
                    rf'\1\n{inner_html}\n        \2',
                    html,
                )

        # 同步更新 Tab 2「最新情報」卡片 1（MU / MUU 每日焦點）與卡片 2（宏觀與微結構）
        def replace_tag_inner(src, elem_id, new_inner):
            return re.sub(
                rf'(<[a-zA-Z0-9]+[^>]*id="{elem_id}"[^>]*>)[\s\S]*?(</[a-zA-Z0-9]+>)',
                lambda m: f"{m.group(1)}\n            {new_inner}\n          {m.group(2)}",
                src,
                count=1,
            )

        macro = macro or {}
        tech_slip = tech_slip or {}
        mu_ma5_s = f"${tech_slip['mu_ma5']:.2f}" if tech_slip.get("mu_ma5") else "--"
        mu_ma20_s = f"${tech_slip['mu_ma20']:.2f}" if tech_slip.get("mu_ma20") else "--"
        mu_rsi_s = f"{tech_slip['mu_rsi14']}" if tech_slip.get("mu_rsi14") is not None else "--"

        mu_card_title = f"MU 收 ${mu['price']:.2f} ({mu['change_pct']:+.2f}%)、MUU 收 ${muu['price']:.2f} ({muu['change_pct']:+.2f}%)｜{headline or '最新記憶體與 AI 焦點'}"
        insight_lines = [re.sub(r"\*\*([^*]+)\*\*", r"\1", ln.strip()) for ln in (news_block or "").splitlines() if ln.strip()]
        mu_body_extra = f" {insight_lines[1]}" if len(insight_lines) >= 2 else (f" {insight_lines[0]}" if insight_lines else "")
        mu_card_body = (
            f"美股最新收盤：MU 收 ${mu['price']:.2f} ({mu['change_pct']:+.2f}%，盤中高 ${mu['high']:.2f} / 低 ${mu['low']:.2f})、"
            f"MUU 收 ${muu['price']:.2f} ({muu['change_pct']:+.2f}%，高 ${muu['high']:.2f} / 低 ${muu['low']:.2f})。"
            f"技術面 5MA {mu_ma5_s} / 20MA {mu_ma20_s} / RSI14 {mu_rsi_s}。{mu_body_extra}"
        )
        mu_tip_text = f"💡 <strong>對 MUU 操作啟示</strong>：{tactical_line or (insight_lines[-1] if insight_lines else '嚴守劇本紀律，逢反抽分批調節游擊倉降本。')}"

        html = re.sub(r'id="news-card-mu-date">[^<]+<', f'id="news-card-mu-date">{TODAY_STR} 雲端更新<', html)
        html = replace_tag_inner(html, "news-card-mu-title", mu_card_title)
        html = replace_tag_inner(html, "news-card-mu-body", mu_card_body)
        html = replace_tag_inner(html, "news-card-mu-tip", mu_tip_text)

        us10y_s = f"{macro['us10y']['price']:.2f}% ({macro['us10y']['change_pct']:+.2f}%)" if macro.get("us10y") else "--"
        dxy_s = f"{macro['dxy']['price']:.2f}" if macro.get("dxy") else "--"
        fx_s = f"{macro['usdtwd']['price']:.2f}" if macro.get("usdtwd") else "--"
        sox_s = f"{macro['sox']['change_pct']:+.2f}%" if macro.get("sox") else "--"
        nvda_s = f"{macro['nvda']['change_pct']:+.2f}%" if macro.get("nvda") else "--"
        wdc_s = f"{macro['wdc']['change_pct']:+.2f}%" if macro.get("wdc") else "--"
        avgo_s = f"{macro['avgo']['change_pct']:+.2f}%" if macro.get("avgo") else "--"
        s20 = tech_slip.get("slippage_20d")
        slip_s = f"MUU 20日槓桿耗損 {s20['slippage_pct']:+.2f}%（MU {s20['mu_ret_pct']:+.1f}% vs MUU {s20['muu_ret_pct']:+.1f}%）" if s20 else "高波動震盪期留意槓桿耗損"
        opt_s = (
            f"CBOE MU 選擇權 ({options_info['expiration']})：Max Pain ${options_info['max_pain']:.0f}、"
            f"P/C(量/OI) {options_info['vol_pcr'] or '--'}/{options_info['oi_pcr'] or '--'}、"
            f"Call牆 ${options_info['call_wall']['strike']:.0f} / Put牆 ${options_info['put_wall']['strike']:.0f}、"
            f"IV {options_info['atm_iv_pct'] or '--'}%、Net GEX {options_info['net_gex_m']:+.1f}M。"
            if options_info
            else ""
        )
        macro_title = f"US10Y {us10y_s}｜費半 {sox_s}・NVDA {nvda_s}・WDC {wdc_s}｜{('MU Max Pain $' + str(int(options_info['max_pain']))) if options_info and options_info.get('max_pain') else '宏觀與微結構共振'}"
        macro_body = f"總經資金：US10Y {us10y_s}、DXY {dxy_s}、USD/TWD {fx_s}。同業共振：SOX {sox_s}、NVDA {nvda_s}、WDC {wdc_s}、AVGO {avgo_s}。{opt_s}{slip_s}。"
        macro_tip = f"💡 <strong>微結構風控紀律</strong>：{insight_lines[2] if len(insight_lines) >= 3 else '緊盯 US10Y 5.00% 關卡與選擇權 OI 牆變化，高 IV 震盪期嚴控槓桿倉位。'}"

        html = re.sub(r'id="news-card-macro-date">[^<]+<', f'id="news-card-macro-date">{TODAY_STR} 雲端更新<', html)
        html = replace_tag_inner(html, "news-card-macro-title", macro_title)
        html = replace_tag_inner(html, "news-card-macro-body", macro_body)
        html = replace_tag_inner(html, "news-card-macro-tip", macro_tip)

        with open(INDEX_PATH, "w", encoding="utf-8") as f:
            f.write(html)

    if os.path.exists(WIDGET_PATH):
        with open(WIDGET_PATH, "r", encoding="utf-8") as f:
            js = f.read()

        js = re.sub(
            r"MU:\s*\{[^}]+\}",
            f"MU: {{ price: {mu['price']}, prevClose: {mu['prev_close']}, changePct: {mu['change_pct']} }}",
            js,
        )
        js = re.sub(
            r"MUU:\s*\{[^}]+\}",
            f"MUU: {{ price: {muu['price']}, prevClose: {muu['prev_close']}, changePct: {muu['change_pct']} }}",
            js,
        )
        if headline:
            safe_hl = headline.replace('"', '\\"')
            js = re.sub(r'headline:\s*"[^"]*"', f'headline: "{safe_hl}"', js)
        js = re.sub(r'lastPushDate:\s*"[^"]*"', f'lastPushDate: "{TODAY_STR}"', js)

        with open(WIDGET_PATH, "w", encoding="utf-8") as f:
            f.write(js)

    dash_path = os.path.join(BASE_DIR, "dashboard.html")
    if os.path.exists(dash_path):
        with open(dash_path, "r", encoding="utf-8") as f:
            dhtml = f.read()
        dhtml = re.sub(
            r'\{\s*symbol:\s*"MU",\s*date:\s*"[^"]+",\s*price:\s*[\d.]+,\s*d1:\s*[-\d.]+',
            f'{{ symbol: "MU", date: "{TODAY_STR}", price: {mu["price"]}, d1: {mu["change_pct"]}',
            dhtml,
        )
        dhtml = re.sub(
            r'\{\s*symbol:\s*"MUU",\s*date:\s*"[^"]+",\s*price:\s*[\d.]+,\s*d1:\s*[-\d.]+',
            f'{{ symbol: "MUU", date: "{TODAY_STR}", price: {muu["price"]}, d1: {muu["change_pct"]}',
            dhtml,
        )
        if tw2059 and tw2059.get("price"):
            dhtml = re.sub(
                r'\{\s*symbol:\s*"2059\.TW",\s*date:\s*"[^"]+",\s*price:\s*[\d.]+,\s*d1:\s*[-\d.]+',
                f'{{ symbol: "2059.TW", date: "{TODAY_STR}", price: {tw2059["price"]}, d1: {tw2059["change_pct"]}',
                dhtml,
            )
        with open(dash_path, "w", encoding="utf-8") as f:
            f.write(dhtml)


def save_macro_options_json(mu, muu, tw2059, macro, tech_slip, options_info, committee=None):
    out = {
        "updated_at": NOW_TW.strftime("%Y-%m-%d %H:%M:%S+08:00"),
        "date": TODAY_STR,
        "core": {"MU": mu, "MUU": muu, "2059.TW": tw2059},
        "macro_and_peers": macro,
        "mu_tech_and_muu_slippage": tech_slip,
        "mu_options": options_info,
        "committee": committee,
    }
    with open(MACRO_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"[OK] Saved {MACRO_JSON_PATH}")


def send_line_push(message_text):
    token = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN", "").strip()
    user_id = os.environ.get("LINE_USER_ID", "").strip()
    if not token or not user_id:
        print("[WARN] LINE_CHANNEL_ACCESS_TOKEN or LINE_USER_ID not set. Skipping LINE push.")
        return False

    url = "https://api.line.me/v2/bot/message/push"
    payload = {
        "to": user_id,
        "messages": [{"type": "text", "text": message_text[:4900]}],
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json; charset=utf-8",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        res_body = resp.read().decode("utf-8")
        print(f"[OK] LINE Push succeeded: {res_body}")
        return True


def main():
    parser = argparse.ArgumentParser(description="MU / MUU 六維度雲端晨報")
    parser.add_argument("--dry-run", action="store_true", help="本機測試模式：印出報表，不改前端檔也不發 LINE")
    parser.add_argument("--save-json-only", action="store_true", help="僅寫入 daily_macro_options.json，不發 LINE 也不動執行鎖")
    args = parser.parse_args()

    event_name = os.environ.get("GITHUB_EVENT_NAME", "")
    if event_name == "schedule" and not args.dry_run and not args.save_json_only:
        now_tw = datetime.now(TW_TZ)
        if now_tw.hour < 8 or (now_tw.hour == 8 and now_tw.minute < 10):
            print("[INFO] Before 08:10 TW time; deferring to 08:00 Google Apps Script primary trigger.")
            return
        if os.path.exists(WIDGET_PATH):
            with open(WIDGET_PATH, "r", encoding="utf-8") as f:
                if f'lastPushDate: "{TODAY_STR}"' in f.read():
                    print(f"[INFO] Already executed today ({TODAY_STR}) via primary trigger. Skipping duplicate scheduled run.")
                    return
        if os.path.exists(LAST_RUN_PATH):
            try:
                with open(LAST_RUN_PATH, "r", encoding="utf-8") as f:
                    if f.read().strip() == TODAY_STR:
                        print(f"[INFO] Already executed today ({TODAY_STR}). Skipping duplicate scheduled run.")
                        return
            except Exception as e:
                print(f"[WARN] Error reading last_run_date: {e}")

    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        cfg = json.load(f)

    # 1. 核心三檔報價
    mu = fetch_quote_multi("MU", "mu.us", {"price": 705.27, "prev_close": 712.42, "high": 722.96, "low": 687.33, "change_pct": -1.00})
    muu = fetch_quote_multi("MUU", "muu.us", {"price": 13.94, "prev_close": 14.21, "high": 14.65, "low": 13.26, "change_pct": -1.90})
    tw2059 = fetch_quote_multi("2059.TW", None, {"price": 6520.0, "prev_close": 6565.0, "high": 6750.0, "low": 6210.0, "change_pct": -0.69})

    # 2. 宏觀與同業共振 + 技術指標/耗損 + MU 選擇權微結構
    macro = fetch_macro_and_peers()
    tech_slip = compute_mu_tech_and_slippage()
    options_info = fetch_mu_options_microstructure(mu["price"])

    mu_news = fetch_google_news_tw("美光 MU OR HBM 記憶體", max_items=3)
    tw_news = fetch_google_news_tw("2059 川湖", max_items=2)
    all_news = mu_news + tw_news

    top_headline = mu_news[0]["title"] if mu_news else f"MU 收 ${mu['price']:.2f} ({mu['change_pct']:+.2f}%)｜緊盯 US10Y 與 200MA 攻防"

    # 3. 部位與跨市場台幣結算
    p_muu = cfg["muu"]
    mkt_val = round(muu["price"] * p_muu["total_shares"], 2)
    unrealized_usd = round(mkt_val - p_muu["total_cost_usd"], 2)
    unrealized_pct = round((unrealized_usd / p_muu["total_cost_usd"]) * 100.0, 2)

    swing_diff_pct = round(((muu["price"] - p_muu["swing_cost"]) / p_muu["swing_cost"]) * 100.0, 2)
    swing_diff_usd = round((muu["price"] - p_muu["swing_cost"]) * p_muu["swing_shares"], 2)

    fx_rate = (macro.get("usdtwd") or {}).get("price", 32.5)
    tw_val = tw2059["price"] * cfg["tw2059"]["shares"]
    tw_cost = cfg["tw2059"]["total_cost_twd"]
    total_nav_twd = mkt_val * fx_rate + tw_val
    total_cost_twd = p_muu["total_cost_usd"] * fx_rate + tw_cost
    total_pnl_twd = total_nav_twd - total_cost_twd
    total_pnl_pct = (total_pnl_twd / total_cost_twd) * 100.0 if total_cost_twd else 0.0

    tactical_line = build_tactical_commentary(mu, muu, cfg)
    committee_text, committee_data = generate_gemini_committee_summary(
        mu, muu, tw2059, macro, tech_slip, options_info, all_news, cfg
    )

    if committee_text:
        news_block = committee_text
    elif all_news:
        news_block = "\n".join([f"{i+1}. {n['title']}" for i, n in enumerate(all_news[:4])])
    else:
        news_block = tactical_line

    # 4. 組合「宏觀與同業共振」與「衍生品微結構」區塊
    macro_parts = []
    if macro.get("us10y"):
        macro_parts.append(f"US10Y {macro['us10y']['price']:.2f}% ({macro['us10y']['change_pct']:+.1f}%)")
    if macro.get("dxy"):
        macro_parts.append(f"DXY {macro['dxy']['price']:.2f}")
    if macro.get("usdtwd"):
        macro_parts.append(f"匯率 {macro['usdtwd']['price']:.2f}")
    peer_parts = []
    if macro.get("sox"):
        peer_parts.append(f"SOX {macro['sox']['change_pct']:+.2f}%")
    if macro.get("nvda"):
        peer_parts.append(f"NVDA {macro['nvda']['change_pct']:+.2f}%")
    if macro.get("wdc"):
        peer_parts.append(f"WDC {macro['wdc']['change_pct']:+.2f}%")
    if macro.get("avgo"):
        peer_parts.append(f"AVGO {macro['avgo']['change_pct']:+.2f}%")

    macro_block = (
        f"• 總經：{'｜'.join(macro_parts) if macro_parts else '待更新'}\n"
        f"• 同業：{'｜'.join(peer_parts) if peer_parts else '待更新'}"
    )

    opt_lines = []
    if options_info:
        gex_str = f"｜GEX {options_info['net_gex_m']:+.1f}M" if options_info.get("net_gex_m") is not None else ""
        opt_lines.append(
            f"• 選擇權 ({options_info['expiration']})：Max Pain ${options_info['max_pain']:.0f}｜"
            f"P/C(量/OI) {options_info['vol_pcr'] or '--'}/{options_info['oi_pcr'] or '--'}｜IV {options_info['atm_iv_pct'] or '--'}%{gex_str}"
        )
        opt_lines.append(
            f"• OI牆：壓力 Call ${options_info['call_wall']['strike']:.0f} ({options_info['call_wall']['oi']:,})｜"
            f"支撐 Put ${options_info['put_wall']['strike']:.0f} ({options_info['put_wall']['oi']:,})"
        )
    else:
        opt_lines.append("• 選擇權：Yahoo Options 暫無最新報價")

    s5 = tech_slip.get("slippage_5d")
    s20 = tech_slip.get("slippage_20d")
    slip_parts = []
    if s5:
        slip_parts.append(f"5日 {s5['slippage_pct']:+.1f}%")
    if s20:
        slip_parts.append(f"20日 {s20['slippage_pct']:+.1f}%")
    tech_str = f"5MA ${tech_slip['mu_ma5']:.1f}" if tech_slip.get("mu_ma5") else ""
    if tech_slip.get("mu_ma20"):
        tech_str += f" / 20MA ${tech_slip['mu_ma20']:.1f}"
    if tech_slip.get("mu_rsi14"):
        tech_str += f" / RSI {tech_slip['mu_rsi14']}"
    opt_lines.append(f"• 動能與耗損：{tech_str or '--'}｜MUU耗損 {' / '.join(slip_parts) if slip_parts else '--'}")
    micro_block = "\n".join(opt_lines)

    line_msg = f"""☀️【MU / MUU 六維度雲端 AI 戰情日報】
📅 日期：{TODAY_STR}（GitHub + Gemini 自動結算）
━━━━━━━━━━━━━━
📈 核心收盤行情：
• MU ：${mu['price']:.2f} ({mu['change_pct']:+.2f}%) 高${mu['high']:.2f} / 低${mu['low']:.2f}
• MUU：${muu['price']:.2f} ({muu['change_pct']:+.2f}%) 高${muu['high']:.2f} / 低${muu['low']:.2f}
{tactical_line}

🌐 宏觀資金與同業共振：
{macro_block}

🧮 MU 選擇權微結構 & MUU 槓桿耗損：
{micro_block}

🏛️ 4-Agent 投資委員會裁決：
{news_block}

💼 雙市場持倉結算：
• MUU ({p_muu['total_shares']:,}股｜均價 ${p_muu['avg_cost_usd']:.3f})：市值 ${mkt_val:,.0f}｜損益 {unrealized_usd:+,.0f} USD ({unrealized_pct:+.2f}%)
• ⚡ 游擊 {p_muu['swing_shares']} 股 (@${p_muu['swing_cost']:.2f})：{swing_diff_usd:+.0f} USD ({swing_diff_pct:+.2f}%)
• 🏭 川湖 ({cfg['tw2059']['shares']}股｜均價 {cfg['tw2059']['avg_cost_twd']:,.0f})：收 {tw2059['price']:,.0f} ({tw2059['change_pct']:+.2f}%)
• 💰 合計總淨值 (USD/TWD {fx_rate:.2f})：NT$ {total_nav_twd:,.0f}（總損益 NT$ {total_pnl_twd:+,.0f} / {total_pnl_pct:+.2f}%）

📱 iOS 戰情室：https://hsienstyle.github.io/mu-war-room/
📊 120日儀表板：https://hsienstyle.github.io/mu-war-room/dashboard.html"""

    print("\n" + line_msg + "\n")

    if args.dry_run:
        print("[DRY-RUN] 測試完成，未寫入檔案與發送 LINE。")
        return

    save_macro_options_json(mu, muu, tw2059, macro, tech_slip, options_info, committee=committee_data)
    if args.save_json_only:
        print("[SAVE-JSON-ONLY] 已儲存 daily_macro_options.json，略過前端修改與 LINE 推播。")
        return

    update_frontend_files(
        mu, muu, tw2059, top_headline, news_block,
        macro=macro, tech_slip=tech_slip, options_info=options_info,
        tactical_line=tactical_line, cfg=cfg
    )
    send_line_push(line_msg)

    try:
        with open(LAST_RUN_PATH, "w", encoding="utf-8") as f:
            f.write(TODAY_STR)
    except Exception as e:
        print(f"[WARN] Failed to write last_run_date: {e}")


if __name__ == "__main__":
    main()
