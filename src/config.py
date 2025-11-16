"""Configuration management for AuctionEye."""
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from urllib.parse import urlencode, urljoin

from dotenv import load_dotenv


@dataclass
class Config:
    """Application configuration loaded from environment variables."""

    # Site configuration
    base_url: str
    browse_path: str
    max_pages: int

    # Database configuration
    db_path: Path

    # SMTP configuration
    smtp_host: str
    smtp_port: int
    smtp_user: str
    smtp_pass: str
    email_from: str
    email_to: str

    # HTTP configuration
    user_agent: str
    request_timeout: int

    # Logging
    log_level: str

    @property
    def browse_url(self) -> str:
        """Construct the full browse URL with query parameters."""
        param_string = urlencode(
            {"ViewStyle": "list", "StatusFilter": "active_only", "SortFilterOptions": "1"},
            doseq=True
        )
        base = urljoin(self.base_url, self.browse_path)
        return f"{base}?{param_string}"

    @classmethod
    def from_env(cls, env_file: Optional[Path] = None) -> "Config":
        """Load configuration from environment variables.

        Args:
            env_file: Optional path to .env file to load

        Returns:
            Config instance

        Raises:
            KeyError: If required environment variables are missing
        """
        if env_file:
            load_dotenv(env_file)
        else:
            load_dotenv()

        # Required variables
        base_url = os.environ["BASE_URL"]
        smtp_user = os.environ["SMTP_USER"]
        smtp_pass = os.environ["SMTP_PASS"]

        # Optional with defaults
        log_level = os.getenv("LOG_LEVEL", "INFO").upper()
        browse_path = os.getenv("BROWSE_PATH", "/Browse")
        max_pages = int(os.getenv("MAX_PAGES", "20"))
        db_path = Path(os.getenv("DB_PATH", "/data/seen_items.db"))

        smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
        smtp_port = int(os.getenv("SMTP_PORT", "587"))
        email_from = os.getenv("EMAIL_FROM", smtp_user)
        email_to = os.getenv("EMAIL_TO", smtp_user)

        user_agent = os.getenv(
            "USER_AGENT",
            "swap-watcher/1.0 (+personal script; contact owner of this account)",
        )
        request_timeout = int(os.getenv("REQUEST_TIMEOUT", "20"))

        return cls(
            base_url=base_url,
            browse_path=browse_path,
            max_pages=max_pages,
            db_path=db_path,
            smtp_host=smtp_host,
            smtp_port=smtp_port,
            smtp_user=smtp_user,
            smtp_pass=smtp_pass,
            email_from=email_from,
            email_to=email_to,
            user_agent=user_agent,
            request_timeout=request_timeout,
            log_level=log_level,
        )
