"""PMR Terminal - live portfolio P&L from config/portfolio.yaml."""
from __future__ import annotations

import numpy as np
import pandas as pd
import yaml

from .risk import portfolio_risk


def load_portfolio(path: str = "config/portfolio.yaml") -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


def compute_pnl(close: pd.DataFrame, cfg: dict) -> dict:
    base = cfg.get("base_currency", "INR")
    usdinr = float(close["INR=X"].dropna().iloc[-1]) if "INR=X" in close.columns else 83.0

    def to_base(v: float, ccy: str) -> float:
        if base == "INR" and ccy == "USD":
            return v * usdinr
        if base == "USD" and ccy == "INR":
            return v / usdinr
        return v

    positions, total_cost, total_val, total_day = [], 0.0, 0.0, 0.0
    for h in cfg["holdings"]:
        sym = h["symbol"]
        if sym not in close.columns:
            continue
        s = close[sym].dropna()
        px, prev = float(s.iloc[-1]), float(s.iloc[-2]) if len(s) > 1 else float(s.iloc[-1])
        cost = to_base(h["qty"] * h["avg_price"], h["currency"])
        val = to_base(h["qty"] * px, h["currency"])
        day = to_base(h["qty"] * (px - prev), h["currency"])
        positions.append({
            "symbol": sym, "qty": h["qty"], "avg_price": h["avg_price"],
            "price": round(px, 2), "currency": h["currency"],
            "value": round(val, 0), "cost": round(cost, 0),
            "pnl": round(val - cost, 0),
            "pnl_pct": round((val / cost - 1) * 100, 2) if cost else 0,
            "day_pnl": round(day, 0),
            "day_pct": round((px / prev - 1) * 100, 2) if prev else 0,
        })
        total_cost += cost; total_val += val; total_day += day

    weights = {p["symbol"]: p["value"] / total_val for p in positions} if total_val else {}
    return {
        "base_currency": base, "usdinr": round(usdinr, 2),
        "positions": sorted(positions, key=lambda p: -p["value"]),
        "total_value": round(total_val, 0), "total_cost": round(total_cost, 0),
        "total_pnl": round(total_val - total_cost, 0),
        "total_pnl_pct": round((total_val / total_cost - 1) * 100, 2) if total_cost else 0,
        "day_pnl": round(total_day, 0),
        "day_pct": round(total_day / (total_val - total_day) * 100, 2)
        if total_val - total_day else 0,
        "risk": portfolio_risk(close, weights),
        "weights": {k: round(v, 4) for k, v in weights.items()},
    }
