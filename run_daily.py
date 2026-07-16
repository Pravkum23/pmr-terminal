"""PMR Terminal - daily orchestrator. (v1.1)

Fetch -> metrics/RAG -> scanner -> signals -> fundamentals -> risk ->
optimizer -> backtest -> P&L -> docs/data.js -> PPT deck -> HTML email.
Run: python run_daily.py [--no-email]
"""
from __future__ import annotations

import json
import math
import os
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

from pmr.data import fetch_history, load_universe
from pmr.signals import (attach_relative_strength, instrument_metrics,
                         market_breadth, movers_mtd)
from pmr.scanner import scan
from pmr.engine import generate_signals
from pmr.risk import risk_table
from pmr.optimizer import optimize
from pmr.backtest import backtest_trend
from pmr.pnl import compute_pnl, load_portfolio
from pmr.report_email import build_email_html, send_email
from pmr.report_pptx import build_deck
from pmr.fundamentals import attach_summaries, fetch_fundamentals
from pmr.extended import build_extended
from pmr.ai_analyst import write_brief

SITE_URL = os.environ.get("SITE_URL", "")


def _json_default(o):
    import numpy as np
    if isinstance(o, np.integer):
        return int(o)
    if isinstance(o, np.floating):
        f = float(o)
        return None if (math.isnan(f) or math.isinf(f)) else f
    if isinstance(o, np.bool_):
        return bool(o)
    raise TypeError(f"Not JSON serializable: {type(o)}")


def _clean(o):
    import numpy as np
    if isinstance(o, dict):
        return {k: _clean(v) for k, v in o.items()}
    if isinstance(o, list):
        return [_clean(v) for v in o]
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        o = float(o)
    if isinstance(o, (np.bool_,)):
        return bool(o)
    if isinstance(o, float) and (math.isnan(o) or math.isinf(o)):
        return None
    return o


def main():
    now = datetime.now(ZoneInfo("Asia/Singapore"))
    print(f"PMR Terminal run @ {now:%a %d %b %Y %H:%M} SGT")

    universe = load_universe()
    port_cfg = load_portfolio()
    port_syms = [h["symbol"] for h in port_cfg["holdings"]]
    all_syms = sorted({i["symbol"] for i in universe} | set(port_syms))

    print(f"Fetching {len(all_syms)} symbols from Yahoo Finance...")
    close = fetch_history(all_syms)
    print(f"Got {close.shape[0]} rows x {close.shape[1]} symbols")

    rows = [instrument_metrics(i, close[i["symbol"]])
            if i["symbol"] in close.columns else {**i, "ok": False}
            for i in universe]
    n_ok = sum(r.get("ok", False) for r in rows)
    print(f"Metrics OK for {n_ok}/{len(rows)} instruments")
    if n_ok < len(rows) * 0.7:
        sys.exit("Too many instruments failed - aborting to avoid publishing bad data.")

    # relative strength benchmarks: NIFTY for India, S&P for US, SPX for global
    def _b3m(sym):
        if sym in close.columns:
            s = close[sym].dropna()
            if len(s) > 63:
                return float((s.iloc[-1] / s.iloc[-64] - 1) * 100)
        return 0.0
    bench_3m = {"India": _b3m("^NSEI"), "US": _b3m("^GSPC"),
                "Global": _b3m("^GSPC"), "Singapore": _b3m("^STI"),
                "Asia-Pacific": _b3m("^N225"), "Europe": _b3m("^FTSE")}
    attach_relative_strength(rows, bench_3m)

    scanner_rows = scan(rows)
    signal_rows = generate_signals(rows)
    print("Fetching fundamentals for equities...")
    fundamentals = fetch_fundamentals(rows)
    print(f"Fundamentals for {len(fundamentals)} stocks")
    attach_summaries(rows, fundamentals)
    breadth = market_breadth(rows)
    movers = movers_mtd(rows)
    risk_rows = risk_table(close, rows)
    pnl = compute_pnl(close, port_cfg)

    extended = []
    if os.environ.get("PMR_EXTENDED", "1") == "1":
        try:
            extended = build_extended({i["symbol"] for i in universe}, bench_3m)
        except Exception as e:  # noqa: BLE001
            print(f"Extended tier failed, continuing without it: {e}")

    top15 = [r["symbol"] for r in scanner_rows[:15]]
    opt = optimize(close, sorted(set(top15 + port_syms)))
    bt = backtest_trend(close, sorted(set(top15 + port_syms)))

    slim = lambda r: {k: v for k, v in r.items()
                      if k not in ("spark", "summary", "fundamentals")}
    data = _clean({
        "generated_at": f"{now:%A, %d %b %Y %H:%M} SGT",
        "site_url": SITE_URL,
        "breadth": breadth,
        "movers": movers,
        "instruments": rows,
        "scanner": [slim(r) for r in scanner_rows],
        "signals": [slim(r) for r in signal_rows],
        "risk": risk_rows,
        "optimizer": opt,
        "pnl": pnl,
        "backtest": bt,
        "extended": extended,
    })

    data["ai_brief"] = write_brief(data)

    os.makedirs("docs", exist_ok=True)
    with open("docs/data.js", "w", encoding="utf-8") as f:
        f.write("window.PMR = " + json.dumps(data, default=_json_default) + ";")
    print("Wrote docs/data.js")

    build_deck(data, "docs/pmr_daily.pptx")

    html = build_email_html(data)
    with open("docs/email_preview.html", "w", encoding="utf-8") as f:
        f.write(html)
    if "--no-email" not in sys.argv:
        send_email(html, f"PMR Terminal Daily Brief - {now:%d %b %Y} | "
                         f"{breadth['tone']} | RAG {breadth['red']}R/{breadth['amber']}A/{breadth['green']}G")

    print("Done.")


if __name__ == "__main__":
    main()
