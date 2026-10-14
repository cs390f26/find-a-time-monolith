"""Shared pytest fixtures.

Fixtures are setup helpers: when a test lists a fixture name as a parameter,
pytest runs the fixture first and passes in its result. They are defined here
(conftest.py) so every test file can use them without importing.

These tests use DynamoDB Local (see docs/development.md): it must be running and
the Events table must exist. In CI it runs as a service container (.github/workflows/ci.yml).
"""

import pytest

from findatime.app import create_app
from findatime.app_logic import FindATimeApp
from findatime.db import EventStorage
from findatime.settings import ensure_settings


@pytest.fixture
def store():
    """An EventStorage connected to the Events table, emptied before the test."""
    settings = ensure_settings()
    storage = EventStorage(
        table_name=settings["EVENTS_TABLE_NAME"],
        region_name=settings["AWS_DEFAULT_REGION"],
        endpoint_url=settings["DYNAMODB_ENDPOINT_URL"],
    )
    storage.delete_all_events()
    return storage


@pytest.fixture
def app_logic(store):
    """The business layer, using the empty store."""
    return FindATimeApp(store)


@pytest.fixture
def client(app_logic):
    """A Flask test client: sends HTTP requests to the app without a real server."""
    flask_app = create_app(app_logic)
    flask_app.config["TESTING"] = True
    return flask_app.test_client()


@pytest.fixture
def missing_table_store():
    """An EventStorage whose table does not exist, to test "database unavailable" paths."""
    settings = ensure_settings()
    return EventStorage(
        table_name="TableThatDoesNotExist",
        region_name=settings["AWS_DEFAULT_REGION"],
        endpoint_url=settings["DYNAMODB_ENDPOINT_URL"],
    )
