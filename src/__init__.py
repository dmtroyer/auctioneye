"""AuctionEye - Auction monitoring and notification system."""

__version__ = "1.0.0"

from .config import Config
from .repository import ItemRepository
from .scraper import ScraperService
from .email_service import EmailService, EmailConfig
from .watcher_service import AuctionWatcher

__all__ = [
    "Config",
    "ItemRepository",
    "ScraperService",
    "EmailService",
    "EmailConfig",
    "AuctionWatcher",
]
