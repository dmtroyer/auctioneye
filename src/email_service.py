"""Email service for sending auction notifications."""
import logging
import smtplib
from dataclasses import dataclass
from datetime import datetime, UTC
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pathlib import Path
from typing import List, Dict, Protocol

from jinja2 import Environment, FileSystemLoader, select_autoescape


logger = logging.getLogger(__name__)


class SmtpClient(Protocol):
    """Protocol for SMTP clients (allows for easier testing)."""

    def starttls(self) -> None:
        """Start TLS encryption."""
        ...

    def login(self, user: str, password: str) -> None:
        """Login to SMTP server."""
        ...

    def send_message(self, msg: MIMEMultipart) -> None:
        """Send an email message."""
        ...


@dataclass
class EmailConfig:
    """Configuration for email sending."""
    smtp_host: str
    smtp_port: int
    smtp_user: str
    smtp_pass: str
    email_from: str
    email_to: str


class EmailService:
    """Service for formatting and sending email notifications."""

    def __init__(
        self,
        config: EmailConfig,
        template_dir: Path,
        smtp_factory=None
    ):
        """Initialize the email service.

        Args:
            config: Email configuration
            template_dir: Directory containing Jinja2 email templates
            smtp_factory: Factory function for creating SMTP connections
                         (defaults to smtplib.SMTP)
        """
        self.config = config
        self.smtp_factory = smtp_factory or self._default_smtp_factory

        # Set up Jinja2 environment for templates
        self.env = Environment(
            loader=FileSystemLoader(str(template_dir)),
            autoescape=select_autoescape(["html", "xml"]),
        )
        self.html_template = self.env.get_template("email.html.j2")
        self.html_no_items_template = self.env.get_template("email-no-items.html.j2")

    def _default_smtp_factory(self):
        """Default factory for creating SMTP connections."""
        return smtplib.SMTP(self.config.smtp_host, self.config.smtp_port)

    def format_email_bodies(
        self,
        new_items: List[Dict[str, str]]
    ) -> tuple[str, str]:
        """Format plain text and HTML email bodies.

        Args:
            new_items: List of new auction items

        Returns:
            Tuple of (text_body, html_body)
        """
        if not new_items:
            return self._format_no_items_email()

        return self._format_new_items_email(new_items)

    def _format_no_items_email(self) -> tuple[str, str]:
        """Format email for when there are no new items."""
        text_body = "No new SWAP items.\n\nThe watcher ran successfully."
        html_body = self.html_no_items_template.render(
            run_timestamp=datetime.now(UTC).isoformat()
        )
        return text_body, html_body

    def _format_new_items_email(
        self,
        new_items: List[Dict[str, str]]
    ) -> tuple[str, str]:
        """Format email for new items found.

        Args:
            new_items: List of new auction items

        Returns:
            Tuple of (text_body, html_body)
        """
        # Plain text version
        text_lines = [f"New SWAP items ({len(new_items)}):", ""]
        for item in sorted(new_items, key=lambda i: i["title"].lower()):
            price = item.get("price") or "N/A"
            text_lines.append(f"- {item['title']} ({price})")
            text_lines.append(f"  {item['url']}")
            if item.get("image"):
                text_lines.append(f"  Image: {item['image']}")
            text_lines.append("")
        text_body = "\n".join(text_lines)

        # HTML version
        html_body = self.html_template.render(items=new_items)

        return text_body, html_body

    def send_email(
        self,
        subject: str,
        text_body: str,
        html_body: str
    ) -> None:
        """Send an email notification.

        Args:
            subject: Email subject line
            text_body: Plain text email body
            html_body: HTML email body

        Raises:
            smtplib.SMTPException: If email sending fails
        """
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = self.config.email_from
        msg["To"] = self.config.email_to

        part_text = MIMEText(text_body, "plain", "utf-8")
        part_html = MIMEText(html_body, "html", "utf-8")

        # Order matters: plain first, then HTML
        msg.attach(part_text)
        msg.attach(part_html)

        with self.smtp_factory() as smtp:
            smtp.starttls()
            smtp.login(self.config.smtp_user, self.config.smtp_pass)
            smtp.send_message(msg)

        logger.info("Email sent successfully to %s", self.config.email_to)

    def send_notification(
        self,
        new_items: List[Dict[str, str]],
        total_items: int
    ) -> None:
        """Send a notification email about new items.

        Args:
            new_items: List of new auction items found
            total_items: Total number of items scanned
        """
        if new_items:
            subject = f"{len(new_items)} new SWAP item(s) found"
        else:
            subject = "No new SWAP items"

        text_body, html_body = self.format_email_bodies(new_items)
        self.send_email(subject, text_body, html_body)

        logger.info(
            "Notification sent: %d new items, %d total items",
            len(new_items), total_items
        )
