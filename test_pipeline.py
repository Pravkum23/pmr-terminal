"""End-to-end test with synthetic data (Yahoo blocked in sandbox)."""
import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np, pandas as pd, sys, types
import pmr.data as data

def fake_fetch(symbols, period="3y", retries=3):
    rng = np.random.default_rng(42)
    idx = pd.bdate_range(end="2026-07-15", periods=756)
    cols = {}
    for i, s in enumerate(symbols):
        drift = rng.normal(0.0004, 0.0004)
        vol = rng.uniform(0.008, 0.03)
        r = rng.normal(drift, vol, len(idx))
        cols[s] = 100 * np.exp(np.cumsum(r))
    df = pd.DataFrame(cols, index=idx)
    return df

data.fetch_history = fake_fetch
sys.modules["pmr.data"].fetch_history = fake_fetch
# patch the already-imported reference in run_daily

import pmr.extended as ext
def fake_lists(exclude):
    caps = ["Large Cap","Mid Cap","Small Cap","Micro Cap"]
    return [{"symbol": f"FAKE{i}.NS" if i%2 else f"FAKE{i}", "name": f"Fake Co {i}",
             "asset_class": "India "+caps[i%4] if i%2 else "S&P 500",
             "region": "India" if i%2 else "US", "cap": caps[i%4] if i%2 else "Large Cap",
             "sector": "Testing", "rag_green": 8, "rag_amber": 18} for i in range(120)]
ext.load_extended_lists = fake_lists
ext.fetch_history_chunked = lambda syms, period="2y", chunk=200: fake_fetch(syms)

import run_daily
run_daily.fetch_history = fake_fetch
sys.argv = ["run_daily.py", "--no-email"]
run_daily.main()
