from __future__ import annotations

__version__ = "1.2.0"


import asyncio
import logging
from collections.abc import Callable
from typing import Any

import async_timeout
from bleak import BleakClient, BleakError
from bleak.backends.device import BLEDevice

__all__ = ["establish_connection", "BleakNotFoundError", "BleakDisconnectedError"]

BLEAK_EXCEPTIONS = (AttributeError, BleakError)

_LOGGER = logging.getLogger(__name__)

MAX_TRANSIENT_ERRORS = 9

# Shorter time outs and more attempts
# seems to be better for dbus, and corebluetooth
# is happy either way. Ideally we want everything
# to finish in < 60s or declare we cannot connect

MAX_CONNECT_ATTEMPTS = 5
BLEAK_TIMEOUT = 12

# Bleak may not always timeout
# since the dbus connection can stall
# so we have an additional timeout to
# be sure we do not block forever
BLEAK_SAFETY_TIMEOUT = 13

# These errors are transient with dbus, and we should retry
TRANSIENT_ERRORS = {"le-connection-abort-by-local", "br-connection-canceled"}


class BleakNotFoundError(BleakError):
    """The device was not found."""


class BleakConnectionError(BleakError):
    """The device was not found."""


async def establish_connection(
    client_class: type[BleakClient],
    device: BLEDevice,
    name: str,
    disconnected_callback: Callable[[BleakClient], None] | None = None,
    max_attempts: int = MAX_CONNECT_ATTEMPTS,
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
        raise BleakConnectionError(msg) from exc

    while True:
        attempt += 1
        _LOGGER.debug("%s: Connecting (attempt: %s)", name, attempt)
        try:
            async with async_timeout.timeout(BLEAK_SAFETY_TIMEOUT):
                await client.connect(timeout=BLEAK_TIMEOUT)
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

    raise RuntimeError("This should never happen")
