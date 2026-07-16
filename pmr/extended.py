"""PMR Terminal - extended universe tier, segmented by market cap.

India (NSE official index lists): Large = NIFTY 100, Mid = Midcap 150,
Small = Smallcap 250, Micro = Microcap 250. US: S&P 500 (all Large Cap).
Scanner scores are percentiles WITHIN each (market, cap) peer group.
Lists fetched at runtime, cached in docs/lists/ (committed daily).
Entirely failure-tolerant.
"""
from __future__ import annotations

import io
import os

import pandas as pd
import requests
import yfinance as yf

from .signals import instrument_metrics
from .scanner import scan
from .engine import generate_signals

SP500_URL = "https://raw.githubusercontent.com/datasets/s-and-p-500-companies/main/data/constituents.csv"
NSE_BASE = "https://archives.nseindia.com/content/indices/"
INDIA_LISTS = [
    ("Large Cap", ["ind_nifty100list.csv"]),
    ("Mid Cap",   ["ind_niftymidcap150list.csv"]),
    ("Small Cap", ["ind_niftysmallcap250list.csv"]),
    ("Micro Cap", ["ind_niftymicrocap250_list.csv", "ind_niftymicrocap250list.csv"]),
]
CACHE_DIR = "docs/lists"

KEEP = ["symbol", "name", "asset_class", "region", "cap", "sector", "price",
        "ret_1d", "ret_1w", "ret_1m", "ret_3m", "mtd", "ytd", "ret_1y",
        "dd_52w", "rag", "rsi14", "vol_ann", "above_200", "golden_cross",
        "scan_score", "scan_pillars", "signal", "confidence", "ok"]


def _get_csv(urls, cache_name):
    cache = os.path.join(CACHE_DIR, cache_name)
    for url in urls:
        try:
            r = requests.get(url, timeout=30,
                             headers={"User-Agent": "Mozilla/5.0"})
            r.raise_for_status()
            df = pd.read_csv(io.StringIO(r.text))
            os.makedirs(CACHE_DIR, exist_ok=True)
            df.to_csv(cache, index=False)
            return df
        except Exception as e:  # noqa: BLE001
            print(f"List fetch failed ({url}): {e}")
    if os.path.exists(cache):
        print(f"Using cached {cache_name}")
        return pd.read_csv(cache)
    return None


def load_extended_lists(exclude):
    insts, seen = [], set(exclude)
    sp = _get_csv([SP500_URL], "sp500.csv")
    if sp is not None:
        for _, row in sp.iterrows():
            sym = str(row["Symbol"]).replace(".", "-")
            if sym in seen:
                continue
            seen.add(sym)
            insts.append({"symbol": sym, "name": str(row["Security"]),
                          "asset_class": "S&P 500", "region": "US",
                          "cap": "Large Cap",
                          "sector": str(row.get("GICS Sector", "")),
                          "rag_green": 8, "rag_amber": 18})
    for cap, files in INDIA_LISTS:
        df = _get_csv([NSE_BASE + f for f in files], files[0])
        if df is None:
            continue
        g, a = {"Large Cap": (8, 18), "Mid Cap": (10, 22),
                "Small Cap": (12, 28), "Micro Cap": (15, 35)}[cap]
        for _, row in df.iterrows():
            base = str(row["Symbol"]).strip()
            if base.upper().startswith("DUMMY"):
                continue
            sym = f"{base}.NS"
            if sym in seen:
                continue
            seen.add(sym)
            insts.append({"symbol": sym, "name": str(row["Company Name"]),
                          "asset_class": f"India {cap}", "region": "India",
                          "cap": cap, "sector": str(row.get("Industry", "")),
                          "rag_green": g, "rag_amber": a})
    return insts


def fetch_history_chunked(symbols, period="2y", chunk=200):
    frames = []
    for i in range(0, len(symbols), chunk):
        batch = symbols[i:i + chunk]
        try:
            raw = yf.download(batch, period=period, interval="1d",
                              auto_adjust=True, progress=False,
                              group_by="column", threads=True)
            close = raw["Close"] if isinstance(raw.columns, pd.MultiIndex) else raw[["Close"]]
            frames.append(close)
        except Exception as e:  # noqa: BLE001
            print(f"Chunk {i} failed: {e}")
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, axis=1).dropna(how="all").ffill()


def _slim(r):
    out = {}
    for k in KEEP:
        v = r.get(k)
        if isinstance(v, float):
            v = round(v, 3)
        out[k] = v
    return out


def build_extended(core_symbols):
    """Full extended-tier pipeline. Returns slim rows (may be empty)."""
    insts = load_extended_lists(exclude=core_symbols)
    if not insts:
        print("Extended tier: no lists available, skipping")
        return []
    print(f"Extended tier: {len(insts)} constituents, fetching history...")
    close = fetch_history_chunked([i["symbol"] for i in insts])
    if close.empty:
        print("Extended tier: no price data, skipping")
        return []
    rows = [instrument_metrics(i, close[i["symbol"]])
            if i["symbol"] in close.columns else {**i, "ok": False}
            for i in insts]
    ok = [r for r in rows if r.get("ok")]
    print(f"Extended tier: metrics OK for {len(ok)}/{len(rows)}")
    if len(ok) < 50:
        return []
    groups = {}
    for r in ok:
        groups.setdefault((r["region"], r["cap"]), []).append(r)
    for key, grp in groups.items():
        if len(grp) >= 5:
            scan(grp)
        print(f"  scored {key[0]} {key[1]}: {len(grp)} names")
    generate_signals(ok)
    for r in ok:
        r.pop("spark", None)
        r.pop("signal_reasons", None)
    return [_slim(r) for r in ok]
