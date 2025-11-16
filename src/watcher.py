#!/usr/bin/env python3
"""
Auction watcher - monitors auction site for new items and sends email notifications.

This is the legacy entry point maintained for backward compatibility.
The code has been refactored into modular components in separate files.
"""
import logging
from pathlib import Path

from .config import Config
from .repository import ItemRepository
from .scraper import ScraperService
from .email_service import EmailService, EmailConfig
from .watcher_service import AuctionWatcher


def setup_logging(log_level: str) -> None:
    """Configure logging for the application."""
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )


def create_watcher(config: Config) -> AuctionWatcher:
    """Create and configure the auction watcher with all dependencies.

    Args:
        config: Application configuration

    Returns:
        Configured AuctionWatcher instance
    """
    # Create repository
    repository = ItemRepository(config.db_path)

    # Create scraper
    scraper = ScraperService(
        base_url=config.base_url,
        browse_url=config.browse_url,
        user_agent=config.user_agent,
        timeout=config.request_timeout,
    )

    # Create email service
    email_config = EmailConfig(
        smtp_host=config.smtp_host,
        smtp_port=config.smtp_port,
        smtp_user=config.smtp_user,
        smtp_pass=config.smtp_pass,
        email_from=config.email_from,
        email_to=config.email_to,
    )
    template_dir = Path(__file__).resolve().parent / "templates"
    email_service = EmailService(email_config, template_dir)

    # Create watcher with all dependencies
    return AuctionWatcher(
        repository=repository,
        scraper=scraper,
        email_service=email_service,
        max_pages=config.max_pages,
    )


def main() -> None:
    """Main entry point for the auction watcher."""
    # Load configuration
    config = Config.from_env()

    # Set up logging
    setup_logging(config.log_level)
    logger = logging.getLogger(__name__)

    try:
        # Create and run watcher
        watcher = create_watcher(config)
        result = watcher.run()

        # Print summary
        print(
            f"Email sent. New items: {result['new_items']}. "
            f"Total items on page(s): {result['total_items']}."
        )

    except Exception:
        logger.exception("Fatal error during watcher execution")
        raise


if __name__ == "__main__":
    main()
