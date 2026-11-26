#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🏭 台股 2059.TW 川湖 — 16:30 盤後籌碼全自動雲端專報腳本
功能：
1. 串接臺灣證交所 (TWSE) 官方公開 API，零外部套件依賴（純 Python 標準函式庫）：
   - 日線價量與 5MA / 20MA (STOCK_DAY + STOCK_DAY_ALL)
   - 三大法人買賣超 + 近 5 日累計與外資/投信連買連賣天數 (T86)
   - 融資融券餘額與當日增減 + 券資比 (MI_MARGN)
   - 借券賣出當日賣出 / 還券 / 餘額增減 (TWT93U)
   - 現股當沖張數與當沖成交比 (TWTB4U)
   - Google News 繁體中文最新川湖新聞
2. 呼叫 Gemini AI 生成 3 點精簡籌碼研判與持倉策略（含無 API Key 時之規則式降級）
3. 自動寫入 tw2059_chips.json、同步更新 index.html 川湖盤後籌碼卡片，並發送 LINE 籌碼專報
4. 內建休市日自動偵測與防重複推播機制（支援 --dry-run 本機乾跑測試）
"""

import argparse
import json
import os
import re
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone

TW_TZ = timezone(timedelta(hours=8))
NOW_TW = datetime.now(TW_TZ)
TODAY_STR = NOW_TW.strftime("%Y-%m-%d")

STOCK_NO = "2059"
STOCK_NAME = "川湖"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "portfolio_config.json")
INDEX_PATH = os.path.join(BASE_DIR, "index.html")
CHIPS_JSON_PATH = os.path.join(BASE_DIR, "tw2059_chips.json")
LAST_RUN_PATH = os.path.join(BASE_DIR, "last_tw2059_run_date.txt")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
    "Accept": "application/json,text/plain,*/*",
    "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8",
    "Referer": "https://www.twse.com.tw/zh/trading/historical/stock-day.html",
}

# 部分雲端環境偶爾遇 TWSE 憑證鏈異常，預設使用標準 SSL，必要時才降級
SSL_CTX = ssl.create_default_context()


def http_get_json(url, timeout=15):
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=SSL_CTX) as resp:
            return json.loads(resp.read().decode("utf-8", errors="ignore"))
    except (ssl.SSLError, urllib.error.URLError) as e:
        if isinstance(e, ssl.SSLError) or isinstance(getattr(e, "reason", None), ssl.SSLError):
            unverified = ssl._create_unverified_context()
            with urllib.request.urlopen(req, timeout=timeout, context=unverified) as resp:
                return json.loads(resp.read().decode("utf-8", errors="ignore"))
        raise


def to_num(val, default=0.0):
    if val is None:
        return default
    s = str(val).strip().replace(",", "").replace("+", "").replace("X", "").replace(" ", "")
    if not s or s in ("--", "-", "N/A", "除息", "除權"):
        return default
    try:
        return float(s)
    except ValueError:
        return default


def to_int(val, default=0):
    return int(round(to_num(val, float(default))))


def shares_to_lots(shares):
    """股數轉張數（保留整數，若為極小量保留 1 位小數以免失真）"""
    lots = shares / 1000.0
    if abs(lots) >= 10 or abs(lots) == 0:
        return int(round(lots))
    return round(lots, 1)


def fmt_lots(lots, signed=True):
    if isinstance(lots, float) and not lots.is_integer():
        return f"{lots:+,.1f}" if signed else f"{lots:,.1f}"
    n = int(round(lots))
    if signed and n == 0:
        return "0"
    return f"{n:+,d}" if signed else f"{n:,d}"


def roc_to_iso(roc_date_str):
    """將民國日期 '115/11/19' 轉為 '2026-11-19'"""
    parts = str(roc_date_str).strip().split("/")
    if len(parts) != 3:
        return str(roc_date_str)
    y = int(parts[0]) + 1911
    return f"{y:04d}-{int(parts[1]):02d}-{int(parts[2]):02d}"


def fetch_stock_day_series(stock_no, ref_dt):
    """抓取當月與上月日線資料，回傳依日期排序之日線清單"""
    months = [
        ref_dt.replace(day=1),
        (ref_dt.replace(day=1) - timedelta(days=1)).replace(day=1),
    ]
    rows_by_date = {}
    for m_dt in reversed(months):
        ymd = m_dt.strftime("%Y%m01")
        url = f"https://www.twse.com.tw/rwd/zh/afterTrading/STOCK_DAY?date={ymd}&stockNo={stock_no}&response=json"
        try:
            data = http_get_json(url, timeout=15)
            if data.get("stat") != "OK" or not data.get("data"):
                continue
            for r in data["data"]:
                # 欄位：[0]日期, [1]成交股數, [2]成交金額, [3]開盤價, [4]最高價, [5]最低價, [6]收盤價, [7]漲跌價差, [8]成交筆數
                iso = roc_to_iso(r[0])
                close = to_num(r[6])
                if close <= 0:
                    continue
                rows_by_date[iso] = {
                    "date": iso,
                    "volume_shares": to_int(r[1]),
                    "volume_lots": round(to_int(r[1]) / 1000.0, 1),
                    "turnover": to_int(r[2]),
                    "open": to_num(r[3]),
                    "high": to_num(r[4]),
                    "low": to_num(r[5]),
                    "close": close,
                    "change": to_num(r[7]),
                }
        except Exception as e:
            print(f"[WARN] STOCK_DAY failed for {ymd}: {e}")
        time.sleep(0.35)

    series = [rows_by_date[d] for d in sorted(rows_by_date.keys())]
    return series


def fetch_t86_for_date(date_str, stock_no):
    """抓取指定日期 (YYYY-MM-DD) 三大法人買賣超 (T86)"""
    ymd = date_str.replace("-", "")
    url = f"https://www.twse.com.tw/rwd/zh/fund/T86?date={ymd}&selectType=ALLBUT0999&response=json"
    data = http_get_json(url, timeout=20)
    if data.get("stat") != "OK" or not data.get("data"):
        return None

    fields = data.get("fields", [])
    rows = data.get("data", [])

    def find_idx(*keywords):
        for i, f in enumerate(fields):
            if all(k in f for k in keywords):
                return i
        return None

    idx_code = find_idx("證券代號") if find_idx("證券代號") is not None else 0
    idx_f_main = find_idx("外陸資買賣超股數")
    idx_f_dealer = find_idx("外資自營商買賣超股數")
    idx_trust = find_idx("投信買賣超股數")
    idx_dealer_total = next((i for i, f in enumerate(fields) if f.strip() == "自營商買賣超股數"), None)
    if idx_dealer_total is None:
        idx_dealer_total = next(
            (i for i, f in enumerate(fields) if "自營商買賣超股數" in f and "外資" not in f and "自行" not in f and "避險" not in f),
            None,
        )
    idx_total = find_idx("三大法人買賣超股數")

    for r in rows:
        if str(r[idx_code]).strip() == stock_no:
            foreign_shares = (to_int(r[idx_f_main]) if idx_f_main is not None else 0) + (
                to_int(r[idx_f_dealer]) if idx_f_dealer is not None else 0
            )
            trust_shares = to_int(r[idx_trust]) if idx_trust is not None else 0
            dealer_shares = to_int(r[idx_dealer_total]) if idx_dealer_total is not None else 0
            total_shares = (
                to_int(r[idx_total])
                if idx_total is not None
                else (foreign_shares + trust_shares + dealer_shares)
            )
            return {
                "date": date_str,
                "foreign_shares": foreign_shares,
                "trust_shares": trust_shares,
                "dealer_shares": dealer_shares,
                "total_shares": total_shares,
                "foreign_lots": shares_to_lots(foreign_shares),
                "trust_lots": shares_to_lots(trust_shares),
                "dealer_lots": shares_to_lots(dealer_shares),
                "total_lots": shares_to_lots(total_shares),
            }
    return None


def fetch_margin_for_date(date_str, stock_no):
    """抓取指定日期融資融券 (MI_MARGN)"""
    ymd = date_str.replace("-", "")
    url = f"https://www.twse.com.tw/rwd/zh/marginTrading/MI_MARGN?date={ymd}&selectType=ALL&response=json"
    try:
        data = http_get_json(url, timeout=20)
        if data.get("stat") == "OK":
            tables = data.get("tables") or []
            target_table = None
            for tb in tables:
                fields = tb.get("fields") or []
                if any("代號" in f for f in fields) and len(fields) >= 13:
                    target_table = tb
                    break
            if target_table:
                fields = target_table.get("fields", [])
                # 欄位標準順序（單位：張）：
                # [0]代號 [1]名稱 [2]融資買進 [3]融資賣出 [4]融資現償 [5]融資前日餘額 [6]融資今日餘額 [7]融資限額
                # [8]融券買進 [9]融券賣出 [10]融券現償 [11]融券前日餘額 [12]融券今日餘額 [13]融券限額 [14]資券互抵 [15]註記
                bal_prev_idxs = [i for i, f in enumerate(fields) if "前日餘額" in f]
                bal_curr_idxs = [i for i, f in enumerate(fields) if "今日餘額" in f]
                m_prev_i = bal_prev_idxs[0] if len(bal_prev_idxs) >= 1 else 5
                m_curr_i = bal_curr_idxs[0] if len(bal_curr_idxs) >= 1 else 6
                s_prev_i = bal_prev_idxs[1] if len(bal_prev_idxs) >= 2 else 11
                s_curr_i = bal_curr_idxs[1] if len(bal_curr_idxs) >= 2 else 12

                for r in target_table.get("data", []):
                    if str(r[0]).strip() == stock_no:
                        m_prev = to_int(r[m_prev_i])
                        m_curr = to_int(r[m_curr_i])
                        s_prev = to_int(r[s_prev_i])
                        s_curr = to_int(r[s_curr_i])
                        ratio = round((s_curr / m_curr) * 100.0, 2) if m_curr > 0 else 0.0
                        return {
                            "margin_prev": m_prev,
                            "margin_balance": m_curr,
                            "margin_change": m_curr - m_prev,
                            "short_prev": s_prev,
                            "short_balance": s_curr,
                            "short_change": s_curr - s_prev,
                            "short_margin_ratio": ratio,
                        }
    except Exception as e:
        print(f"[WARN] MI_MARGN RWD failed for {date_str}: {e}")

    # 備援：證交所 OpenAPI 最新交易日 MI_MARGN（僅在查詢最新日有效）
    try:
        rows = http_get_json("https://openapi.twse.com.tw/v1/exchangeReport/MI_MARGN", timeout=15)
        for r in rows:
            if str(r.get("股票代號", "")).strip() == stock_no:
                m_prev = to_int(r.get("融資前日餘額"))
                m_curr = to_int(r.get("融資今日餘額"))
                s_prev = to_int(r.get("融券前日餘額"))
                s_curr = to_int(r.get("融券今日餘額"))
                ratio = round((s_curr / m_curr) * 100.0, 2) if m_curr > 0 else 0.0
                return {
                    "margin_prev": m_prev,
                    "margin_balance": m_curr,
                    "margin_change": m_curr - m_prev,
                    "short_prev": s_prev,
                    "short_balance": s_curr,
                    "short_change": s_curr - s_prev,
                    "short_margin_ratio": ratio,
                }
    except Exception as e:
        print(f"[WARN] MI_MARGN OpenAPI fallback failed: {e}")

    return None


def fetch_sbl_for_date(date_str, stock_no):
    """抓取指定日期盤後借券賣出餘額 (TWT93U，單位：股 -> 轉張)"""
    ymd = date_str.replace("-", "")
    url = f"https://www.twse.com.tw/rwd/zh/marginTrading/TWT93U?date={ymd}&response=json"
    try:
        data = http_get_json(url, timeout=20)
        if data.get("stat") != "OK":
            return None
        rows = data.get("data") or []
        fields = data.get("fields") or []
        if not rows and data.get("tables"):
            tb = data["tables"][0]
            rows = tb.get("data") or []
            fields = tb.get("fields") or []

        # 標準欄位：
        # [0]代號 [1]名稱 | 融券：[2]前日餘額 [3]賣出 [4]買進 [5]現券 [6]今日餘額 [7]限額
        # 借券賣出：[8]前日餘額 [9]當日賣出 [10]當日還券 [11]當日調整 [12]當日餘額 [13]次日限額 [14]備註
        prev_idxs = [i for i, f in enumerate(fields) if "前日餘額" in f]
        sell_idxs = [i for i, f in enumerate(fields) if "當日賣出" in f or f == "賣出"]
        ret_idxs = [i for i, f in enumerate(fields) if "當日還券" in f or "還券" in f]
        curr_idxs = [i for i, f in enumerate(fields) if "當日餘額" in f or "今日餘額" in f]

        sbl_prev_i = prev_idxs[-1] if len(prev_idxs) >= 2 else 8
        sbl_sell_i = sell_idxs[-1] if sell_idxs else 9
        sbl_ret_i = ret_idxs[-1] if ret_idxs else 10
        sbl_curr_i = curr_idxs[-1] if len(curr_idxs) >= 2 else 12

        for r in rows:
            if str(r[0]).strip() == stock_no:
                prev_sh = to_int(r[sbl_prev_i])
                sell_sh = to_int(r[sbl_sell_i])
                ret_sh = to_int(r[sbl_ret_i])
                curr_sh = to_int(r[sbl_curr_i])
                return {
                    "sbl_prev_lots": shares_to_lots(prev_sh),
                    "sbl_sell_lots": shares_to_lots(sell_sh),
                    "sbl_return_lots": shares_to_lots(ret_sh),
                    "sbl_balance_lots": shares_to_lots(curr_sh),
                    "sbl_change_lots": shares_to_lots(curr_sh - prev_sh),
                }
    except Exception as e:
        print(f"[WARN] TWT93U failed for {date_str}: {e}")
    return None


def fetch_day_trade_for_date(date_str, stock_no, total_volume_shares):
    """抓取指定日期現股當沖統計 (TWTB4U)"""
    ymd = date_str.replace("-", "")
    url = f"https://www.twse.com.tw/rwd/zh/dayTrading/TWTB4U?date={ymd}&response=json"
    try:
        data = http_get_json(url, timeout=20)
        if data.get("stat") != "OK":
            return None
        tables = data.get("tables") or []
        target_rows = []
        fields = []
        for tb in tables:
            f = tb.get("fields") or []
            if any("證券代號" in col for col in f):
                fields = f
                target_rows = tb.get("data") or []
                break
        if not target_rows and data.get("data"):
            fields = data.get("fields") or []
            target_rows = data.get("data") or []

        idx_vol = next((i for i, f in enumerate(fields) if "成交股數" in f), 3)
        for r in target_rows:
            if str(r[0]).strip() == stock_no:
                dt_shares = to_int(r[idx_vol])
                ratio = round((dt_shares / total_volume_shares) * 100.0, 2) if total_volume_shares > 0 else 0.0
                return {
                    "day_trade_lots": shares_to_lots(dt_shares),
                    "day_trade_ratio": ratio,
                }
    except Exception as e:
        print(f"[WARN] TWTB4U failed for {date_str}: {e}")
    return None


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
        print(f"[WARN] Google News RSS failed: {e}")
        return []


def calc_streak(values_desc):
    """計算由最新往舊之連續買超(+)或連賣(-)天數，回傳如 ('連買', 3) 或 ('連賣', 2) 或 ('持平', 0)"""
    if not values_desc:
        return ("持平", 0)
    first = values_desc[0]
    if first == 0:
        return ("持平", 0)
    direction = 1 if first > 0 else -1
    days = 0
    for v in values_desc:
        if (direction > 0 and v > 0) or (direction < 0 and v < 0):
            days += 1
        else:
            break
    return ("連買" if direction > 0 else "連賣", days)


def build_rule_commentary(summary, cfg):
    """無 Gemini API Key 或連線失敗時的規則式籌碼研判"""
    p = summary["price"]
    t86 = summary["t86_latest"]
    margin = summary.get("margin")
    sbl = summary.get("sbl")

    f_dir, f_days = summary["streaks"]["foreign"]
    t_dir, t_days = summary["streaks"]["trust"]

    lines = []
    # 1. 法人動向
    if t86["foreign_lots"] > 0 and t86["trust_lots"] >= 0:
        lines.append(f"1. 【三大法人動向】：外資轉買/續買 {fmt_lots(t86['foreign_lots'])} 張（{f_dir} {f_days} 日）、投信 {fmt_lots(t86['trust_lots'])} 張，土洋偏多共振，籌碼結構改善。")
    elif t86["foreign_lots"] < 0 and t86["trust_lots"] > 0:
        lines.append(f"1. 【三大法人動向】：外資賣超 {fmt_lots(t86['foreign_lots'])} 張（{f_dir} {f_days} 日），但投信逆勢買超 {fmt_lots(t86['trust_lots'])} 張（{t_dir} {t_days} 日），呈現土洋對作格局。")
    else:
        lines.append(f"1. 【三大法人動向】：三大法人合計 {fmt_lots(t86['total_lots'])} 張（外資 {f_dir} {f_days} 日、近 5 日三大法人累計 {fmt_lots(summary['t86_5d']['total_lots'])} 張），持續觀察外資賣壓是否收斂。")

    # 2. 信用與借券
    m_txt = f"融資 {fmt_lots(margin['margin_change'])} 張（餘額 {margin['margin_balance']:,} 張）" if margin else "融資資料待補"
    sbl_txt = f"借券賣出餘額 {fmt_lots(sbl['sbl_change_lots'])} 張（總餘額 {fmt_lots(sbl['sbl_balance_lots'], signed=False)} 張）" if sbl else "借券資料待補"
    lines.append(f"2. 【散戶與空方籌碼】：{m_txt}；{sbl_txt}。留意借券賣出若轉為還券回補，將是千金股止跌反攻領先訊號。")

    # 3. 位階與持倉
    shares = cfg["tw2059"]["shares"]
    ma5 = p.get("ma5")
    ma5_txt = f"5MA ({ma5:,.0f} 元)" if ma5 else "短均線"
    pos_txt = "站上" if (ma5 and p["close"] >= ma5) else "仍壓於"
    lines.append(f"3. 【位階與 {shares} 股波段紀律】：收盤 {p['close']:,.0f} 元（{p['change_pct']:+.2f}%）{pos_txt} {ma5_txt}，1X 現股零波動耗損無斷頭壓力，守穩 5,900 元結構支撐續抱朝月線 ~8,000 元修復，不因短線震盪碎賣。")
    return "\n".join(lines)


def generate_gemini_chips_insight(summary, news_items, cfg):
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        return None

    p = summary["price"]
    t86 = summary["t86_latest"]
    t5 = summary["t86_5d"]
    margin = summary.get("margin") or {}
    sbl = summary.get("sbl") or {}
    dt = summary.get("day_trade") or {}
    f_dir, f_days = summary["streaks"]["foreign"]
    t_dir, t_days = summary["streaks"]["trust"]
    tw_cfg = cfg["tw2059"]

    margin_prompt = (
        f"融資增減 {fmt_lots(margin['margin_change'])} 張（餘額 {margin['margin_balance']:,} 張）、"
        f"融券增減 {fmt_lots(margin['short_change'])} 張（餘額 {margin['short_balance']:,} 張，券資比 {margin['short_margin_ratio']:.2f}%）"
        if margin
        else "證交所尚未公布（暫缺，請勿解讀為 0）"
    )
    sbl_prompt = (
        f"當日賣出 {fmt_lots(sbl['sbl_sell_lots'], signed=False)} 張、還券 {fmt_lots(sbl['sbl_return_lots'], signed=False)} 張、"
        f"餘額增減 {fmt_lots(sbl['sbl_change_lots'])} 張（總餘額 {fmt_lots(sbl['sbl_balance_lots'], signed=False)} 張）"
        if sbl
        else "證交所尚未公布（暫缺，請勿解讀為 0）"
    )
    dt_prompt = (
        f"{fmt_lots(dt['day_trade_lots'], signed=False)} 張（佔比 {dt['day_trade_ratio']:.1f}%）"
        if dt
        else "證交所尚未公布（暫缺，請勿解讀為 0）"
    )

    headlines = "\n".join([f"- {n['title']}" for n in news_items]) if news_items else "無最新新聞標題"
    prompt = f"""你是「🏛️ 單一旗艦 CIO 麾下台股 AI 伺服器與千金股籌碼專家」，專精解讀 2059 川湖（GB300 / Vera Rubin 導軌龍頭）的法人與信用籌碼。
