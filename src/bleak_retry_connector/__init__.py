from __future__ import annotations

__version__ = "0.1.0"


import asyncio
import logging
from collections.abc import Callable

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
BLEAK_TIMEOUT = 10

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
) -> BleakClient:
    """Establish a connection to the accessory."""
    timeouts = 0
    connect_errors = 0
    transient_errors = 0
    attempt = 0

    client = client_class(device)
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
            await client.connect(timeout=BLEAK_TIMEOUT)
        except asyncio.TimeoutError as exc:
            timeouts += 1
            _LOGGER.debug(
                "%s: Timed out trying to connect (attempt: %s)", name, attempt
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
