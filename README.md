# PMR Terminal

**P**raveen · **M**oulya · **R**isha — a daily market intelligence terminal.

47 instruments · 10 asset classes · auto-runs every weekday at **07:00 SGT / 04:30 IST** (before Indian and Asian markets open), publishes a **live public webpage**, sends an **HTML email brief**, and builds a **PowerPoint deck** — all free, no server.

## What's inside

| Module | File | What it does |
|---|---|---|
| Market data | `pmr/data.py` | Yahoo Finance history for all 47 symbols (+ optional NSE cross-check) |
| RAG signals | `pmr/signals.py` | RED / AMBER / GREEN from 52-week-high drawdown, thresholds per asset class |
| AI stock scanner | `pmr/scanner.py` | 0–100 composite score: momentum, trend, risk-adjusted return, drawdown health, mean-reversion |
| AI buy/sell engine | `pmr/engine.py` | STRONG BUY → STRONG SELL with confidence % and plain-English reasons |
| Portfolio optimizer | `pmr/optimizer.py` | Max Sharpe / Min Variance / Risk Parity model portfolios |
| Risk manager | `pmr/risk.py` | VaR, CVaR, vol, max drawdown, correlations vs NIFTY & S&P |
| Backtesting engine | `pmr/backtest.py` | 200DMA trend rule vs buy & hold — CAGR, Sharpe, MaxDD, win rate |
| Live P&L | `pmr/pnl.py` | Your real holdings from `config/portfolio.yaml`, INR/USD converted |
| Web dashboard | `docs/index.html` | 7-tab dark terminal (the live site) |
| Email brief | `pmr/report_email.py` | Daily HTML brief via Gmail |
| PPT deck | `pmr/report_pptx.py` | 5 slides: summary, MTD movers with sparklines, risk scatter, signals, P&L |

## Setup (one time, ~10 minutes)

### 1. Push to GitHub
```bash
cd pmr-terminal
git init && git add -A && git commit -m "PMR Terminal v1"
# create an empty repo named pmr-terminal on github.com, then:
git remote add origin https://github.com/YOUR_USERNAME/pmr-terminal.git
git branch -M main && git push -u origin main
```

### 2. Enable the website
GitHub repo → **Settings → Pages** → Source: *Deploy from a branch* → Branch: `main`, folder: `/docs` → Save.
Your live site: `https://YOUR_USERNAME.github.io/pmr-terminal/` — shareable with anyone.

### 3. Enable the email
1. Google Account → Security → 2-Step Verification (must be on) → **App passwords** → create one for "Mail".
2. GitHub repo → **Settings → Secrets and variables → Actions** → add three secrets:
   - `GMAIL_USER` = your Gmail address
   - `GMAIL_APP_PASSWORD` = the 16-character app password
   - `EMAIL_TO` = kumprav001@gmail.com (or any recipient)

### 4. Test it
Repo → **Actions** → *PMR Terminal Daily* → **Run workflow**. In ~3 minutes the site, deck and email update with live market data. After that it runs itself every weekday at 07:00 SGT.

## Daily use

- **Website**: bookmark your Pages URL — Market Overview, AI Scanner, AI Signals, Portfolio P&L, Optimizer, Risk Monitor, Backtest tabs.
- **Portfolio**: edit `config/portfolio.yaml` with your real holdings, commit, done. P&L, allocation, risk and optimizer all follow it.
- **Universe**: edit `config/universe.yaml` to swap instruments or tune RAG thresholds.
- **Deck**: download `pmr_daily.pptx` from the site folder (regenerated daily).

## Run locally
```bash
pip install -r requirements.txt
python run_daily.py --no-email
# open docs/index.html in a browser
```
`python test_pipeline.py` runs the full pipeline on synthetic data (no internet needed).

## Data notes
- Yahoo Finance provides end-of-day data (final) and ~15-min delayed intraday — ideal for a pre-open daily snapshot. True real-time tick data requires a paid feed.
- `pmr/data.py:nse_quote()` can cross-check Indian symbols directly against nseindia.com.

---
*Educational analytics — not investment advice. Built with Claude.*