核心操盤鐵律：
1. 川湖為 1X 現股（0% 波動率耗損、無斷頭壓力），只要日線收盤未爆量跌破 5,900 元結構硬底線，嚴禁因反彈幾%就建議碎賣核心倉（拒絕處置效應）！
2. 廢除沉沒成本帳面均價焦慮，專注於籌碼沉澱度與重返月線 (~8,000 元) 乃至萬元回本路徑。
3. 判讀自營商買賣超時，務必區分「ETF 申贖被動避險造市」與「自行買賣方向性部位」，勿將被動避險誤判為主力看空。

請根據以下 {summary['trade_date']} 最新盤後數據，用繁體中文純文字（禁止 ** 或 #）撰寫 3 點精簡直球（每點約 50~70 字）的盤後籌碼裁決（不要加開場白）：
1. 【三大法人與土洋結構】：判讀外資 ({fmt_lots(t86['foreign_lots'])} 張，{f_dir}{f_days}日)、投信 ({fmt_lots(t86['trust_lots'])} 張，{t_dir}{t_days}日)、自營商（注意避險屬性）與近 5 日累計動向。
2. 【融資券與借券空方壓力】：評估融資增減、借券賣出餘額變化與當沖比，判斷散戶籌碼安定度與外資空方回補力道（若標註尚未公布則以已公布項目為主）。
3. 【硬底線與 {tw_cfg['shares']} 股波段指令】：針對現有 {tw_cfg['shares']} 股川湖，給出唯一收盤硬底線（5,900 元）與上檔波段修復目標（~8,000 元月線），中間抱牢不動。

