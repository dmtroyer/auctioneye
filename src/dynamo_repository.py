"""DynamoDB repository for tracking seen auction items.

Stores seen item IDs in a DynamoDB table (provisioned by Terraform).

Table shape:
    id            (String)  -- partition key
    first_seen_at (String)  -- ISO-8601 UTC timestamp
"""
import logging
from datetime import datetime, UTC
from typing import Set, Iterable

import boto3


logger = logging.getLogger(__name__)


class DynamoItemRepository:
    """Repository for managing seen auction items in DynamoDB."""

    def __init__(self, table_name: str, dynamodb_resource=None):
        """Initialize the repository.

        Args:
            table_name: Name of the DynamoDB table.
            dynamodb_resource: Optional boto3 DynamoDB resource (for testing).
        """
        self.table_name = table_name
        resource = dynamodb_resource or boto3.resource("dynamodb")
        self.table = resource.Table(table_name)

    def initialize(self) -> None:
        """No-op: the table is provisioned by Terraform."""
        return None

    def get_seen_ids(self) -> Set[str]:
        """Retrieve all seen item IDs from the table.

        Returns:
            Set of item IDs that have been seen before.
        """
        seen: Set[str] = set()
        scan_kwargs = {"ProjectionExpression": "#id", "ExpressionAttributeNames": {"#id": "id"}}
        while True:
            response = self.table.scan(**scan_kwargs)
            seen.update(item["id"] for item in response.get("Items", []))
            last_key = response.get("LastEvaluatedKey")
            if not last_key:
                break
            scan_kwargs["ExclusiveStartKey"] = last_key
        return seen

    def add_seen_ids(self, ids: Iterable[str]) -> int:
        """Add new item IDs to the table.

        Callers filter against ``get_seen_ids`` first, so an idempotent put is
        correct; a re-put simply overwrites with the same value.

        Args:
            ids: Iterable of item IDs to mark as seen.

        Returns:
            Number of item IDs written.
        """
        id_list = list(ids)
        if not id_list:
            return 0

        now = datetime.now(UTC).isoformat()
        with self.table.batch_writer() as batch:
            for item_id in id_list:
                batch.put_item(Item={"id": item_id, "first_seen_at": now})
        return len(id_list)

    def clear_all(self) -> None:
        """Delete all seen items from the table (useful for testing)."""
        with self.table.batch_writer() as batch:
            for item_id in self.get_seen_ids():
                batch.delete_item(Key={"id": item_id})
