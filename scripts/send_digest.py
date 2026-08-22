#!/usr/bin/env python3
"""Send a weekly news digest email.

Configured via environment variables (see .env.example). If SMTP_HOST is
not set, runs in dry-run mode and prints the digest instead of sending it -
useful for previewing content before wiring up real credentials.

Can be triggered by cron, AWS EventBridge, or run manually.
"""
import os
import sys
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv

load_dotenv()

from backend.database import SessionLocal
from backend.digest import get_digest_articles, render_digest_html, render_digest_text


def build_message(html_body: str, text_body: str, from_email: str, to_email: str) -> MIMEMultipart:
    msg = MIMEMultipart("alternative")
    msg["Subject"] = "Your Weekly News Digest"
    msg["From"] = from_email
    msg["To"] = to_email
    msg.attach(MIMEText(text_body, "plain"))
    msg.attach(MIMEText(html_body, "html"))
    return msg


def send_email(msg: MIMEMultipart, host: str, port: int, username: str, password: str, use_tls: bool):
    with smtplib.SMTP(host, port) as server:
        if use_tls:
            server.starttls()
        if username and password:
            server.login(username, password)
        server.send_message(msg)


def main():
    smtp_host = os.getenv("SMTP_HOST", "").strip()
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_username = os.getenv("SMTP_USERNAME", "").strip()
    smtp_password = os.getenv("SMTP_PASSWORD", "").strip()
    smtp_use_tls = os.getenv("SMTP_USE_TLS", "true").lower() == "true"

    from_email = os.getenv("DIGEST_FROM_EMAIL", "").strip()
    to_email = os.getenv("DIGEST_TO_EMAIL", "").strip()
    categories_raw = os.getenv("DIGEST_CATEGORIES", "").strip()
    categories = [c.strip() for c in categories_raw.split(",") if c.strip()] or None
    per_category = int(os.getenv("DIGEST_ARTICLES_PER_CATEGORY", "5"))

    db = SessionLocal()
    try:
        grouped = get_digest_articles(db, categories=categories, per_category=per_category)
    finally:
        db.close()

    html_body = render_digest_html(grouped)
    text_body = render_digest_text(grouped)

    if not smtp_host:
        print("SMTP_HOST not configured - dry run. Digest content:\n")
        print(text_body)
        return 0

    if not from_email or not to_email:
        print("DIGEST_FROM_EMAIL and DIGEST_TO_EMAIL must be set to send email.")
        return 1

    msg = build_message(html_body, text_body, from_email, to_email)

    try:
        send_email(msg, smtp_host, smtp_port, smtp_username, smtp_password, smtp_use_tls)
        print(f"✅ Digest sent to {to_email}")
        return 0
    except Exception as e:
        print(f"❌ Failed to send digest: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