今日盤後數據 ({summary['trade_date']})：
- 收盤：{p['close']:,.0f} 元 ({p['change']:+,.0f} / {p['change_pct']:+.2f}%)，高 {p['high']:,.0f} / 低 {p['low']:,.0f}
- 成交量：{p['volume_lots']:,.0f} 張（較前日 {p.get('vol_change_pct', 0):+.1f}%），5MA：{p.get('ma5', 0):,.0f} 元，20MA：{p.get('ma20', 0):,.0f} 元
- 三大法人當日：外資 {fmt_lots(t86['foreign_lots'])} 張、投信 {fmt_lots(t86['trust_lots'])} 張、自營商 {fmt_lots(t86['dealer_lots'])} 張、合計 {fmt_lots(t86['total_lots'])} 張
- 近 5 日累計：外資 {fmt_lots(t5['foreign_lots'])} 張、投信 {fmt_lots(t5['trust_lots'])} 張、合計 {fmt_lots(t5['total_lots'])} 張
- 融資融券：{margin_prompt}
- 借券賣出：{sbl_prompt}
- 現股當沖：{dt_prompt}
- 川湖最新新聞：
{headlines}
"""

    models_to_try = ["gemini-3-flash-preview", "gemini-2.5-flash", "gemini-3.5-flash-lite", "gemini-2.5-flash-lite"]
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.3, "maxOutputTokens": 2048, "thinkingConfig": {"thinkingBudget": 0}},
    }
    for model_name in models_to_try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
        try:
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=25) as resp:
                res_data = json.loads(resp.read().decode("utf-8"))
            parts = res_data["candidates"][0]["content"]["parts"]
            text = "".join(p.get("text", "") for p in parts).replace("**", "").strip()
            if text:
                print(f"[OK] Gemini chips insight generated using {model_name}")
                return text
        except Exception as e:
            print(f"[WARN] {model_name} skipped/failed: {e}")
    return None


def update_chips_json(summary, insight_text):
    history = []
    if os.path.exists(CHIPS_JSON_PATH):
        try:
            with open(CHIPS_JSON_PATH, "r", encoding="utf-8") as f:
                old = json.load(f)
                history = old.get("history", [])
        except Exception:
            history = []

    record = {
        "date": summary["trade_date"],
        "close": summary["price"]["close"],
        "change_pct": summary["price"]["change_pct"],
        "volume_lots": summary["price"]["volume_lots"],
        "foreign_lots": summary["t86_latest"]["foreign_lots"],
        "trust_lots": summary["t86_latest"]["trust_lots"],
        "dealer_lots": summary["t86_latest"]["dealer_lots"],
        "inst_total_lots": summary["t86_latest"]["total_lots"],
        "margin_change": (summary.get("margin") or {}).get("margin_change"),
        "margin_balance": (summary.get("margin") or {}).get("margin_balance"),
        "short_change": (summary.get("margin") or {}).get("short_change"),
        "sbl_change_lots": (summary.get("sbl") or {}).get("sbl_change_lots"),
        "sbl_balance_lots": (summary.get("sbl") or {}).get("sbl_balance_lots"),
        "day_trade_ratio": (summary.get("day_trade") or {}).get("day_trade_ratio"),
    }

    by_date = {h["date"]: h for h in history if h.get("date")}
    by_date[record["date"]] = record
    sorted_hist = [by_date[d] for d in sorted(by_date.keys())[-30:]]

    out = {
        "updated_at": NOW_TW.strftime("%Y-%m-%d %H:%M:%S+08:00"),
        "stock_no": STOCK_NO,
        "stock_name": STOCK_NAME,
        "latest": summary,
        "insight": insight_text,
        "history": sorted_hist,
    }
    with open(CHIPS_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"[OK] Saved {CHIPS_JSON_PATH} ({len(sorted_hist)} days)")


def update_index_html_tw2059(summary, insight_text, cfg=None):
    if not os.path.exists(INDEX_PATH):
        return

    with open(INDEX_PATH, "r", encoding="utf-8") as f:
        html = f.read()

    p = summary["price"]
    t86 = summary["t86_latest"]
    margin = summary.get("margin")
    sbl = summary.get("sbl")
    dt = summary.get("day_trade")
    f_dir, f_days = summary["streaks"]["foreign"]
    t_dir, t_days = summary["streaks"]["trust"]

    html = re.sub(
        r'id="tw2059-price">[^<]+<',
        f'id="tw2059-price">NT$ {int(round(p["close"])):,}<',
        html,
    )

    def color_cls(v):
        if v is None:
            return "text-slate-300"
        return "text-emerald-400" if v > 0 else ("text-rose-400" if v < 0 else "text-slate-300")

    margin_str = (
        f'{fmt_lots(margin["margin_change"])}張 (餘{margin["margin_balance"]:,})'
        if margin
        else "待更新"
    )
    sbl_str = (
        f'{fmt_lots(sbl["sbl_change_lots"])}張 (餘{fmt_lots(sbl["sbl_balance_lots"], signed=False)})'
        if sbl
        else "待更新"
    )
    dt_str = f'{dt["day_trade_ratio"]:.1f}%' if dt else "待更新"

    first_insight = ""
    if insight_text:
        first_line = next((ln.strip() for ln in insight_text.splitlines() if ln.strip()), "")
        first_insight = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", first_line)

    chips_inner = f"""          <div class="flex items-center justify-between text-[11px]">
            <span class="font-bold text-amber-300">📊 盤後籌碼專報（{summary['trade_date']}）</span>
            <span class="text-slate-400">量 {int(round(p['volume_lots'])):,}張｜當沖 {dt_str}</span>
          </div>
          <div class="grid grid-cols-3 gap-1.5 text-center text-[11px]">
            <div class="bg-slate-950/70 rounded-lg p-1.5 border border-slate-800">
              <div class="text-slate-400 text-[10px]">外資 ({f_dir}{f_days}日)</div>
              <div class="font-mono font-bold {color_cls(t86['foreign_lots'])}">{fmt_lots(t86['foreign_lots'])}張</div>
            </div>
            <div class="bg-slate-950/70 rounded-lg p-1.5 border border-slate-800">
              <div class="text-slate-400 text-[10px]">投信 ({t_dir}{t_days}日)</div>
              <div class="font-mono font-bold {color_cls(t86['trust_lots'])}">{fmt_lots(t86['trust_lots'])}張</div>
            </div>
            <div class="bg-slate-950/70 rounded-lg p-1.5 border border-slate-800">
              <div class="text-slate-400 text-[10px]">三大合計</div>
              <div class="font-mono font-bold {color_cls(t86['total_lots'])}">{fmt_lots(t86['total_lots'])}張</div>
            </div>
          </div>
          <div class="text-[11px] text-slate-300 space-y-0.5">
            <div>• <strong>融資變動</strong>：{margin_str}｜<strong>借券餘額</strong>：{sbl_str}</div>
            {f'<div class="text-slate-400">• {first_insight}</div>' if first_insight else ''}
          </div>"""

    if 'id="tw2059-chips-box"' in html:
        html = re.sub(
            r'(<div id="tw2059-chips-box"[^>]*>)[\s\S]*?(</div>\s*<!-- /tw2059-chips-box -->)',
            rf'\1\n{chips_inner}\n        \2',
            html,
        )

    # 同步更新 Tab 2「最新情報」第 3 張卡片（2059 川湖盤後籌碼與動能）
    def replace_tag_inner(src, elem_id, new_inner):
        return re.sub(
            rf'(<[a-zA-Z0-9]+[^>]*id="{elem_id}"[^>]*>)[\s\S]*?(</[a-zA-Z0-9]+>)',
            lambda m: f"{m.group(1)}\n            {new_inner}\n          {m.group(2)}",
            src,
            count=1,
        )

    t5 = summary["t86_5d"]
    tw_title = (
        f"川湖收 {p['close']:,.0f} 元 ({p['change_pct']:+.2f}%)｜"
        f"外資 {fmt_lots(t86['foreign_lots'])} 張（{f_dir}{f_days}日）、三大法人合計 {fmt_lots(t86['total_lots'])} 張"
    )
    ma5_txt = f"{p['ma5']:,.0f}" if p.get("ma5") else "--"
    ma20_txt = f"{p['ma20']:,.0f}" if p.get("ma20") else "--"
    tw_body = (
        f"{summary['trade_date']} 盤後結算：川湖收 {p['close']:,.0f} 元 ({p['change']:+,.0f} / {p['change_pct']:+.2f}%，"
        f"高 {p['high']:,.0f} / 低 {p['low']:,.0f})，量 {int(round(p['volume_lots'])):,} 張，5MA {ma5_txt} / 20MA {ma20_txt}。"
        f"籌碼面：外資 {fmt_lots(t86['foreign_lots'])} 張（近5日 {fmt_lots(t5['foreign_lots'])}）、"
        f"投信 {fmt_lots(t86['trust_lots'])} 張、三大合計 {fmt_lots(t86['total_lots'])} 張；"
        f"融資 {margin_str}、借券 {sbl_str}、當沖 {dt_str}。"
    )
    tw_cfg = (cfg or {}).get("tw2059", {"shares": 22, "total_cost_twd": 238687, "avg_cost_twd": 10849.41})
    mkt_val = p["close"] * tw_cfg["shares"]
    insight_lines = [re.sub(r"\*\*([^*]+)\*\*", r"\1", ln.strip()) for ln in (insight_text or "").splitlines() if ln.strip()]
    tip_extra = insight_lines[-1] if insight_lines else "現股無斷頭壓力，留意 5MA 與外資連買訊號擇機做 T 降本。"
    tw_tip = (
        f"💡 <strong>持倉解析 ({tw_cfg['shares']}股 / 均價 {tw_cfg['avg_cost_twd']:,.0f} 元)</strong>："
        f"現股市值 NT$ {mkt_val:,.0f}（成本 NT$ {tw_cfg['total_cost_twd']:,.0f}）。{tip_extra}"
    )

    html = re.sub(r'id="news-card-2059-date">[^<]+<', f'id="news-card-2059-date">{summary["trade_date"]} 收盤更新<', html)
    html = replace_tag_inner(html, "news-card-2059-title", tw_title)
    html = replace_tag_inner(html, "news-card-2059-body", tw_body)
    html = replace_tag_inner(html, "news-card-2059-tip", tw_tip)

    with open(INDEX_PATH, "w", encoding="utf-8") as f:
        f.write(html)
    print("[OK] Updated tw2059-chips-box and Tab 2 news-card-2059 in index.html")


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


def build_line_message(summary, insight_text, cfg):
    p = summary["price"]
    t86 = summary["t86_latest"]
    t5 = summary["t86_5d"]
    margin = summary.get("margin")
    sbl = summary.get("sbl")
    dt = summary.get("day_trade")
    f_dir, f_days = summary["streaks"]["foreign"]
    t_dir, t_days = summary["streaks"]["trust"]

    tw_cfg = cfg["tw2059"]
    shares = tw_cfg["shares"]
    total_cost = tw_cfg["total_cost_twd"]
    avg_cost = tw_cfg["avg_cost_twd"]
    mkt_val = p["close"] * shares
    unrealized = mkt_val - total_cost
    unrealized_pct = (unrealized / total_cost) * 100.0 if total_cost else 0.0

    ma5_str = f"{p['ma5']:,.0f}" if p.get("ma5") else "--"
    ma20_str = f"{p['ma20']:,.0f}" if p.get("ma20") else "--"
    vol_chg_str = f"{p['vol_change_pct']:+.1f}%" if p.get("vol_change_pct") is not None else "--"

    margin_block = (
        f"• 融資增減：{fmt_lots(margin['margin_change'])} 張（餘額 {margin['margin_balance']:,} 張）\n"
        f"• 融券增減：{fmt_lots(margin['short_change'])} 張（餘額 {margin['short_balance']:,} 張｜券資比 {margin['short_margin_ratio']:.2f}%）"
        if margin
        else "• 融資融券：證交所尚未更新今日資料"
    )

    sbl_block = (
        f"• 借券賣出：今賣 {fmt_lots(sbl['sbl_sell_lots'], signed=False)} / 還券 {fmt_lots(sbl['sbl_return_lots'], signed=False)} 張\n"
        f"• 借券餘額：{fmt_lots(sbl['sbl_balance_lots'], signed=False)} 張（較前日 {fmt_lots(sbl['sbl_change_lots'])} 張）"
        if sbl
        else "• 借券賣出：證交所尚未更新今日資料"
    )

    dt_line = (
        f"• 現股當沖：{fmt_lots(dt['day_trade_lots'], signed=False)} 張（佔比 {dt['day_trade_ratio']:.1f}%）"
        if dt
        else "• 現股當沖：證交所尚未更新今日資料"
    )

    arrow = "🔺" if p["change"] > 0 else ("🔻" if p["change"] < 0 else "➖")
    return f"""🏭【2059 川湖 16:30 盤後籌碼專報】
