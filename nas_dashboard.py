#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GitHub Pages 雲端版：MU / MUU 120日量化與波動率耗損儀表板產生器 (原 NAS 儀表板升級版)
自動產出 dashboard.html，供 iPhone 與電腦隨時隨地免連回家網即可瀏覽。
"""

import csv
import json
import math
import os
import urllib.request
from datetime import datetime, timedelta, timezone

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUT_HTML = os.path.join(SCRIPT_DIR, "dashboard.html")

WATCHLIST = ["MU", "MUU", "2059.TW", "NVDA", "AMD", "WDC", "SNDK"]
DECAY_WINDOWS = [5, 20, 60, 120]
CHART_DAYS = 120
TW_TZ = timezone(timedelta(hours=8))


def fetch_history(symbol: str, range_: str = "1y"):
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1d&range={range_}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        result = json.loads(resp.read().decode("utf-8"))["chart"]["result"][0]

    offset = result["meta"].get("gmtoffset", 0)
    closes = result["indicators"]["quote"][0]["close"]
    by_date = {}
    for ts, c in zip(result.get("timestamp", []), closes):
        if c is None:
            continue
        d = datetime.fromtimestamp(ts + offset, tz=timezone.utc).strftime("%Y-%m-%d")
        by_date[d] = float(c)
    return sorted(by_date.items())


def pct(a, b):
    return (a / b - 1.0) * 100.0 if b else 0.0


def rsi14(closes):
    if len(closes) < 15:
        return None
    diffs = [closes[i] - closes[i - 1] for i in range(len(closes) - 14, len(closes))]
    gains = sum(d for d in diffs if d > 0) / 14.0
    losses = sum(-d for d in diffs if d < 0) / 14.0
    return 100.0 if losses == 0 else 100.0 - 100.0 / (1.0 + gains / losses)


def summarize(symbol, hist):
    closes = [c for _, c in hist]
    last = closes[-1]
    ma50 = sum(closes[-50:]) / min(len(closes), 50)
    return {
        "symbol": symbol,
        "date": hist[-1][0],
        "price": last,
        "d1": pct(last, closes[-2]) if len(closes) > 1 else 0.0,
        "d20": pct(last, closes[-21]) if len(closes) > 20 else None,
        "ma50_gap": pct(last, ma50),
        "rsi": rsi14(closes),
    }


def ann_vol(closes):
    rets = [math.log(closes[i] / closes[i - 1]) for i in range(1, len(closes))]
    if len(rets) < 2:
        return None
    mean = sum(rets) / len(rets)
    var = sum((r - mean) ** 2 for r in rets) / (len(rets) - 1)
    return math.sqrt(var) * math.sqrt(252) * 100.0


def decay_table(mu_hist, muu_hist):
    mu_map, muu_map = dict(mu_hist), dict(muu_hist)
    dates = sorted(set(mu_map) & set(muu_map))
    mu = [mu_map[d] for d in dates]
    muu = [muu_map[d] for d in dates]

    rows = []
    for n in DECAY_WINDOWS:
        if len(dates) <= n:
            continue
        mu_r = pct(mu[-1], mu[-1 - n])
        muu_r = pct(muu[-1], muu[-1 - n])
        rows.append({
            "days": n,
            "start": dates[-1 - n],
            "mu": mu_r,
            "two_x": 2 * mu_r,
            "muu": muu_r,
            "gap": muu_r - 2 * mu_r,
            "vol": ann_vol(mu[-1 - n:]),
        })

    cd = dates[-CHART_DAYS:]
    m0, u0 = mu_map[cd[0]], muu_map[cd[0]]
    chart = {
        "dates": cd,
        "mu": [round(mu_map[d] / m0 * 100, 2) for d in cd],
        "muu": [round(muu_map[d] / u0 * 100, 2) for d in cd],
        "two_x": [round(100 + 2 * (mu_map[d] / m0 - 1) * 100, 2) for d in cd],
    }
    return rows, chart


def load_positions():
    pos = {}
    candidates = [
        os.path.join(SCRIPT_DIR, "portfolio", "trades.csv"),
        os.path.join(SCRIPT_DIR, "trades.csv"),
        os.path.join(os.path.dirname(SCRIPT_DIR), "portfolio", "trades.csv"),
    ]
    csv_path = next((p for p in candidates if os.path.exists(p)), None)
    if not csv_path:
        return pos
    with open(csv_path, "r", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            sym = (row.get("代號") or "").strip().upper()
            act = (row.get("動作(BUY/SELL)") or "").strip().upper()
            try:
                qty = float(row.get("股數") or 0)
                price = float(row.get("成交價格") or 0)
                fee = float(row.get("手續費") or 0)
            except ValueError:
                continue
            p = pos.setdefault(sym, {"shares": 0.0, "cost": 0.0, "ccy": (row.get("幣別") or "").strip()})
            if act == "BUY":
                p["shares"] += qty
                p["cost"] += qty * price + fee
            elif act == "SELL":
                p["shares"] -= qty
                p["cost"] -= qty * price - fee
    return {k: v for k, v in pos.items() if v["shares"] > 0}


HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="zh-Hant"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>MU / MUU 120日量化與耗損儀表板</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4"></script>
<style>
 body{font-family:-apple-system,BlinkMacSystemFont,"Microsoft JhengHei",sans-serif;background:#090D16;color:#e2e8f0;margin:0;padding:16px;padding-top:calc(env(safe-area-inset-top,16px) + 12px)}
 .topbar{display:flex;align-items:center;justify-content:space-between;margin-bottom:12px}
 .back-btn{display:inline-flex;align-items:center;gap:6px;background:#1e293b;color:#38bdf8;text-decoration:none;padding:8px 14px;border-radius:999px;font-size:13px;font-weight:600;border:1px solid #334155}
 h1{font-size:19px;margin:0 0 4px} h2{font-size:15px;margin:22px 0 8px;color:#38bdf8}
 .sub{color:#94a3b8;font-size:12px}
 .cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:12px}
 .card{background:#1e293b;border-radius:14px;padding:14px;border:1px solid rgba(148,163,184,0.12)}
 .card b{font-size:17px} .row{display:flex;justify-content:space-between;font-size:13px;margin-top:5px}
 .table-wrap{overflow-x:auto;border-radius:12px;border:1px solid rgba(148,163,184,0.12)}
 table{width:100%;border-collapse:collapse;background:#1e293b;font-size:13px;white-space:nowrap}
 th,td{padding:9px 10px;text-align:right;border-bottom:1px solid #334155} th:first-child,td:first-child{text-align:left}
 th{background:#0f172a;color:#94a3b8;font-weight:600}
 .up{color:#10b981} .down{color:#f43f5e}
 .box{background:#1e293b;border-radius:14px;padding:12px;border:1px solid rgba(148,163,184,0.12)}
 .note{font-size:12px;color:#94a3b8;margin-top:8px;line-height:1.6}
</style></head><body>
<div class="topbar">
 <div>
  <h1>📊 MU / MUU 120日量化與耗損儀表板</h1>
  <div class="sub">雲端更新時間：__UPDATED__（Yahoo Finance 日線自動結算）</div>
 </div>
 <a href="./index.html" class="back-btn">⬅️ 返回戰情室</a>
</div>

<h2>💼 持倉與回本漲幅試算 (自動讀取 trades.csv)</h2><div class="cards" id="pos"></div>
<h2>📈 產業鏈觀察清單 (20日報酬 / 50MA乖離 / RSI14)</h2><div class="table-wrap"><table id="watch"></table></div>
<h2>📉 MU vs MUU vs 2×MU 標準化走勢圖（近 __CHART_DAYS__ 個交易日，起點 = 100）</h2>
<div class="box"><canvas id="chart" height="130"></canvas></div>
<h2>⚖️ MUU 多週期波動率耗損追蹤 (5 / 20 / 60 / 120日)</h2><div class="table-wrap"><table id="decay"></table></div>
<div class="note">
 • 「落差」= MUU 實際報酬 − 2 × MU 報酬。負值代表每日重設、波動率耗損與內扣費用（約 1.01%/年）造成的摩擦。<br>
 • MU 年化波動率越高、走勢越反覆震盪，落差越大；單邊強趨勢時則可能因複利效應產生正落差。
</div>
<script>
const D = __DATA__;
const f = (v, d=2) => v==null ? "-" : Number(v).toLocaleString("en-US",{minimumFractionDigits:d,maximumFractionDigits:d});
const c = v => v==null ? "" : (v>=0 ? "up" : "down");
const s = v => v==null ? "-" : (v>=0?"+":"") + f(v) + "%";

document.getElementById("pos").innerHTML = D.positions.map(p => `
 <div class="card"><b>${p.symbol}</b> <span class="sub">${f(p.shares,0)} 股 · ${p.ccy}</span>
  <div class="row"><span>實質均價</span><span>${f(p.avg,3)}</span></div>
  <div class="row"><span>最新現價</span><span>${f(p.price)}</span></div>
  <div class="row"><span>目前市值</span><span>${f(p.value)}</span></div>
  <div class="row"><span>未實現損益</span><span class="${c(p.pnl)}">${f(p.pnl)}（${s(p.pnl_pct)}）</span></div>
  <div class="row"><span>回本還需漲幅</span><span style="color:#fbbf24;font-weight:bold">${p.breakeven>0 ? s(p.breakeven) : "已獲利"}</span></div>
 </div>`).join("") || '<div class="sub">無持倉資料</div>';

document.getElementById("watch").innerHTML =
 "<tr><th>代號</th><th>日期</th><th>收盤</th><th>日漲跌</th><th>20日累積</th><th>50MA 乖離</th><th>RSI14</th></tr>" +
 D.watch.map(w => `<tr><td><b>${w.symbol}</b></td><td>${w.date}</td><td>${f(w.price)}</td>
  <td class="${c(w.d1)}">${s(w.d1)}</td><td class="${c(w.d20)}">${s(w.d20)}</td>
  <td class="${c(w.ma50_gap)}">${s(w.ma50_gap)}</td><td>${f(w.rsi,1)}</td></tr>`).join("");

document.getElementById("decay").innerHTML =
 "<tr><th>區間</th><th>起始日</th><th>MU</th><th>2×MU</th><th>MUU 實際</th><th>耗損落差</th><th>MU 年化波動</th></tr>" +
 D.decay.map(r => `<tr><td><b>${r.days} 日</b></td><td>${r.start}</td>
  <td class="${c(r.mu)}">${s(r.mu)}</td><td class="${c(r.two_x)}">${s(r.two_x)}</td>
  <td class="${c(r.muu)}">${s(r.muu)}</td><td class="${c(r.gap)}"><b>${s(r.gap)}</b></td><td>${f(r.vol,1)}%</td></tr>`).join("");

if (D.chart) new Chart(document.getElementById("chart"), {
 type: "line",
 data: { labels: D.chart.dates, datasets: [
  {label:"MU 正股", data:D.chart.mu, borderColor:"#38bdf8", pointRadius:0, borderWidth:2},
  {label:"MUU (2X 實際)", data:D.chart.muu, borderColor:"#f43f5e", pointRadius:0, borderWidth:2},
  {label:"2×MU 理論倍數", data:D.chart.two_x, borderColor:"#fbbf24", borderDash:[5,4], pointRadius:0, borderWidth:1.5}
 ]},
 options: { interaction:{mode:"index",intersect:false},
  scales:{x:{ticks:{color:"#94a3b8",maxTicksLimit:7}},y:{ticks:{color:"#94a3b8"}}},
  plugins:{legend:{labels:{color:"#e2e8f0"}}} }
});
</script></body></html>
"""


