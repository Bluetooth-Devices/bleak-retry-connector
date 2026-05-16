import logging
from collections.abc import Iterator
from unittest.mock import patch

import pytest
from blockbuster import BlockBuster, blockbuster_ctx

import bleak_retry_connector


@pytest.fixture(autouse=True)
def configure_test_logging(caplog):
    caplog.set_level(logging.DEBUG)


@pytest.fixture(autouse=True)
def blockbuster() -> Iterator[BlockBuster]:
    with blockbuster_ctx("bleak_retry_connector") as bb:
        yield bb


@pytest.fixture()
def mock_linux():
    with (
        patch.object(bleak_retry_connector, "IS_LINUX", True),
        patch.object(bleak_retry_connector.bluez, "IS_LINUX", True),
        patch.object(bleak_retry_connector.bleak_manager, "IS_LINUX", True),
        patch("bleak.backends.platform.system", return_value="Linux"),
    ):
        yield


@pytest.fixture()
def mock_macos():
    with (
        patch.object(bleak_retry_connector, "IS_LINUX", False),
        patch.object(bleak_retry_connector.bluez, "IS_LINUX", False),
        patch.object(bleak_retry_connector.bleak_manager, "IS_LINUX", False),
    ):
        yield
