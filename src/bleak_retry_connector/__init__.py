from __future__ import annotations

__version__ = "1.7.2"


import asyncio
import contextlib
import inspect
import logging
import platform
from collections.abc import Callable
from typing import Any

import async_timeout
from bleak import BleakClient, BleakError
from bleak.backends.device import BLEDevice
from bleak.backends.service import BleakGATTServiceCollection

CAN_CACHE_SERVICES = platform.system() == "Linux"

if CAN_CACHE_SERVICES:
    with contextlib.suppress(ImportError):  # pragma: no cover
        from bleak.backends.bluezdbus import defs  # pragma: no cover
        from bleak.backends.bluezdbus.manager import (  # pragma: no cover
            get_global_bluez_manager,
        )

BLEAK_HAS_SERVICE_CACHE_SUPPORT = (
    "dangerous_use_bleak_cache" in inspect.signature(BleakClient.connect).parameters
)

__all__ = [
    "establish_connection",
    "BleakClientWithServiceCache",
    "BleakAbortedError",
    "BleakNotFoundError",
    "BleakDisconnectedError",
]

BLEAK_EXCEPTIONS = (AttributeError, BleakError)

_LOGGER = logging.getLogger(__name__)

MAX_TRANSIENT_ERRORS = 9

# Shorter time outs and more attempts
# seems to be better for dbus, and corebluetooth
# is happy either way. Ideally we want everything
# to finish in < 60s or declare we cannot connect

MAX_CONNECT_ATTEMPTS = 4
BLEAK_TIMEOUT = 14.25

# Bleak may not always timeout
# since the dbus connection can stall
# so we have an additional timeout to
# be sure we do not block forever
BLEAK_SAFETY_TIMEOUT = 14.75

# These errors are transient with dbus, and we should retry
TRANSIENT_ERRORS = {"le-connection-abort-by-local", "br-connection-canceled"}

DEVICE_MISSING_ERRORS = {"org.freedesktop.DBus.Error.UnknownObject"}

# Currently the same as transient error
ABORT_ERRORS = TRANSIENT_ERRORS

ABORT_ADVICE = (
    "Interference/range; "
    "External Bluetooth adapter w/extension may help; "
    "Extension cables reduce USB 3 port interference"
)

DEVICE_MISSING_ADVICE = (
    "The device disappeared; " "Try restarting the scanner or moving the device closer"
)


class BleakNotFoundError(BleakError):
    """The device was not found."""


class BleakConnectionError(BleakError):
    """The device was not found."""


class BleakAbortedError(BleakError):
    """The connection was aborted."""


class BleakClientWithServiceCache(BleakClient):
    """A BleakClient that implements service caching."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialize the BleakClientWithServiceCache."""
        super().__init__(*args, **kwargs)
        self._cached_services: BleakGATTServiceCollection | None = None

    @property
    def _has_service_cache(self) -> bool:
        """Check if we can cache services and there is a cache."""
        return (
            not BLEAK_HAS_SERVICE_CACHE_SUPPORT
            and CAN_CACHE_SERVICES
            and self._cached_services is not None
        )

    async def connect(
        self, *args: Any, dangerous_use_bleak_cache: bool = False, **kwargs: Any
    ) -> bool:
        """Connect to the specified GATT server.

        Returns:
            Boolean representing connection status.

        """
        if self._has_service_cache and await self._services_vanished():
            _LOGGER.debug("Clear cached services since they have vanished")
            self._cached_services = None

        connected = await super().connect(
            *args, dangerous_use_bleak_cache=dangerous_use_bleak_cache, **kwargs
        )

        if (
            connected
            and not dangerous_use_bleak_cache
            and not BLEAK_HAS_SERVICE_CACHE_SUPPORT
        ):
            self.set_cached_services(self.services)

        return connected

    async def get_services(
        self, *args: Any, dangerous_use_bleak_cache: bool = False, **kwargs: Any
    ) -> BleakGATTServiceCollection:
        """Get the services."""
        if self._has_service_cache:
            _LOGGER.debug("Cached services found: %s", self._cached_services)
            self.services = self._cached_services
            self._services_resolved = True
            return self._cached_services
        return await super().get_services(
            *args, dangerous_use_bleak_cache=dangerous_use_bleak_cache, **kwargs
        )

    async def _services_vanished(self) -> bool:
        """Check if the services have vanished."""
        with contextlib.suppress(Exception):
            device_path = self._device_path
            manager = await get_global_bluez_manager()
            for service_path, service_ifaces in manager._properties.items():
                if (
                    service_path.startswith(device_path)
                    and defs.GATT_SERVICE_INTERFACE in service_ifaces
                ):
                    return False
        return True

    def set_cached_services(self, services: BleakGATTServiceCollection | None) -> None:
        """Set the cached services."""
        self._cached_services = services


