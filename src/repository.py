"""Database repository for tracking seen auction items."""
import sqlite3
from datetime import datetime, UTC
from pathlib import Path
from typing import Set, Iterable, Protocol


class Connection(Protocol):
    """Protocol for database connections (allows for easier testing)."""

    def execute(self, sql: str, parameters: tuple = ()) -> sqlite3.Cursor:
        """Execute a SQL statement."""
        ...

    def commit(self) -> None:
        """Commit the current transaction."""
        ...

    def close(self) -> None:
        """Close the connection."""
        ...


class ItemRepository:
    """Repository for managing seen auction items in the database."""

    def __init__(self, db_path: Path):
        """Initialize the repository.

        Args:
            db_path: Path to the SQLite database file
        """
        self.db_path = db_path

    def get_connection(self) -> sqlite3.Connection:
        """Create and return a database connection.

        Returns:
            SQLite connection with WAL mode enabled
        """
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA journal_mode=WAL;")
        return conn

    def initialize(self) -> None:
        """Create the database schema if it doesn't exist."""
        conn = self.get_connection()
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

    def get_seen_ids(self) -> Set[str]:
        """Retrieve all seen item IDs from the database.

        Returns:
            Set of item IDs that have been seen before
        """
        conn = self.get_connection()
        try:
            cur = conn.execute("SELECT id FROM seen_items")
            return {row[0] for row in cur.fetchall()}
        finally:
            conn.close()

    def add_seen_ids(self, ids: Iterable[str]) -> int:
        """Add new item IDs to the seen items table.

        Args:
            ids: Iterable of item IDs to mark as seen

        Returns:
            Number of new items added (excludes duplicates)
        """
        id_list = list(ids)
        if not id_list:
            return 0

        now = datetime.now(UTC).isoformat()
        conn = self.get_connection()
        try:
            cur = conn.cursor()
            cur.executemany(
                "INSERT OR IGNORE INTO seen_items (id, first_seen_at) VALUES (?, ?)",
                [(item_id, now) for item_id in id_list],
            )
            rows_affected = cur.rowcount
            conn.commit()
            return rows_affected
        finally:
            conn.close()

    def clear_all(self) -> None:
        """Clear all seen items from the database (useful for testing)."""
        conn = self.get_connection()
        try:
            conn.execute("DELETE FROM seen_items")
            conn.commit()
        finally:
            conn.close()
