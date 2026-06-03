# core/email_client.py
#
# Sends Gmail HTML digest of confirmed business openings.
# Graceful — skips silently if Gmail not configured.

import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv

load_dotenv()

GMAIL_ADDRESS      = os.environ.get("GMAIL_ADDRESS", "")
GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD", "")


def send_digest(to_email: str, results: list, raw_query: str) -> bool:
    """Send HTML digest. Returns True if sent, False if skipped or failed."""
    if not to_email or not results:
        return False
    if not GMAIL_ADDRESS or not GMAIL_APP_PASSWORD:
        print("Email skipped — GMAIL_ADDRESS or GMAIL_APP_PASSWORD not set.")
        return False

    rows = "".join([
        f"""<tr>
          <td style="padding:10px;border-bottom:1px solid #f0f0f0;font-weight:600">{r.get('business_name') or '—'}</td>
          <td style="padding:10px;border-bottom:1px solid #f0f0f0;color:#666">{r.get('business_type') or '—'}</td>
          <td style="padding:10px;border-bottom:1px solid #f0f0f0;color:#666">{r.get('location_details') or '—'}</td>
          <td style="padding:10px;border-bottom:1px solid #f0f0f0">
            <span style="background:{'#DAFBE1' if r.get('opening_qualifier')=='now_open' else '#FFF8C5'};
                         color:{'#1A7F37' if r.get('opening_qualifier')=='now_open' else '#9A6700'};
                         padding:2px 8px;border-radius:20px;font-size:12px;font-weight:600">
              {(r.get('opening_qualifier') or '').replace('_',' ')}
            </span>
          </td>
          <td style="padding:10px;border-bottom:1px solid #f0f0f0;color:#666">{r.get('opening_date') or '—'}</td>
          <td style="padding:10px;border-bottom:1px solid #f0f0f0">
            {'<a href="' + r["source_url"] + '" style="color:#0969DA">↗ source</a>' if r.get("source_url") else '—'}
          </td>
        </tr>"""
        for r in results
    ])

    html = f"""
    <html><body style="font-family:Inter,sans-serif;color:#1F2328;max-width:800px;margin:0 auto;padding:24px">
      <h2 style="margin-bottom:4px;font-size:18px">New business openings</h2>
      <p style="color:#8B949E;margin:0 0 24px;font-size:13px">{raw_query} — {len(results)} result(s)</p>
      <table style="width:100%;border-collapse:collapse;font-size:13px">
        <thead>
          <tr style="background:#F6F8FA;text-align:left">
            <th style="padding:10px;font-weight:600;color:#57606A">Business</th>
            <th style="padding:10px;font-weight:600;color:#57606A">Type</th>
            <th style="padding:10px;font-weight:600;color:#57606A">Location</th>
            <th style="padding:10px;font-weight:600;color:#57606A">Status</th>
            <th style="padding:10px;font-weight:600;color:#57606A">Date</th>
            <th style="padding:10px;font-weight:600;color:#57606A">Source</th>
          </tr>
        </thead>
        <tbody>{rows}</tbody>
      </table>
      <p style="color:#8B949E;font-size:11px;margin-top:32px">
        Powered by CatchAll Web Search API — platform.newscatcherapi.com
      </p>
    </body></html>
    """

    msg = MIMEMultipart()
    msg["Subject"] = f"New openings: {raw_query} ({len(results)} results)"
    msg["From"]    = GMAIL_ADDRESS
    msg["To"]      = to_email
    msg.attach(MIMEText(html, "html"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
            smtp.send_message(msg)
        print(f"Email sent to {to_email} — {len(results)} results.")
        return True
    except smtplib.SMTPAuthenticationError:
        print("Gmail auth failed — check GMAIL_APP_PASSWORD in .env")
        return False
    except smtplib.SMTPException as e:
        print(f"Email failed: {e}")
        return False
