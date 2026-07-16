"""PMR Terminal - portfolio optimizer.

Runs on the top-scored liquid instruments (or the user's portfolio symbols).
Produces three model portfolios: Max Sharpe, Min Variance, Risk Parity.
Long-only, per-asset cap to force diversification.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.optimize import minimize

CAP = 0.30  # max weight per asset


def _prep(close: pd.DataFrame, symbols: list[str]):
    syms = [s for s in symbols if s in close.columns]
    rets = close[syms].pct_change().dropna().iloc[-504:]
    syms = [s for s in syms if s in rets.columns and rets[s].std() > 0]
    rets = rets[syms]
    mu = rets.mean() * 252
    cov = rets.cov() * 252
    return syms, mu.values, cov.values


def _solve(n, objective, mu=None):
    x0 = np.ones(n) / n
    bounds = [(0.0, CAP)] * n
    cons = [{"type": "eq", "fun": lambda w: w.sum() - 1}]
    res = minimize(objective, x0, bounds=bounds, constraints=cons,
                   method="SLSQP", options={"maxiter": 500})
    return res.x if res.success else x0


def optimize(close: pd.DataFrame, symbols: list[str]) -> dict:
    syms, mu, cov = _prep(close, symbols)
    n = len(syms)
    if n < 3:
        return {}

    def neg_sharpe(w):
        r = w @ mu
        v = np.sqrt(w @ cov @ w)
        return -(r / v) if v > 0 else 0

    def variance(w):
        return w @ cov @ w

    def risk_parity(w):
        v = np.sqrt(w @ cov @ w)
        mrc = cov @ w / v
        rc = w * mrc
        return ((rc - v / n) ** 2).sum() * 1e4

    out = {}
    for name, obj in (("max_sharpe", neg_sharpe), ("min_variance", variance),
                      ("risk_parity", risk_parity)):
        w = _solve(n, obj)
        ret = float(w @ mu) * 100
        vol = float(np.sqrt(w @ cov @ w)) * 100
        out[name] = {
            "weights": {s: round(float(x), 4) for s, x in zip(syms, w) if x > 0.01},
            "exp_return": round(ret, 2), "exp_vol": round(vol, 2),
            "sharpe": round(ret / vol, 2) if vol > 0 else None,
        }
    return out
