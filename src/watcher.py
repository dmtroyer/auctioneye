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
from jinja2 import Environment, FileSystemLoader, select_autoescape
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
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

env = Environment(
    loader=FileSystemLoader(str(BASE_DIR / "templates")),
    autoescape=select_autoescape(["html", "xml"]),
)
html_template = env.get_template("email.html.j2")
html_no_items_template = env.get_template("email-no-items.html.j2")
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


from typing import List, Dict

from typing import List, Dict

def format_email_bodies(new_items: List[Dict]) -> tuple[str, str]:
    if not new_items:
        # Plain text fallback
        text_body = "No new SWAP items.\n\nThe watcher ran successfully."

        # HTML body from the no-items template
        html_body = html_no_items_template.render(
            run_timestamp=datetime.now(UTC).isoformat()
        )
        return text_body, html_body

    # ---------- New items case ----------
    text_lines = [f"New SWAP items ({len(new_items)}):", ""]
    for item in sorted(new_items, key=lambda i: i["title"].lower()):
        price = item.get("price") or "N/A"
        text_lines.append(f"- {item['title']} ({price})")
        text_lines.append(f"  {item['url']}")
        if item.get("image"):
            text_lines.append(f"  Image: {item['image']}")
        text_lines.append("")
    text_body = "\n".join(text_lines)

    html_body = html_template.render(items=new_items)
    return text_body, html_body


# --------------------------------------------------------------------
# Main
# --------------------------------------------------------------------


def main() -> None:
    init_db()

    seen_ids = get_seen_ids()
    all_items = fetch_all_items()
    new_items = [i for i in all_items if i["id"] not in seen_ids]

    if new_items:
        subject = f"{len(new_items)} new SWAP item(s) found"
        # record new ids only when there actually are new items
        add_seen_ids({i["id"] for i in new_items})
    else:
        subject = "No new SWAP items"

    text_body, html_body = format_email_bodies(new_items)
    send_email(subject, text_body, html_body)

    print(
        f"Email sent. New items: {len(new_items)}. "
        f"Total items on page(s): {len(all_items)}."
    )


if __name__ == "__main__":
    main()
