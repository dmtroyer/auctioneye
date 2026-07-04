"""Tests that create_watcher wires up the DynamoDB repository."""
import boto3
import pytest
from moto import mock_aws

from src.config import Config
from src.dynamo_repository import DynamoItemRepository
from src.watcher import create_watcher


def _config(**overrides) -> Config:
    base = dict(
        base_url="https://example.com",
        browse_path="/Browse",
        max_pages=1,
        dynamodb_table="some-table",
        smtp_host="smtp.example.com",
        smtp_port=587,
        smtp_user="u@example.com",
        smtp_pass="pw",
        email_from="u@example.com",
        email_to="u@example.com",
        user_agent="test",
        request_timeout=5,
        log_level="INFO",
    )
    base.update(overrides)
    return Config(**base)


def test_create_watcher_uses_dynamo():
    with mock_aws():
        boto3.setup_default_session(region_name="us-east-2")
        watcher = create_watcher(_config())
        assert isinstance(watcher.repository, DynamoItemRepository)
        assert watcher.repository.table_name == "some-table"


def test_config_requires_dynamodb_table(monkeypatch):
    monkeypatch.setenv("BASE_URL", "https://example.com")
    monkeypatch.setenv("SMTP_USER", "u@example.com")
    monkeypatch.setenv("SMTP_PASS", "pw")
    monkeypatch.delenv("DYNAMODB_TABLE", raising=False)
    with pytest.raises(KeyError, match="DYNAMODB_TABLE"):
        Config.from_env()
