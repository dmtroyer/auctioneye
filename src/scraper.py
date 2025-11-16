"""Web scraping service for auction items."""
import logging
from typing import List, Dict, Protocol
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


logger = logging.getLogger(__name__)


class HttpClient(Protocol):
    """Protocol for HTTP clients (allows for easier testing)."""

    def get(self, url: str, **kwargs) -> requests.Response:
        """Make a GET request."""
        ...


class ScraperService:
    """Service for scraping auction items from web pages."""

    def __init__(
        self,
        base_url: str,
        browse_url: str,
        user_agent: str,
        timeout: int = 20,
        http_client: HttpClient = requests
    ):
        """Initialize the scraper service.

        Args:
            base_url: Base URL of the auction site
            browse_url: Full URL for browsing items (with query params)
            user_agent: User agent string for HTTP requests
            timeout: Request timeout in seconds
            http_client: HTTP client to use (defaults to requests module)
        """
        self.base_url = base_url
        self.browse_url = browse_url
        self.user_agent = user_agent
        self.timeout = timeout
        self.http_client = http_client

    def fetch_page_html(self, page: int) -> str:
        """Fetch HTML content for a specific page number.

        Args:
            page: Page number to fetch

        Returns:
            HTML content as string

        Raises:
            requests.HTTPError: If the request fails
        """
        params = {"page": page}
        headers = {"User-Agent": self.user_agent}

        resp = self.http_client.get(
            self.browse_url,
            params=params,
            headers=headers,
            timeout=self.timeout
        )
        resp.raise_for_status()
        return resp.text

    def parse_items_from_html(self, html: str) -> List[Dict[str, str]]:
        """Parse auction items from HTML content.

        Args:
            html: HTML content to parse

        Returns:
            List of item dictionaries with keys: id, title, url, price, image
        """
        soup = BeautifulSoup(html, "html.parser")
        items = []

        for section in soup.find_all("section", attrs={"data-listingid": True}):
            try:
                item = self._parse_item_section(section)
                if item:
                    items.append(item)
            except Exception:
                logger.exception(
                    "Error parsing section with data-listingid=%r",
                    section.get("data-listingid")
                )
                continue

        # Deduplicate by id in case items are repeated
        dedup = {item["id"]: item for item in items}
        return list(dedup.values())

    def _parse_item_section(self, section) -> Dict[str, str] | None:
        """Parse a single item section from the HTML.

        Args:
            section: BeautifulSoup section element

        Returns:
            Item dictionary or None if section cannot be parsed
        """
        # Extract link and title
        link = section.select_one("h2.title a[href]")
        if not link:
            logger.debug(
                "Skipping section without link: %s",
                section.get("data-listingid")
            )
            return None

        title = link.get_text(strip=True)
        if not title:
            logger.debug(
                "Skipping section with empty title: %s",
                section.get("data-listingid")
            )
            return None

        url = urljoin(self.base_url, link["href"])
        item_id = section.get("data-listingid")

        # Extract price
        price_tag = section.select_one("span.price span.NumberPart")
        if not price_tag:
            logger.warning(
                "No price found for listing %s (%r) at %s",
                item_id, title, url
            )
            price = None
        else:
            price = price_tag.get_text(strip=True)

        # Extract image
        image_tag = section.select_one("div.img-container img[src]")
        image_url = image_tag["src"] if image_tag else None

        return {
            "id": item_id,
            "title": title,
            "url": url,
            "price": price,
            "image": image_url
        }

    def fetch_all_items(self, max_pages: int) -> List[Dict[str, str]]:
        """Fetch all items across multiple pages.

        Args:
            max_pages: Maximum number of pages to fetch

        Returns:
            List of all items found, deduplicated by ID
        """
        all_items: List[Dict[str, str]] = []

        for page in range(max_pages):
            logger.info("Fetching page %d", page)
            html = self.fetch_page_html(page)
            items = self.parse_items_from_html(html)

            if not items:
                logger.info("No items found on page %d, stopping", page)
                break

            logger.info("Found %d items on page %d", len(items), page)
            all_items.extend(items)

        # Deduplicate across pages
        by_id = {item["id"]: item for item in all_items}
        return list(by_id.values())