📅 交易日：{summary['trade_date']}（TWSE 官方盤後結算）
━━━━━━━━━━━━━━
📈 價量與均線結構：
• 收盤：{p['close']:,.0f} 元 {arrow} {p['change']:+,.0f} ({p['change_pct']:+.2f}%)
• 區間：高 {p['high']:,.0f} / 低 {p['low']:,.0f}｜量 {int(round(p['volume_lots'])):,} 張 ({vol_chg_str})
• 均線：5MA {ma5_str} 元｜20MA {ma20_str} 元

🏛️ 三大法人買賣超（張）：
• 外資：{fmt_lots(t86['foreign_lots'])} 張（{f_dir} {f_days} 日｜近5日 {fmt_lots(t5['foreign_lots'])}）
• 投信：{fmt_lots(t86['trust_lots'])} 張（{t_dir} {t_days} 日｜近5日 {fmt_lots(t5['trust_lots'])}）
• 自營商：{fmt_lots(t86['dealer_lots'])} 張
• 三大合計：{fmt_lots(t86['total_lots'])} 張（近5日累計 {fmt_lots(t5['total_lots'])} 張）

💳 信用交易與借券空方動向：
{margin_block}
{sbl_block}
{dt_line}

🏛️ 單一旗艦 CIO 籌碼判讀與波段指令：
{insight_text}

