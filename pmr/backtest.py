"""PMR Terminal - backtesting engine.

Vectorized backtest of the engine's core trend rule (long when price > 200DMA,
flat otherwise) per instrument over the full history window, vs buy & hold.
This validates the buy/sell engine's foundation with real numbers daily.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def _stats(curve: pd.Series, daily: pd.Series) -> dict:
    yrs = len(curve) / 252
    cagr = (float(curve.iloc[-1]) ** (1 / yrs) - 1) * 100 if yrs > 0 else np.nan
    vol = float(daily.std() * np.sqrt(252) * 100)
    sharpe = float(daily.mean() / daily.std() * np.sqrt(252)) if daily.std() > 0 else 0
    mdd = float(((curve / curve.cummax()) - 1).min() * 100)
    return {"cagr": round(cagr, 2), "vol": round(vol, 2),
            "sharpe": round(sharpe, 2), "max_dd": round(mdd, 2)}


def backtest_trend(close: pd.DataFrame, symbols: list[str]) -> list[dict]:
    out = []
    for sym in symbols:
        if sym not in close.columns:
            continue
        s = close[sym].dropna()
        if len(s) < 300:
            continue
        sma200 = s.rolling(200).mean()
        pos = (s > sma200).astype(float).shift(1).fillna(0)  # trade next day
        ret = s.pct_change().fillna(0)
        strat = ret * pos
        bh_curve = (1 + ret).cumprod()
        st_curve = (1 + strat).cumprod()
        trades = int(pos.diff().abs().sum() / 2)
        in_market = strat[pos == 1]
        win = float((in_market > 0).mean() * 100) if len(in_market) else 0
        out.append({
            "symbol": sym,
            "strategy": _stats(st_curve, strat),
            "buyhold": _stats(bh_curve, ret),
            "trades": trades, "win_rate": round(win, 1),
            "edge_cagr": round(_stats(st_curve, strat)["cagr"]
                               - _stats(bh_curve, ret)["cagr"], 2),
        })
    return sorted(out, key=lambda r: -r["edge_cagr"])