def main():
    now = datetime.now(TW_TZ).strftime("%Y-%m-%d %H:%M")
    positions = load_positions()

    symbols = list(dict.fromkeys(WATCHLIST + list(positions)))
    hists = {}
    for sym in symbols:
        try:
            hists[sym] = fetch_history(sym)
        except Exception as e:
            print(f"[WARN] {sym} history fetch failed: {e}")

    watch = [summarize(s, hists[s]) for s in WATCHLIST if s in hists and len(hists[s]) > 1]

    pos_out = []
    for sym, p in positions.items():
        if sym not in hists or not hists[sym]:
            continue
        price = hists[sym][-1][1]
        avg = p["cost"] / p["shares"]
        value = p["shares"] * price
        pnl = value - p["cost"]
        pos_out.append({
            "symbol": sym, "shares": p["shares"], "ccy": p["ccy"], "avg": avg, "price": price,
            "value": value, "pnl": pnl, "pnl_pct": pnl / p["cost"] * 100 if p["cost"] else 0,
            "breakeven": pct(avg, price),
        })

    decay, chart = [], None
    if "MU" in hists and "MUU" in hists:
        decay, chart = decay_table(hists["MU"], hists["MUU"])

    data = {"positions": pos_out, "watch": watch, "decay": decay, "chart": chart}
    html = (HTML_TEMPLATE
            .replace("__UPDATED__", now)
            .replace("__CHART_DAYS__", str(CHART_DAYS))
            .replace("__DATA__", json.dumps(data, ensure_ascii=False)))

    with open(OUT_HTML, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"[{now}] OK: Dashboard generated at {OUT_HTML}")


if __name__ == "__main__":
    main()