💼 川湖持倉與攻守座標（{shares} 股｜1X 現股零耗損）：
• 最新市值：NT$ {mkt_val:,.0f}
• 唯一攻守：收盤硬底線 5,900 元｜修復目標月線 ~8,000 元 → 萬元回本（中間抱牢不碎賣）

📱 iOS 戰情室：https://hsienstyle.github.io/mu-war-room/"""


def main():
    parser = argparse.ArgumentParser(description="2059 川湖 16:30 盤後籌碼專報")
    parser.add_argument("--dry-run", action="store_true", help="測試模式：只印出報表，不發送 LINE 也不寫檔")
    parser.add_argument("--no-push", action="store_true", help="僅更新 JSON 與 index.html，不發送 LINE 也不更新防重複鎖")
    parser.add_argument("--force-latest", action="store_true", help="即使今日休市也強制回溯最近一個交易日")
    args = parser.parse_args()

    event_name = os.environ.get("GITHUB_EVENT_NAME", "")
    is_scheduled = event_name == "schedule"

    if is_scheduled and not args.dry_run:
        now_tw = datetime.now(TW_TZ)
        # 16:40 前禮讓 16:35 Google Apps Script 主觸發器
        if now_tw.hour < 16 or (now_tw.hour == 16 and now_tw.minute < 40):
            print("[INFO] Before 16:40 TW time; deferring to 16:35 GAS primary trigger.")
            return
        if os.path.exists(LAST_RUN_PATH):
            with open(LAST_RUN_PATH, "r", encoding="utf-8") as f:
                if f.read().strip() == TODAY_STR:
                    print(f"[INFO] Already sent TW2059 report today ({TODAY_STR}). Skipping.")
                    return

    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        cfg = json.load(f)

    # 1. 抓取日線序列
    series = fetch_stock_day_series(STOCK_NO, NOW_TW)
    if not series:
        raise RuntimeError("無法取得 TWSE 2059 日線資料 (STOCK_DAY)")

    latest_day = series[-1]
    latest_date = latest_day["date"]
    print(f"[OK] Latest TWSE trading day for 2059: {latest_date}, close={latest_day['close']}")

    # 自動排程若偵測到今日非交易日（台股休市）且非強制模式，直接安全跳過
    allow_fallback = args.dry_run or args.force_latest or (event_name == "workflow_dispatch")
    if latest_date != TODAY_STR and not allow_fallback:
        print(f"[INFO] Today ({TODAY_STR}) has no TWSE close yet (latest={latest_date}); likely market holiday. Skipping push.")
        return

    # 計算漲跌幅、5MA、20MA、量增減
    prev_day = series[-2] if len(series) >= 2 else None
    prev_close = prev_day["close"] if prev_day else (latest_day["close"] - latest_day["change"])
    change_val = round(latest_day["close"] - prev_close, 2)
    change_pct = round((change_val / prev_close) * 100.0, 2) if prev_close else 0.0
    closes = [d["close"] for d in series]
    ma5 = round(sum(closes[-5:]) / 5.0, 2) if len(closes) >= 5 else None
    ma20 = round(sum(closes[-20:]) / 20.0, 2) if len(closes) >= 20 else None
    vol_change_pct = (
        round(((latest_day["volume_shares"] - prev_day["volume_shares"]) / prev_day["volume_shares"]) * 100.0, 1)
        if prev_day and prev_day["volume_shares"] > 0
        else None
    )

    price_info = {
        "close": latest_day["close"],
        "prev_close": prev_close,
        "change": change_val,
        "change_pct": change_pct,
        "open": latest_day["open"],
        "high": latest_day["high"],
        "low": latest_day["low"],
        "volume_shares": latest_day["volume_shares"],
        "volume_lots": latest_day["volume_lots"],
        "vol_change_pct": vol_change_pct,
        "ma5": ma5,
        "ma20": ma20,
    }

    # 2. 抓取近 5 個交易日三大法人 (T86) 以計算連買連賣與 5 日累計
    recent_dates_desc = [d["date"] for d in reversed(series[-7:])]
    t86_history = []
    for d_str in recent_dates_desc:
        try:
            rec = fetch_t86_for_date(d_str, STOCK_NO)
            if rec:
                t86_history.append(rec)
                if len(t86_history) >= 5:
                    break
        except Exception as e:
            print(f"[WARN] T86 failed for {d_str}: {e}")
        time.sleep(0.35)

    if not t86_history:
        raise RuntimeError(f"無法取得 {latest_date} 三大法人資料 (T86)")

    trade_date = t86_history[0]["date"]
    t86_latest = t86_history[0]
    t86_5d = {
        "days": len(t86_history),
        "foreign_lots": shares_to_lots(sum(r["foreign_shares"] for r in t86_history)),
        "trust_lots": shares_to_lots(sum(r["trust_shares"] for r in t86_history)),
        "dealer_lots": shares_to_lots(sum(r["dealer_shares"] for r in t86_history)),
        "total_lots": shares_to_lots(sum(r["total_shares"] for r in t86_history)),
    }
    streaks = {
        "foreign": calc_streak([r["foreign_shares"] for r in t86_history]),
        "trust": calc_streak([r["trust_shares"] for r in t86_history]),
    }
    print(f"[OK] T86 ({trade_date}): F={t86_latest['foreign_lots']} T={t86_latest['trust_lots']} D={t86_latest['dealer_lots']}")

    # 3. 抓取融資融券、借券賣出、當沖、最新新聞
    time.sleep(0.35)
    margin_info = fetch_margin_for_date(trade_date, STOCK_NO)
    time.sleep(0.35)
    sbl_info = fetch_sbl_for_date(trade_date, STOCK_NO)
    time.sleep(0.35)
    day_trade_info = fetch_day_trade_for_date(trade_date, STOCK_NO, latest_day["volume_shares"])
    news_items = fetch_google_news_tw("2059 川湖", max_items=3)

    summary = {
        "trade_date": trade_date,
        "price": price_info,
        "t86_latest": t86_latest,
        "t86_5d": t86_5d,
        "streaks": streaks,
        "margin": margin_info,
        "sbl": sbl_info,
        "day_trade": day_trade_info,
    }

    # 4. 生成 AI 籌碼判讀
    insight = generate_gemini_chips_insight(summary, news_items, cfg)
    if not insight:
        insight = build_rule_commentary(summary, cfg)

    # 5. 組合 LINE 訊息
    line_msg = build_line_message(summary, insight, cfg)
    print("\n" + line_msg + "\n")

    if args.dry_run:
        print("[DRY-RUN] 測試模式完成，未寫入檔案與發送 LINE。")
        return

    # 6. 更新 JSON、網頁卡片與發送 LINE
    update_chips_json(summary, insight)
    update_index_html_tw2059(summary, insight, cfg)

    if args.no_push:
        print("[NO-PUSH] 已同步更新 tw2059_chips.json 與 index.html（略過 LINE 推播與執行日期鎖）。")
        return

    send_line_push(line_msg)

    with open(LAST_RUN_PATH, "w", encoding="utf-8") as f:
        f.write(TODAY_STR)


if __name__ == "__main__":
    main()
