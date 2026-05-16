"""Tests for the bleak_manager helpers (DBus socket cache + global manager getter)."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock

import pytest

import bleak_retry_connector
from bleak_retry_connector.bleak_manager import (
    _reset_dbus_socket_cache,
    get_global_bluez_manager_with_timeout,
)

pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
def _clear_dbus_socket_cache():
    """Ensure the _has_dbus_socket attribute is reset around every test."""
    _reset_dbus_socket_cache()
    yield
    _reset_dbus_socket_cache()


async def test_returns_none_on_non_linux(mock_macos):
    """On non-Linux platforms the helper returns None without touching DBus."""
    assert await get_global_bluez_manager_with_timeout() is None


async def test_returns_cached_manager_when_loop_already_registered(
    mock_linux, monkeypatch
):
    """If the loop is already registered in _global_instances, return that manager."""
    sentinel_manager = object()
    loop = asyncio.get_running_loop()
    monkeypatch.setattr(
        bleak_retry_connector.bleak_manager,
        "_global_instances",
        {loop: sentinel_manager},
    )
    # If we hit this, get_global_bluez_manager should never be called.
    mock_get = AsyncMock(side_effect=AssertionError("should not be called"))
    monkeypatch.setattr(
        bleak_retry_connector.bleak_manager, "get_global_bluez_manager", mock_get
    )

    assert await get_global_bluez_manager_with_timeout() is sentinel_manager
    mock_get.assert_not_called()


async def test_short_circuits_after_filenotfound_is_cached(mock_linux, monkeypatch):
    """A FileNotFoundError marks the socket missing and skips subsequent calls."""
    monkeypatch.setattr(bleak_retry_connector.bleak_manager, "_global_instances", {})
    mock_get = AsyncMock(side_effect=FileNotFoundError(2, "no such file", "/run/dbus"))
    monkeypatch.setattr(
        bleak_retry_connector.bleak_manager, "get_global_bluez_manager", mock_get
    )

    assert await get_global_bluez_manager_with_timeout() is None
    assert mock_get.call_count == 1

    # Second call must not retry — the cache short-circuits to None.
    assert await get_global_bluez_manager_with_timeout() is None
    assert mock_get.call_count == 1


async def test_short_circuits_after_timeout_is_cached(mock_linux, monkeypatch):
    """An asyncio.TimeoutError also flips the cache to False and skips retries."""
    monkeypatch.setattr(bleak_retry_connector.bleak_manager, "_global_instances", {})
    mock_get = AsyncMock(side_effect=asyncio.TimeoutError())
    monkeypatch.setattr(
        bleak_retry_connector.bleak_manager, "get_global_bluez_manager", mock_get
    )

    assert await get_global_bluez_manager_with_timeout() is None
    assert mock_get.call_count == 1

    # Second call must not retry — the cache short-circuits to None.
    assert await get_global_bluez_manager_with_timeout() is None
    assert mock_get.call_count == 1


async def test_generic_exception_returns_none_but_does_not_cache(
    mock_linux, monkeypatch
):
    """A generic exception logs and returns None, but does NOT poison the cache."""
    monkeypatch.setattr(bleak_retry_connector.bleak_manager, "_global_instances", {})
    mock_get = AsyncMock(side_effect=RuntimeError("boom"))
    monkeypatch.setattr(
        bleak_retry_connector.bleak_manager, "get_global_bluez_manager", mock_get
    )

    assert await get_global_bluez_manager_with_timeout() is None
    assert mock_get.call_count == 1

    # A generic exception (not FileNotFoundError / TimeoutError) does NOT flip the
    # _has_dbus_socket cache to False, so a subsequent call still tries again.
    assert await get_global_bluez_manager_with_timeout() is None
    assert mock_get.call_count == 2


async def test_returns_manager_on_success(mock_linux, monkeypatch):
    """When get_global_bluez_manager succeeds, its return value is propagated."""
    sentinel_manager = object()
    monkeypatch.setattr(bleak_retry_connector.bleak_manager, "_global_instances", {})
    mock_get = AsyncMock(return_value=sentinel_manager)
    monkeypatch.setattr(
        bleak_retry_connector.bleak_manager, "get_global_bluez_manager", mock_get
    )

    assert await get_global_bluez_manager_with_timeout() is sentinel_manager
    mock_get.assert_awaited_once()


async def test_reset_dbus_socket_cache_re_enables_retries(mock_linux, monkeypatch):
    """_reset_dbus_socket_cache() lets the helper retry after a cached failure."""
    monkeypatch.setattr(bleak_retry_connector.bleak_manager, "_global_instances", {})
    sentinel_manager = object()
    mock_get = AsyncMock(
        side_effect=[
            FileNotFoundError(2, "no such file", "/run/dbus"),
            sentinel_manager,
        ]
    )
    monkeypatch.setattr(
        bleak_retry_connector.bleak_manager, "get_global_bluez_manager", mock_get
    )

    # First call: cache flips to False.
    assert await get_global_bluez_manager_with_timeout() is None
    # Second call would short-circuit without the reset.
    assert await get_global_bluez_manager_with_timeout() is None
    assert mock_get.call_count == 1

    _reset_dbus_socket_cache()

    # After reset, the helper tries again and gets the manager.
    assert await get_global_bluez_manager_with_timeout() is sentinel_manager
    assert mock_get.call_count == 2
