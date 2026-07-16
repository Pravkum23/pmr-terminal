"""PMR Terminal - AI buy/sell signal engine (v2).

Rules-based ensemble: seven checks vote; net vote + scanner score decide
signal and confidence. Educational signals, not investment advice.
"""
from __future__ import annotations


def _votes(r):
    v, why = 0, []
    if r.get("above_200"):
        v += 1; why.append("above 200DMA")
    elif r.get("above_200") is False:
        v -= 1; why.append("below 200DMA")
    if r.get("golden_cross"):
        v += 1; why.append("golden cross (50>200)")
    elif r.get("golden_cross") is False:
        v -= 1; why.append("death cross (50<200)")
    if r.get("macd_bull"):
        v += 1; why.append("MACD bullish")
    elif r.get("macd_bull") is False:
        v -= 1; why.append("MACD bearish")
    rs = r.get("rs_3m")
    if rs is not None:
        if rs > 0:
            v += 1; why.append(f"outperforming market by {rs:.1f}% (3M)")
        else:
            v -= 1; why.append(f"lagging market by {abs(rs):.1f}% (3M)")
    if (r.get("ret_3m") or 0) > 0:
        v += 1; why.append(f"3M momentum +{r['ret_3m']:.1f}%")
    else:
        v -= 1; why.append(f"3M momentum {r['ret_3m']:.1f}%")
    rsi = r.get("rsi14") or 50
    if rsi >= 70:
        v -= 1; why.append(f"overbought RSI {rsi:.0f}")
    elif rsi <= 30:
        v += 1; why.append(f"oversold RSI {rsi:.0f}")
    if r["rag"] == "GREEN":
        v += 1; why.append("GREEN regime")
    elif r["rag"] == "RED":
        v -= 1; why.append("RED regime (deep drawdown)")
    return v, why


def generate_signals(rows):
    out = []
    for r in rows:
        if not r.get("ok"):
            continue
        v, why = _votes(r)
        score = r.get("scan_score", 50)
        rsi = r.get("rsi14") or 50
        if v >= 4 and score >= 70 and rsi < 70:
            sig = "STRONG BUY"
        elif v >= 2 and score >= 55:
            sig = "BUY"
        elif v <= -4 and r["rag"] == "RED":
            sig = "STRONG SELL"
        elif v <= -2:
            sig = "SELL"
        else:
            sig = "HOLD"
        conf = min(95, 50 + abs(v) * 6 + (score - 50) * 0.3 * (1 if v >= 0 else -1))
        r["signal"] = sig
        r["confidence"] = round(max(30, conf), 0)
        r["signal_reasons"] = why
        out.append(r)
    order = {"STRONG BUY": 0, "BUY": 1, "HOLD": 2, "SELL": 3, "STRONG SELL": 4}
    return sorted(out, key=lambda r: (order[r["signal"]], -r.get("scan_score", 0)))
