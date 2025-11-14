#!/usr/bin/env python3
import os
import logging
import smtplib
import sqlite3
from datetime import datetime, UTC
from email.mime.text import MIMEText
from pathlib import Path
from typing import List, Dict
from urllib.parse import urlencode, urljoin
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

# --------------------------------------------------------------------
# Config
# --------------------------------------------------------------------
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=LOG_LEVEL,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

load_dotenv()  # lets you run locally with a .env file as well

BASE_URL = os.environ["BASE_URL"]
BROWSE_PATH = "/Browse"
param_string = urlencode({"ViewStyle": "list", "StatusFilter": "active_only", "SortFilterOptions": "1"}, doseq=True)
base = urljoin(BASE_URL, BROWSE_PATH)
BROWSE_URL = base + "?" + param_string

# Where the SQLite DB lives (mount /data as a volume in Docker)
DB_PATH = Path("/data/seen_items.db")

# SMTP / email config - set via environment variables
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.environ["SMTP_USER"]  # required
SMTP_PASS = os.environ["SMTP_PASS"]  # required
EMAIL_FROM = os.getenv("EMAIL_FROM", SMTP_USER)
EMAIL_TO = os.getenv("EMAIL_TO", SMTP_USER)

# How many pages of /Browse to scan each run
MAX_PAGES = int(os.getenv("MAX_PAGES", "20"))

# HTTP config
USER_AGENT = os.getenv(
    "USER_AGENT",
    "swap-watcher/1.0 (+personal script; contact owner of this account)",
)
REQUEST_TIMEOUT = 20


# --------------------------------------------------------------------
# SQLite helpers
# --------------------------------------------------------------------


def get_connection() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    # a little more robust for concurrent-ish access
    conn.execute("PRAGMA journal_mode=WAL;")
    return conn


