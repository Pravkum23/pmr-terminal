"""PMR Terminal - AI stock scanner.

Composite 0-100 score per instrument built from five factor pillars:
momentum, trend, mean-reversion (RSI), risk-adjusted return, drawdown health.
Scores are cross-sectional percentile ranks, so they answer:
"how does this instrument look vs everything else in the universe today?"
"""
from __future__ import annotations

import numpy as np
import pandas as pd

WEIGHTS = {"momentum": 0.30, "trend": 0.25, "riskadj": 0.20,
           "ddhealth": 0.15, "meanrev": 0.10}


def _pct_rank(x: pd.Series) -> pd.Series:
    return x.rank(pct=True) * 100


def scan(rows: list[dict]) -> list[dict]:
    ok = [r for r in rows if r.get("ok")]
    df = pd.DataFrame(ok)

    mom = _pct_rank(df["ret_1m"].fillna(0) * 0.5 + df["ret_3m"].fillna(0) * 0.3
                    + df["ret_6m"].fillna(0) * 0.2)
    trend = _pct_rank(
        df["above_50"].astype(float) + df["above_200"].fillna(False).astype(float)
        + df["golden_cross"].fillna(False).astype(float))
    riskadj = _pct_rank((df["ret_3m"].fillna(0)) / df["vol_ann"].clip(lower=1))
    ddhealth = _pct_rank(df["dd_52w"])  # closer to 52w high = higher
    # mean reversion sweet spot: reward RSI 40-60, penalise extremes
    meanrev = _pct_rank(-(df["rsi14"] - 50).abs())

    score = (WEIGHTS["momentum"] * mom + WEIGHTS["trend"] * trend
             + WEIGHTS["riskadj"] * riskadj + WEIGHTS["ddhealth"] * ddhealth
             + WEIGHTS["meanrev"] * meanrev)

    df["scan_score"] = score.round(1)
    df["scan_pillars"] = [
        {"momentum": round(m, 0), "trend": round(t, 0), "riskadj": round(ra, 0),
         "ddhealth": round(dh, 0), "meanrev": round(mr, 0)}
        for m, t, ra, dh, mr in zip(mom, trend, riskadj, ddhealth, meanrev)
    ]
    out = df.to_dict("records")
    # write scores back onto original rows
    by_sym = {r["symbol"]: r for r in out}
    for r in rows:
        if r["symbol"] in by_sym:
            r["scan_score"] = by_sym[r["symbol"]]["scan_score"]
            r["scan_pillars"] = by_sym[r["symbol"]]["scan_pillars"]
    return sorted(out, key=lambda r: -r["scan_score"])
