import logging
from unittest.mock import patch

import pytest

import bleak_retry_connector


@pytest.fixture(autouse=True)
def configure_test_logging(caplog):
    caplog.set_level(logging.DEBUG)


@pytest.fixture()
def mock_linux():
    with patch.object(bleak_retry_connector, "IS_LINUX", True), patch.object(
        bleak_retry_connector.bluez, "IS_LINUX", True
    ):
        yield


@pytest.fixture()
def mock_macos():
    with patch.object(bleak_retry_connector, "IS_LINUX", False), patch.object(
        bleak_retry_connector.bluez, "IS_LINUX", False
    ):
        yield