def init_db() -> None:
    conn = get_connection()
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS seen_items (
                id TEXT PRIMARY KEY,
                first_seen_at TEXT NOT NULL
            )
            """
        )
        conn.commit()
    finally:
        conn.close()


def get_seen_ids() -> set:
    conn = get_connection()
    try:
        cur = conn.execute("SELECT id FROM seen_items")
        return {row[0] for row in cur.fetchall()}
    finally:
        conn.close()


def add_seen_ids(ids) -> None:
    ids = list(ids)
    if not ids:
        return

    now = datetime.now(UTC).isoformat()
    conn = get_connection()
    try:
        tx = conn
        cur = tx.cursor()
        cur.executemany(
            "INSERT OR IGNORE INTO seen_items (id, first_seen_at) VALUES (?, ?)",
            [(i, now) for i in ids],
        )
        tx.commit()
    finally:
        conn.close()


# --------------------------------------------------------------------
# SWAP scraping
# --------------------------------------------------------------------


def fetch_page_html(page: int) -> str:
    params = {"page": page}
    headers = {"User-Agent": USER_AGENT}
    resp = requests.get(BROWSE_URL, params=params, headers=headers, timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    return resp.text


def parse_items_from_html(html: str) -> List[Dict]:
    soup = BeautifulSoup(html, "html.parser")
    items = []

    for section in soup.find_all("section", attrs={"data-listingid": True}):
        try:
            link = section.select_one("h2.title a[href]")
            if not link:
                logger.debug("Skipping section without link: %s", section.get("data-listingid"))
                continue

            title = link.get_text(strip=True)
            if not title:
                logger.debug("Skipping section with empty title: %s", section.get("data-listingid"))
                continue

            url = urljoin(BASE_URL, link["href"])
            item_id = section.get("data-listingid")

            price_tag = section.select_one("span.price span.NumberPart")
            if not price_tag:
                # Either skip these or set a default value.
                logger.warning(
                    "No price found for listing %s (%r) at %s",
                    item_id, title, url,
                )
                # If you want to skip items with no price, uncomment:
                # continue
                price = None
            else:
                price_text = price_tag.get_text(strip=True)
                price = price_text  # or clean/Decimal-ize it if you want

            image_tag = section.select_one("div.img-container img[src]")
            if image_tag:
                image_url = image_tag["src"]
            else:
                image_url = None

            items.append(
                {
                    "id": item_id,
                    "title": title,
                    "url": url,
                    "price": price,
                    "image": image_url
                }
            )

        except Exception as e:
            # This prevents one weird section from crashing the whole scrape
            logger.exception("Error parsing section with data-listingid=%r", section.get("data-listingid"))
            # Optional super-verbose debugging:
            # logger.debug("Section HTML:\n%s", section.prettify())
            continue

    # Deduplicate by id in case headings are repeated for some reason
    dedup = {}
    for i in items:
        dedup[i["id"]] = i
    return list(dedup.values())


def fetch_all_items(max_pages: int = MAX_PAGES) -> List[Dict]:
    """
    Walk /Browse?page=0..N until there are no more items or max_pages is reached.
    """
    all_items: List[Dict] = []

    for page in range(0, MAX_PAGES):
        html = fetch_page_html(page)
        items = parse_items_from_html(html)
        if not items:
            # assume we've fallen off the end
            break

        all_items.extend(items)

    # Dedup across pages (just in case)
    by_id = {}
    for i in all_items:
        by_id[i["id"]] = i
    return list(by_id.values())


# --------------------------------------------------------------------
# Email
# --------------------------------------------------------------------


def send_email(subject: str, text_body: str, html_body: str) -> None:
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = EMAIL_FROM
    msg["To"] = EMAIL_TO

    part_text = MIMEText(text_body, "plain", "utf-8")
    part_html = MIMEText(html_body, "html", "utf-8")

    # Order matters: plain first, then HTML
    msg.attach(part_text)
    msg.attach(part_html)

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as smtp:
        smtp.starttls()
        smtp.login(SMTP_USER, SMTP_PASS)
        smtp.send_message(msg)


def format_email_bodies(new_items: List[Dict]) -> tuple[str, str]:
    # ---------- Plain text (fallback) ----------
    text_lines = []
    text_lines.append(f"New SWAP items ({len(new_items)}):\n")

    for item in sorted(new_items, key=lambda i: i["title"].lower()):
        price = item.get("price") or "N/A"
        text_lines.append(f"- {item['title']} ({price})")
        text_lines.append(f"  {item['url']}")
        image_url = item.get("image")
        if image_url:
            text_lines.append(f"  Image: {image_url}")
        text_lines.append("")

    text_body = "\n".join(text_lines)

    # ---------- HTML ----------
    html_items = []

    for item in sorted(new_items, key=lambda i: i["title"].lower()):
        title = item["title"]
        url = item["url"]
        price = item.get("price") or "N/A"
        image_url = item.get("image")

        # Simple "card" per item
        item_html = [
            '<tr>',
            '  <td style="padding: 10px; border-bottom: 1px solid #ddd;">',
            f'    <div style="font-size: 16px; font-weight: bold; margin-bottom: 4px;">'
            f'<a href="{url}" style="color: #1155cc; text-decoration: none;">{title}</a></div>',
            f'    <div style="margin-bottom: 4px; color: #555;">Price: {price}</div>',
        ]

        if image_url:
            item_html.append(
                f'    <div style="margin-bottom: 4px;">'
                f'<a href="{url}"><img src="{image_url}" alt="" '
                f'style="max-width: 200px; height: auto; border: 1px solid #ccc;" /></a></div>'
            )

        item_html.append(
            f'    <div style="font-size: 12px;"><a href="{url}">{url}</a></div>'
        )
        item_html.append("  </td>")
        item_html.append("</tr>")

        html_items.append("\n".join(item_html))

    html_body = f"""\
<!DOCTYPE html>
<html>
  <head>
    <meta charset="utf-8" />
    <title>New SWAP items</title>
  </head>
  <body style="font-family: Arial, sans-serif; font-size: 14px; color: #333;">
    <h2>New SWAP items ({len(new_items)})</h2>
    <table cellspacing="0" cellpadding="0" border="0" style="border-collapse: collapse; width: 100%; max-width: 700px;">
      {''.join(html_items)}
    </table>
  </body>
</html>
"""

    return text_body, html_body


# --------------------------------------------------------------------
# Main
# --------------------------------------------------------------------


def main() -> None:
    init_db()

    seen_ids = get_seen_ids()
    all_items = fetch_all_items()
    new_items = [i for i in all_items if i["id"] not in seen_ids]

    if not new_items:
        print("No new items.")
        return

    subject = f"{len(new_items)} new SWAP item(s) found"
    text_body, html_body = format_email_bodies(new_items)
    send_email(subject, text_body, html_body)

    add_seen_ids({i["id"] for i in new_items})
    print(f"Sent email with {len(new_items)} new items.")


if __name__ == "__main__":
    main()
