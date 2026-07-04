"""Tests for the DynamoDB repository using moto to mock DynamoDB."""
import boto3
import pytest
from moto import mock_aws

from src.dynamo_repository import DynamoItemRepository

TABLE_NAME = "test-seen-items"


@pytest.fixture
def dynamo_table():
    """Create a mocked DynamoDB table matching the Terraform schema."""
    with mock_aws():
        resource = boto3.resource("dynamodb", region_name="us-east-1")
        resource.create_table(
            TableName=TABLE_NAME,
            KeySchema=[{"AttributeName": "id", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "id", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )
        yield resource


@pytest.fixture
def repo(dynamo_table):
    return DynamoItemRepository(TABLE_NAME, dynamodb_resource=dynamo_table)


def test_get_seen_ids_empty(repo):
    assert repo.get_seen_ids() == set()


def test_add_and_get_round_trip(repo):
    added = repo.add_seen_ids(["a", "b", "c"])
    assert added == 3
    assert repo.get_seen_ids() == {"a", "b", "c"}


def test_add_empty_is_noop(repo):
    assert repo.add_seen_ids([]) == 0
    assert repo.get_seen_ids() == set()


def test_add_is_idempotent(repo):
    repo.add_seen_ids(["a", "b"])
    repo.add_seen_ids(["b", "c"])
    assert repo.get_seen_ids() == {"a", "b", "c"}


def test_clear_all(repo):
    repo.add_seen_ids(["a", "b", "c"])
    repo.clear_all()
    assert repo.get_seen_ids() == set()


def test_get_seen_ids_paginates(repo):
    ids = [f"item-{i}" for i in range(150)]
    repo.add_seen_ids(ids)
    assert repo.get_seen_ids() == set(ids)


def test_initialize_is_noop(repo):
    repo.initialize()  # should not raise
