"""Main auction watcher orchestrator."""
import logging
from typing import List, Dict

from .repository import ItemRepository
from .scraper import ScraperService
from .email_service import EmailService


logger = logging.getLogger(__name__)


class AuctionWatcher:
    """Orchestrates the auction watching workflow."""

    def __init__(
        self,
        repository: ItemRepository,
        scraper: ScraperService,
        email_service: EmailService,
        max_pages: int
    ):
        """Initialize the auction watcher.

        Args:
            repository: Repository for tracking seen items
            scraper: Service for scraping auction items
            email_service: Service for sending email notifications
            max_pages: Maximum number of pages to scrape
        """
        self.repository = repository
        self.scraper = scraper
        self.email_service = email_service
        self.max_pages = max_pages

    def run(self) -> Dict[str, int]:
        """Run a single check for new auction items.

        Returns:
            Dictionary with 'new_items' and 'total_items' counts
        """
        logger.info("Starting auction watcher run")

        # Initialize database if needed
        self.repository.initialize()

        # Get previously seen items
        seen_ids = self.repository.get_seen_ids()
        logger.info("Found %d previously seen items", len(seen_ids))

        # Fetch current items
        all_items = self.scraper.fetch_all_items(self.max_pages)
        logger.info("Fetched %d total items", len(all_items))

        # Identify new items
        new_items = self._filter_new_items(all_items, seen_ids)
        logger.info("Identified %d new items", len(new_items))

        # Record new items
        if new_items:
            new_ids = {item["id"] for item in new_items}
            rows_added = self.repository.add_seen_ids(new_ids)
            logger.info("Added %d new item IDs to database", rows_added)

        # Send notification
        self.email_service.send_notification(new_items, len(all_items))

        return {
            "new_items": len(new_items),
            "total_items": len(all_items)
        }

    def _filter_new_items(
        self,
        all_items: List[Dict[str, str]],
        seen_ids: set
    ) -> List[Dict[str, str]]:
        """Filter items to find only new ones.

        Args:
            all_items: All items fetched from the site
            seen_ids: Set of previously seen item IDs

        Returns:
            List of new items not in seen_ids
        """
        return [item for item in all_items if item["id"] not in seen_ids]
