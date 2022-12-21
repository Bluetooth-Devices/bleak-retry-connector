from __future__ import annotations

import asyncio
import contextlib
import logging
import platform

import async_timeout

DISCONNECT_TIMEOUT = 5
DBUS_CONNECT_TIMEOUT = 8.5

_LOGGER = logging.getLogger(__name__)

IS_LINUX = platform.system() == "Linux"
DEFAULT_ATTEMPTS = 2

if IS_LINUX:
    with contextlib.suppress(ImportError):  # pragma: no cover
        from bleak.backends.bluezdbus.manager import (  # pragma: no cover
            BlueZManager,
            get_global_bluez_manager,
        )


async def get_global_bluez_manager_with_timeout() -> "BlueZManager" | None:
    """Get the properties."""
    if not IS_LINUX:
        return None
    if (
        getattr(get_global_bluez_manager_with_timeout, "_has_dbus_socket", None)
        is False
    ):
        # We are not running on a system with DBus do don't
        # keep trying to call get_global_bluez_manager as it
        # waits for a bit trying to connect to DBus.
        return None

    try:
        async with async_timeout.timeout(DBUS_CONNECT_TIMEOUT):
            return await get_global_bluez_manager()
    except FileNotFoundError as ex:
        setattr(get_global_bluez_manager_with_timeout, "_has_dbus_socket", False)
        _LOGGER.debug(
            "Dbus socket at %s not found, will not try again until next restart: %s",
            ex.filename,
            ex,
        )
    except asyncio.TimeoutError:
        setattr(get_global_bluez_manager_with_timeout, "_has_dbus_socket", False)
        _LOGGER.debug(
            "Timed out trying to connect to DBus; will not try again until next restart"
        )
    except Exception as ex:  # pylint: disable=broad-except
        _LOGGER.debug(
            "get_global_bluez_manager_with_timeout failed: %s", ex, exc_info=True
        )

    return None


def _reset_dbus_socket_cache() -> None:
    """Reset the dbus socket cache."""
    setattr(get_global_bluez_manager_with_timeout, "_has_dbus_socket", None)
