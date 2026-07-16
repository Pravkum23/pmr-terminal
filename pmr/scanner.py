"""PMR Terminal - AI stock scanner (v2).

Six factor pillars, cross-sectional percentile ranks within the pool given:
  momentum 25  - 1M/3M/6M blended returns
  trend    20  - price vs 50/200DMA, golden cross, MACD
  relstr   20  - 3M return vs market benchmark (NIFTY for India, SPX for US)
  riskadj  15  - 3M return per unit of volatility
  ddhealth 10  - proximity to 52-week high
  breakout 10  - proximity to 3-month high (fresh highs = strength)
"""
from __future__ import annotations

import numpy as np
import pandas as pd

WEIGHTS = {"momentum": 0.25, "trend": 0.20, "relstr": 0.20,
           "riskadj": 0.15, "ddhealth": 0.10, "breakout": 0.10}


def _pct_rank(x):
    return x.rank(pct=True) * 100


def scan(rows):
    ok = [r for r in rows if r.get("ok")]
    if len(ok) < 3:
        return ok
    df = pd.DataFrame(ok)

    mom = _pct_rank(df["ret_1m"].fillna(0) * 0.5 + df["ret_3m"].fillna(0) * 0.3
                    + df["ret_6m"].fillna(0) * 0.2)
    trend = _pct_rank(
        df["above_50"].astype(float)
        + df["above_200"].fillna(False).astype(float)
        + df["golden_cross"].fillna(False).astype(float)
        + df.get("macd_bull", pd.Series(False, index=df.index)).fillna(False).astype(float))
    if "rs_3m" in df.columns:
        relstr = _pct_rank(df["rs_3m"].fillna(0))
    else:
        relstr = pd.Series(50.0, index=df.index)
    riskadj = _pct_rank((df["ret_3m"].fillna(0)) / df["vol_ann"].clip(lower=1))
    ddhealth = _pct_rank(df["dd_52w"])
    brk = _pct_rank(df.get("breakout", pd.Series(0, index=df.index)).fillna(-99))

    score = (WEIGHTS["momentum"] * mom + WEIGHTS["trend"] * trend
             + WEIGHTS["relstr"] * relstr + WEIGHTS["riskadj"] * riskadj
             + WEIGHTS["ddhealth"] * ddhealth + WEIGHTS["breakout"] * brk)

    df["scan_score"] = score.round(1)
    df["scan_pillars"] = [
        {"momentum": round(m, 0), "trend": round(t, 0), "relstr": round(rs, 0),
         "riskadj": round(ra, 0), "ddhealth": round(dh, 0), "breakout": round(bk, 0)}
        for m, t, rs, ra, dh, bk in zip(mom, trend, relstr, riskadj, ddhealth, brk)
    ]
    out = df.to_dict("records")
    by_sym = {r["symbol"]: r for r in out}
    for r in rows:
        if r["symbol"] in by_sym:
            r["scan_score"] = by_sym[r["symbol"]]["scan_score"]
            r["scan_pillars"] = by_sym[r["symbol"]]["scan_pillars"]
    return sorted(out, key=lambda r: -r["scan_score"])
