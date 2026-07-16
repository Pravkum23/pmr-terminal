"""PMR Terminal - risk manager.

Universe-level and portfolio-level risk: VaR/CVaR, vol, max drawdown,
correlation vs NIFTY & S&P, and a vol-vs-return risk map.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def var_cvar(daily: pd.Series, level: float = 0.95) -> tuple[float, float]:
    d = daily.dropna()
    if len(d) < 30:
        return np.nan, np.nan
    var = float(np.percentile(d, (1 - level) * 100) * 100)
    cvar = float(d[d <= np.percentile(d, (1 - level) * 100)].mean() * 100)
    return var, cvar


def max_drawdown(s: pd.Series) -> float:
    roll = s.cummax()
    return float(((s / roll) - 1).min() * 100)


def risk_table(close: pd.DataFrame, rows: list[dict]) -> list[dict]:
    bench_in = close.get("^NSEI")
    bench_us = close.get("^GSPC")
    out = []
    for r in rows:
        if not r.get("ok") or r["symbol"] not in close.columns:
            continue
        s = close[r["symbol"]].dropna()
        d = s.pct_change().dropna().iloc[-252:]
        var, cvar = var_cvar(d)
        rr = {
            "symbol": r["symbol"], "name": r["name"], "asset_class": r["asset_class"],
            "vol_ann": r["vol_ann"], "var95": var, "cvar95": cvar,
            "max_dd_1y": max_drawdown(s.iloc[-252:]),
            "ret_1y": r.get("ret_1y"), "rag": r["rag"],
        }
        for label, bench in (("corr_nifty", bench_in), ("corr_spx", bench_us)):
            if bench is not None:
                bd = bench.pct_change().dropna().iloc[-252:]
                j = pd.concat([d, bd], axis=1).dropna()
                rr[label] = round(float(j.corr().iloc[0, 1]), 2) if len(j) > 60 else None
            else:
                rr[label] = None
        out.append(rr)
    return sorted(out, key=lambda x: -(x["vol_ann"] or 0))


def portfolio_risk(close: pd.DataFrame, weights: dict[str, float]) -> dict:
    syms = [s for s in weights if s in close.columns]
    if not syms:
        return {}
    w = np.array([weights[s] for s in syms])
    w = w / w.sum()
    rets = close[syms].pct_change().dropna().iloc[-252:]
    port = (rets * w).sum(axis=1)
    var, cvar = var_cvar(port)
    curve = (1 + port).cumprod()
    return {
        "vol_ann": round(float(port.std() * np.sqrt(252) * 100), 2),
        "var95_daily": round(var, 2), "cvar95_daily": round(cvar, 2),
        "max_dd_1y": round(max_drawdown(curve), 2),
        "ret_1y": round(float(curve.iloc[-1] - 1) * 100, 2),
        "sharpe": round(float(port.mean() / port.std() * np.sqrt(252)), 2)
        if port.std() > 0 else None,
    }
