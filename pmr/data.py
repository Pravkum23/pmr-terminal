"""PMR Terminal - market data layer (Yahoo Finance primary, NSE cross-check)."""
from __future__ import annotations

import time

import pandas as pd
import yaml
import yfinance as yf


def load_universe(path: str = "config/universe.yaml") -> list[dict]:
    """Flatten universe.yaml into a list of instrument dicts."""
    with open(path) as f:
        cfg = yaml.safe_load(f)
    out = []
    for cls, spec in cfg["classes"].items():
        for inst in spec["instruments"]:
            out.append({
                "symbol": inst["symbol"],
                "name": inst["name"],
                "asset_class": cls,
                "region": inst.get("region", spec.get("region", "Global")),
                "rag_green": spec["rag"]["green"],
                "rag_amber": spec["rag"]["amber"],
            })
    return out


def fetch_history(symbols: list[str], period: str = "3y",
                  retries: int = 3) -> pd.DataFrame:
    """Download daily closes for all symbols (columns = symbols)."""
    last_err = None
    for attempt in range(retries):
        try:
            raw = yf.download(symbols, period=period, interval="1d",
                              auto_adjust=True, progress=False,
                              group_by="column", threads=True)
            close = raw["Close"] if isinstance(raw.columns, pd.MultiIndex) else raw[["Close"]]
            return close.dropna(how="all").ffill()
        except Exception as e:  # noqa: BLE001
            last_err = e
            time.sleep(5 * (attempt + 1))
    raise RuntimeError(f"Yahoo download failed after {retries} tries: {last_err}")


def nse_quote(symbol_ns: str) -> dict | None:
    """Optional cross-check quote straight from nseindia.com for a .NS symbol.
    Returns None on any failure - never blocks the pipeline."""
    import requests
    sym = symbol_ns.replace(".NS", "")
    try:
        s = requests.Session()
        headers = {"User-Agent": "Mozilla/5.0", "Accept-Language": "en-US"}
        s.get("https://www.nseindia.com", headers=headers, timeout=10)
        r = s.get(f"https://www.nseindia.com/api/quote-equity?symbol={sym}",
                  headers=headers, timeout=10)
        j = r.json()["priceInfo"]
        return {"last": j["lastPrice"], "change_pct": j["pChange"]}
    except Exception:  # noqa: BLE001
        return None
