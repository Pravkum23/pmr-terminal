"""PMR Terminal - per-instrument metrics + RAG signal system.

RAG = drawdown from 52-week high, thresholds per asset class/cap.
Also computes MACD state and 3-month breakout proximity for the scanner.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

TRADING_DAYS = {"1d": 1, "1w": 5, "1m": 21, "3m": 63, "6m": 126, "1y": 252}


def _ret(s, days):
    if len(s) <= days:
        return np.nan
    return (s.iloc[-1] / s.iloc[-1 - days] - 1) * 100


def _mtd(s):
    last = s.index[-1]
    prev_month_end = s.loc[:last.replace(day=1) - pd.Timedelta(days=1)]
    if prev_month_end.empty:
        return np.nan
    return (s.iloc[-1] / prev_month_end.iloc[-1] - 1) * 100


def _ytd(s):
    last = s.index[-1]
    prev_year = s.loc[:pd.Timestamp(year=last.year - 1, month=12, day=31)]
    if prev_year.empty:
        return np.nan
    return (s.iloc[-1] / prev_year.iloc[-1] - 1) * 100


def rsi(s, n=14):
    d = s.diff()
    gain = d.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    loss = (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    rs = gain / loss.replace(0, np.nan)
    return float((100 - 100 / (1 + rs)).iloc[-1])


def instrument_metrics(inst, s):
    """All per-instrument stats used across dashboard/scanner/engine."""
    s = s.dropna()
    if len(s) < 60:
        return {**inst, "ok": False}
    px = float(s.iloc[-1])
    yr = s.iloc[-min(len(s), 252):]
    hi52 = float(yr.max())
    dd52 = (px / hi52 - 1) * 100
    g, a = inst["rag_green"], inst["rag_amber"]
    rag = "GREEN" if -dd52 < g else ("AMBER" if -dd52 < a else "RED")
    sma50 = float(s.rolling(50).mean().iloc[-1])
    sma200 = float(s.rolling(200).mean().iloc[-1]) if len(s) >= 200 else np.nan
    daily = s.pct_change().dropna()
    vol_ann = float(daily.iloc[-63:].std() * np.sqrt(252) * 100)
    # MACD (12/26/9)
    ema12 = s.ewm(span=12, adjust=False).mean()
    ema26 = s.ewm(span=26, adjust=False).mean()
    macd = ema12 - ema26
    macd_sig = macd.ewm(span=9, adjust=False).mean()
    macd_bull = bool(macd.iloc[-1] > macd_sig.iloc[-1])
    # 3-month breakout proximity: 0 = at 63-day high
    hi63 = float(s.iloc[-63:].max())
    breakout = (px / hi63 - 1) * 100
    return {
        **inst, "ok": True,
        "price": px,
        "ret_1d": _ret(s, 1), "ret_1w": _ret(s, 5), "ret_1m": _ret(s, 21),
        "ret_3m": _ret(s, 63), "ret_6m": _ret(s, 126), "ret_1y": _ret(s, 252),
        "mtd": _mtd(s), "ytd": _ytd(s),
        "high_52w": hi52, "dd_52w": dd52, "rag": rag,
        "sma50": sma50, "sma200": sma200,
        "above_50": px > sma50,
        "above_200": bool(px > sma200) if not np.isnan(sma200) else None,
        "golden_cross": bool(sma50 > sma200) if not np.isnan(sma200) else None,
        "macd_bull": macd_bull,
        "breakout": breakout,
        "rsi14": rsi(s),
        "vol_ann": vol_ann,
        "spark": [round(float(x), 4) for x in s.iloc[-63:].tolist()],
    }


def attach_relative_strength(rows, bench_3m: dict):
    """rs_3m = instrument 3M return minus its market benchmark's 3M return."""
    for r in rows:
        if not r.get("ok"):
            continue
        b = bench_3m.get(r.get("region", "Global"), bench_3m.get("Global", 0.0))
        r3 = r.get("ret_3m")
        r["rs_3m"] = round(r3 - b, 2) if r3 is not None and not np.isnan(r3) else None


def market_breadth(rows):
    ok = [r for r in rows if r.get("ok")]
    n = len(ok)
    green = sum(r["rag"] == "GREEN" for r in ok)
    amber = sum(r["rag"] == "AMBER" for r in ok)
    red = sum(r["rag"] == "RED" for r in ok)
    up = sum((r.get("ret_1d") or 0) > 0 for r in ok)
    above200 = sum(bool(r.get("above_200")) for r in ok)
    tone = "RISK-ON" if green / max(n, 1) > 0.6 else (
        "RISK-OFF" if red / max(n, 1) > 0.35 else "MIXED")
    return {"n": n, "green": green, "amber": amber, "red": red,
            "advancers": up, "decliners": n - up,
            "pct_above_200dma": round(above200 / max(n, 1) * 100, 1),
            "tone": tone}


def movers_mtd(rows, k=5):
    ok = sorted([r for r in rows if r.get("ok") and not np.isnan(r["mtd"])],
                key=lambda r: r["mtd"])
    return {"losers": ok[:k], "gainers": ok[::-1][:k]}
