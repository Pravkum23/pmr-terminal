"""PMR Terminal - fundamentals + plain-English performance summaries.

For real equities (India Stocks / US Stocks) we pull public fundamentals from
Yahoo Finance: valuation ratios, margins, and the last reported quarterly
results with year-over-year comparison. Every instrument (equity or not) also
gets a written technical summary. All failure-tolerant: a ticker that errors
simply has no fundamentals that day.
"""
from __future__ import annotations

import yfinance as yf

EQUITY_CLASSES = {"India Stocks", "US Stocks"}


def _safe(d: dict, key, scale=1.0, nd=2):
    v = d.get(key)
    try:
        return round(float(v) * scale, nd) if v is not None else None
    except (TypeError, ValueError):
        return None


def fetch_fundamentals(rows: list[dict]) -> dict[str, dict]:
    """Return {symbol: fundamentals dict} for equity instruments."""
    out = {}
    for r in rows:
        if r.get("asset_class") not in EQUITY_CLASSES:
            continue
        sym = r["symbol"]
        try:
            t = yf.Ticker(sym)
            info = t.info or {}
            f = {
                "sector": info.get("sector"),
                "market_cap": info.get("marketCap"),
                "currency": info.get("currency"),
                "pe_trailing": _safe(info, "trailingPE"),
                "pe_forward": _safe(info, "forwardPE"),
                "pb": _safe(info, "priceToBook"),
                "dividend_yield_pct": _safe(info, "dividendYield", 1, 2),
                "roe_pct": _safe(info, "returnOnEquity", 100, 1),
                "profit_margin_pct": _safe(info, "profitMargins", 100, 1),
                "revenue_growth_pct": _safe(info, "revenueGrowth", 100, 1),
                "earnings_growth_pct": _safe(info, "earningsGrowth", 100, 1),
                "debt_to_equity": _safe(info, "debtToEquity", 0.01, 2),
                "target_mean": _safe(info, "targetMeanPrice"),
                "recommendation": info.get("recommendationKey"),
            }
            # last reported quarter vs same quarter a year ago
            try:
                q = t.quarterly_income_stmt
                if q is not None and not q.empty:
                    cols = list(q.columns)
                    rev = q.loc["Total Revenue"] if "Total Revenue" in q.index else None
                    ni = q.loc["Net Income"] if "Net Income" in q.index else None
                    if rev is not None and len(cols) >= 1:
                        f["q_date"] = str(cols[0].date())
                        f["q_revenue"] = float(rev.iloc[0])
                        f["q_net_income"] = float(ni.iloc[0]) if ni is not None else None
                        if len(cols) >= 5:  # year-ago quarter
                            ra, na = float(rev.iloc[4]), (float(ni.iloc[4]) if ni is not None else None)
                            if ra:
                                f["q_revenue_yoy_pct"] = round((f["q_revenue"] / ra - 1) * 100, 1)
                            if na and f.get("q_net_income") is not None:
                                f["q_net_income_yoy_pct"] = round((f["q_net_income"] / na - 1) * 100, 1)
            except Exception:  # noqa: BLE001
                pass
            out[sym] = {k: v for k, v in f.items() if v is not None}
        except Exception:  # noqa: BLE001
            continue
    return out


def _fmt_big(x, ccy=""):
    if x is None:
        return "n/a"
    for div, suf in ((1e12, "T"), (1e9, "B"), (1e7, "Cr") if ccy == "INR" else (1e9, "B"), (1e6, "M")):
        if abs(x) >= div:
            return f"{x / div:,.1f}{suf}"
    return f"{x:,.0f}"


def write_summary(r: dict, fund: dict | None) -> str:
    """Deterministic plain-English summary from the day's numbers."""
    if not r.get("ok"):
        return "No data available for this instrument today."
    p = []
    mtd = r.get("mtd"); y1 = r.get("ret_1y"); dd = r.get("dd_52w")
    direction = "up" if (r.get("ret_1m") or 0) >= 0 else "down"
    p.append(f"{r['name']} is trading at {r['price']:,.2f}, {direction} "
             f"{abs(r.get('ret_1m') or 0):.1f}% over the past month"
             + (f" and {'up' if mtd >= 0 else 'down'} {abs(mtd):.1f}% month-to-date." if mtd is not None else "."))
    if dd is not None:
        if -dd < 3:
            p.append(f"It sits within {abs(dd):.1f}% of its 52-week high — {r['rag']} signal.")
        else:
            p.append(f"It is {abs(dd):.1f}% below its 52-week high, putting it in {r['rag']} territory.")
    trend_bits = []
    if r.get("above_200") is True:
        trend_bits.append("above its 200-day average (long-term uptrend intact)")
    elif r.get("above_200") is False:
        trend_bits.append("below its 200-day average (long-term trend weak)")
    if r.get("golden_cross") is True:
        trend_bits.append("with the 50-day above the 200-day")
    if trend_bits:
        p.append("The price is " + " ".join(trend_bits) + ".")
    rsi = r.get("rsi14")
    if rsi is not None:
        state = "overbought" if rsi >= 70 else ("oversold" if rsi <= 30 else "neutral")
        p.append(f"RSI is {rsi:.0f} ({state}), and 1-year return stands at "
                 f"{'+' if (y1 or 0) >= 0 else ''}{(y1 or 0):.1f}%.")
    if fund:
        ccy = fund.get("currency", "")
        bits = []
        if fund.get("pe_trailing"):
            bits.append(f"P/E {fund['pe_trailing']}")
        if fund.get("roe_pct") is not None:
            bits.append(f"ROE {fund['roe_pct']}%")
        if fund.get("profit_margin_pct") is not None:
            bits.append(f"net margin {fund['profit_margin_pct']}%")
        if fund.get("market_cap"):
            bits.append(f"market cap {ccy} {_fmt_big(fund['market_cap'], ccy)}")
        if bits:
            p.append("Fundamentals: " + ", ".join(bits) + ".")
        if fund.get("q_revenue"):
            s = (f"In its last reported quarter ({fund.get('q_date', 'latest')}), revenue was "
                 f"{ccy} {_fmt_big(fund['q_revenue'], ccy)}")
            if fund.get("q_revenue_yoy_pct") is not None:
                s += f" ({fund['q_revenue_yoy_pct']:+.1f}% vs the same quarter last year)"
            if fund.get("q_net_income") is not None:
                s += f", with net profit of {ccy} {_fmt_big(fund['q_net_income'], ccy)}"
                if fund.get("q_net_income_yoy_pct") is not None:
                    s += f" ({fund['q_net_income_yoy_pct']:+.1f}% YoY)"
            p.append(s + ".")
        if fund.get("q_revenue_yoy_pct") is not None and fund.get("q_net_income_yoy_pct") is not None:
            rg, ng = fund["q_revenue_yoy_pct"], fund["q_net_income_yoy_pct"]
            if rg > 0 and ng > 0:
                verdict = "a solid quarter — both revenue and profit grew year-over-year"
            elif rg > 0:
                verdict = "a mixed quarter — revenue grew but profit fell year-over-year"
            elif ng > 0:
                verdict = "a mixed quarter — profit grew despite lower revenue"
            else:
                verdict = "a weak quarter — both revenue and profit declined year-over-year"
            p.append(f"Overall, {verdict}.")
    return " ".join(p)


def attach_summaries(rows: list[dict], fundamentals: dict[str, dict]) -> None:
    for r in rows:
        f = fundamentals.get(r["symbol"])
        r["summary"] = write_summary(r, f)
        if f:
            r["fundamentals"] = f