def ble_device_has_changed(original: BLEDevice, new: BLEDevice) -> bool:
    """Check if the device has changed."""
    if original.address != new.address:
        return True
    if (
        isinstance(original.details, dict)
        and "path" in original.details
        and original.details["path"] != new.details["path"]
    ):
        return True
    return False


async def establish_connection(
    client_class: type[BleakClient],
    device: BLEDevice,
    name: str,
    disconnected_callback: Callable[[BleakClient], None] | None = None,
    max_attempts: int = MAX_CONNECT_ATTEMPTS,
    cached_services: BleakGATTServiceCollection | None = None,
    **kwargs: Any,
) -> BleakClient:
    """Establish a connection to the accessory."""
    timeouts = 0
    connect_errors = 0
    transient_errors = 0
    attempt = 0

    client = client_class(device, **kwargs)
    if disconnected_callback:
        client.set_disconnected_callback(disconnected_callback)

    if cached_services and isinstance(client, BleakClientWithServiceCache):
        client.set_cached_services(cached_services)

    def _raise_if_needed(name: str, exc: Exception) -> None:
        """Raise if we reach the max attempts."""
        if (
            timeouts + connect_errors < max_attempts
            and transient_errors < MAX_TRANSIENT_ERRORS
        ):
            return
        msg = f"{name}: Failed to connect: {exc}"
        # Sure would be nice if bleak gave us typed exceptions
        if isinstance(exc, asyncio.TimeoutError) or "not found" in str(exc):
            raise BleakNotFoundError(msg) from exc
        if isinstance(exc, BleakError) and any(
            error in str(exc) for error in ABORT_ERRORS
        ):
            raise BleakAbortedError(f"{msg}: {ABORT_ADVICE}") from exc
        if isinstance(exc, BleakError) and any(
            error in str(exc) for error in DEVICE_MISSING_ERRORS
        ):
            raise BleakNotFoundError(f"{msg}: {DEVICE_MISSING_ADVICE}") from exc
        raise BleakConnectionError(msg) from exc

    while True:
        attempt += 1
        _LOGGER.debug("%s: Connecting (attempt: %s)", name, attempt)
        try:
            async with async_timeout.timeout(BLEAK_SAFETY_TIMEOUT):
                await client.connect(
                    timeout=BLEAK_TIMEOUT,
                    dangerous_use_bleak_cache=bool(cached_services),
                )
        except asyncio.TimeoutError as exc:
            timeouts += 1
            _LOGGER.debug(
                "%s: Timed out trying to connect (attempt: %s)", name, attempt
            )
            _raise_if_needed(name, exc)
        except BrokenPipeError as exc:
            # BrokenPipeError is raised by dbus-next when the device disconnects
            #
            # bleak.exc.BleakDBusError: [org.bluez.Error] le-connection-abort-by-local
            # During handling of the above exception, another exception occurred:
            # Traceback (most recent call last):
            # File "bleak/backends/bluezdbus/client.py", line 177, in connect
            #   reply = await self._bus.call(
            # File "dbus_next/aio/message_bus.py", line 63, in write_callback
            #   self.offset += self.sock.send(self.buf[self.offset:])
            # BrokenPipeError: [Errno 32] Broken pipe
            transient_errors += 1
            _LOGGER.debug(
                "%s: Failed to connect: %s (attempt: %s)", name, str(exc), attempt
            )
            _raise_if_needed(name, exc)
        except BLEAK_EXCEPTIONS as exc:
            bleak_error = str(exc)
            if any(error in bleak_error for error in TRANSIENT_ERRORS):
                transient_errors += 1
            else:
                connect_errors += 1
            _LOGGER.debug(
                "%s: Failed to connect: %s (attempt: %s)", name, str(exc), attempt
            )
            _raise_if_needed(name, exc)
        else:
            _LOGGER.debug("%s: Connected (attempt: %s)", name, attempt)
            return client
        # Ensure the disconnect callback
        # has a chance to run before we try to reconnect
        await asyncio.sleep(0)

    raise RuntimeError("This should never happen")
