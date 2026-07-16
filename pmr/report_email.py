"""PMR Terminal - daily HTML email brief via Gmail SMTP."""
from __future__ import annotations

import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText


def _pct(x):
    if x is None:
        return "–"
    c = "#22c55e" if x >= 0 else "#ef4444"
    return f'<span style="color:{c}">{x:+.2f}%</span>'


def build_email_html(d: dict) -> str:
    b, m, p = d["breadth"], d["movers"], d["pnl"]
    cur = "₹" if p["base_currency"] == "INR" else "$"
    top_sigs = [r for r in d["signals"] if r["signal"] in ("STRONG BUY", "STRONG SELL", "BUY", "SELL")][:8]
    row = ("<tr><td style='padding:5px 8px;border-bottom:1px solid #1f2a44'>{}</td>"
           "<td style='padding:5px 8px;border-bottom:1px solid #1f2a44;text-align:right'>{}</td></tr>")
    sig_row = ("<tr><td style='padding:5px 8px;border-bottom:1px solid #1f2a44'>{}</td>"
               "<td style='padding:5px 8px;border-bottom:1px solid #1f2a44;font-weight:700;color:{}'>{}</td>"
               "<td style='padding:5px 8px;border-bottom:1px solid #1f2a44;text-align:right'>{}%</td></tr>")

    def table(title, inner):
        return (f"<h3 style='color:#7c8db5;font-size:12px;letter-spacing:1px;margin:18px 0 6px'>{title}</h3>"
                f"<table style='width:100%;border-collapse:collapse;font-size:13px'>{inner}</table>")

    gain = "".join(row.format(r["name"], _pct(r["mtd"])) for r in m["gainers"])
    lose = "".join(row.format(r["name"], _pct(r["mtd"])) for r in m["losers"])
    sigs = "".join(sig_row.format(
        r["name"], "#22c55e" if "BUY" in r["signal"] else "#ef4444",
        r["signal"], int(r["confidence"])) for r in top_sigs)

    return f"""<html><body style="margin:0;background:#0a0e1a;padding:22px;
font-family:'Segoe UI',Arial,sans-serif;color:#d7e1f3">
<div style="max-width:620px;margin:auto">
<h1 style="font-size:22px;margin:0"><b style="color:#22d3ee">PMR</b> Terminal — Daily Brief</h1>
<p style="color:#7c8db5;font-size:12px;margin:4px 0 16px">{d['generated_at']} · 47 instruments · 10 asset classes</p>
<div style="background:#111827;border:1px solid #1f2a44;border-radius:10px;padding:14px 16px">
<b>Market tone: <span style="color:{'#22c55e' if b['tone']=='RISK-ON' else '#ef4444' if b['tone']=='RISK-OFF' else '#f59e0b'}">{b['tone']}</span></b>
&nbsp;·&nbsp; RAG: <b style="color:#ef4444">{b['red']}R</b> / <b style="color:#f59e0b">{b['amber']}A</b> / <b style="color:#22c55e">{b['green']}G</b>
&nbsp;·&nbsp; {b['pct_above_200dma']}% above 200DMA
<br><br><b>Portfolio:</b> {cur}{p['total_value']:,.0f}
&nbsp;·&nbsp; Day {_pct(p['day_pct'])} ({cur}{p['day_pnl']:,.0f})
&nbsp;·&nbsp; Total {_pct(p['total_pnl_pct'])}
</div>
{table("TOP MTD GAINERS", gain)}
{table("TOP MTD LOSERS", lose)}
{table("AI SIGNALS (conviction desk)", sigs)}
<p style="margin-top:18px"><a href="{d.get('site_url','#')}" style="color:#22d3ee">Open full PMR Terminal dashboard →</a></p>
<p style="color:#7c8db5;font-size:11px">Educational analytics, not investment advice. Data: Yahoo Finance EOD.</p>
</div></body></html>"""


def send_email(html: str, subject: str) -> bool:
    user = os.environ.get("GMAIL_USER")
    pwd = os.environ.get("GMAIL_APP_PASSWORD")
    to = os.environ.get("EMAIL_TO", user)
    if not user or not pwd:
        print("Email skipped: GMAIL_USER / GMAIL_APP_PASSWORD not set.")
        return False
    msg = MIMEMultipart("alternative")
    msg["Subject"], msg["From"], msg["To"] = subject, user, to
    msg.attach(MIMEText(html, "html"))
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
        s.login(user, pwd)
        s.sendmail(user, [to], msg.as_string())
    print(f"Email sent to {to}")
    return True
