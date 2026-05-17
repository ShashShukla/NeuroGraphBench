"""Shared pytest fixtures.

The FastAPI app's neo4j driver dependency is overridden with a `MagicMock`
so tests do not require a live database. Tests configure the mock's
`execute_query` return value before calling the endpoint.
"""

from collections.abc import Iterator
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from fba.server.app import app
from fba.server.neo4j_driver import getDriver


@pytest.fixture
def mockDriver() -> MagicMock:
    """A MagicMock standing in for a `neo4j.Driver`.

    Configure per-test::

        mockDriver.execute_query.return_value = (records, summary, keys)

    where `records` is a list of dict-like rows.
    """
    return MagicMock()


@pytest.fixture
def client(mockDriver: MagicMock) -> Iterator[TestClient]:
    """FastAPI TestClient with the neo4j driver dependency overridden."""
    app.dependency_overrides[getDriver] = lambda: mockDriver
    try:
        with TestClient(app) as testClient:
            yield testClient
    finally:
        app.dependency_overrides.pop(getDriver, None)
