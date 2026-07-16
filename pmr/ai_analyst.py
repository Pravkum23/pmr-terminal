"""PMR Terminal - AI analyst brief via GitHub Models (free in Actions).

After the quant pipeline computes everything, an LLM reads the day's numbers
and writes a morning analyst brief: market read, why the top names scored,
sector/rotation observations, and what to watch. Runs on the free GitHub
Models API using the workflow's own GITHUB_TOKEN (permissions: models: read).
Failure-tolerant: any error returns "" and the terminal publishes without it.
"""
from __future__ import annotations

import json
import os

import requests

ENDPOINT = "https://models.github.ai/inference/chat/completions"
MODEL = os.environ.get("PMR_AI_MODEL", "openai/gpt-4o-mini")

SYSTEM = """You are the in-house market analyst for PMR Terminal, a daily
India-first market intelligence product. You are given today's computed data:
market breadth, RAG regime counts, top movers, top-scored stocks from a
quantitative scanner (with factor pillars), buy/sell engine signals, and risk
readings. Write a crisp morning brief for an Indian retail investor:

1. MARKET READ (2-3 sentences): overall tone, what breadth and RAG counts say.
2. WHAT STANDS OUT (3-5 bullets): the most interesting scanner names and WHY
   their factors line up (momentum + relative strength + breakout etc.),
   any sector patterns you can see, notable divergences.
3. WATCH TODAY (2-3 bullets): risks, extremes (overbought/oversold), levels.

Rules: plain language, no jargon without a gloss, cite actual numbers from the
data, never invent facts not in the data, max 350 words. End with exactly:
\"Educational analysis, not investment advice.\""""


def _compact(data: dict) -> dict:
    """Small, token-efficient view of the day's data for the model."""
    top = [r for r in data.get("extended", []) if r.get("region") == "India"]
    top = sorted(top, key=lambda r: -(r.get("scan_score") or 0))[:15]
    pick = lambda r, ks: {k: r.get(k) for k in ks}
    return {
        "date": data["generated_at"],
        "breadth": data["breadth"],
        "gainers_mtd": [pick(r, ["name", "mtd", "rag"]) for r in data["movers"]["gainers"]],
        "losers_mtd": [pick(r, ["name", "mtd", "rag"]) for r in data["movers"]["losers"]],
        "top_india_scanner": [pick(r, ["name", "cap", "sector", "scan_score",
                                       "scan_pillars", "signal", "rs_3m",
                                       "ret_3m", "rsi14", "dd_52w"]) for r in top],
        "core_signals": [pick(r, ["name", "signal", "confidence"])
                         for r in data["signals"] if r["signal"] != "HOLD"][:10],
        "riskiest": [pick(r, ["name", "vol_ann", "max_dd_1y", "rag"])
                     for r in data["risk"][:8]],
    }


def write_brief(data: dict) -> str:
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        print("AI brief skipped: no GITHUB_TOKEN")
        return ""
    try:
        r = requests.post(
            ENDPOINT,
            headers={"Authorization": f"Bearer {token}",
                     "Content-Type": "application/json"},
            json={"model": MODEL,
                  "messages": [
                      {"role": "system", "content": SYSTEM},
                      {"role": "user", "content": json.dumps(_compact(data))}],
                  "temperature": 0.4, "max_tokens": 700},
            timeout=90)
        r.raise_for_status()
        brief = r.json()["choices"][0]["message"]["content"].strip()
        print(f"AI brief generated ({len(brief)} chars)")
        return brief
    except Exception as e:  # noqa: BLE001
        print(f"AI brief failed (continuing without): {e}")
        return ""
