from __future__ import annotations

from typing import cast

__version__ = "2.8.9"


import asyncio
import contextlib
import logging
import platform
import time
from collections.abc import Callable, Generator
from typing import Any, TypeVar

import async_timeout
from bleak import BleakClient
from bleak.backends.device import BLEDevice
from bleak.backends.service import BleakGATTServiceCollection
from bleak.exc import BleakDBusError, BleakDeviceNotFoundError, BleakError

DISCONNECT_TIMEOUT = 5

IS_LINUX = platform.system() == "Linux"
DEFAULT_ATTEMPTS = 2

if IS_LINUX:
    from .dbus import disconnect_devices

    with contextlib.suppress(ImportError):  # pragma: no cover
        from bleak.backends.bluezdbus import defs  # pragma: no cover
        from bleak.backends.bluezdbus.manager import (  # pragma: no cover
            get_global_bluez_manager,
        )

NO_RSSI_VALUE = -127


# Make sure bleak and dbus-fast have time
# to run their cleanup callbacks or the
# retry call will just fail in the same way.
BLEAK_TRANSIENT_BACKOFF_TIME = 0.25
BLEAK_TRANSIENT_MEDIUM_BACKOFF_TIME = 0.90
BLEAK_TRANSIENT_LONG_BACKOFF_TIME = 1.25
BLEAK_DBUS_BACKOFF_TIME = 0.25
BLEAK_OUT_OF_SLOTS_BACKOFF_TIME = 4.00
BLEAK_BACKOFF_TIME = 0.1
# Expected disconnect or ran out of slots
# after checking, don't backoff since we
# want to retry immediately.
BLEAK_DISCONNECTED_BACKOFF_TIME = 0.0

RSSI_SWITCH_THRESHOLD = 5

__all__ = [
    "ble_device_description",
    "establish_connection",
    "close_stale_connections",
    "get_device",
    "get_device_by_adapter",
    "retry_bluetooth_connection_error",
    "BleakClientWithServiceCache",
    "BleakAbortedError",
    "BleakNotFoundError",
    "BLEAK_RETRY_EXCEPTIONS",
    "RSSI_SWITCH_THRESHOLD",
    "NO_RSSI_VALUE",
]


BLEAK_EXCEPTIONS = (AttributeError, BleakError)
BLEAK_RETRY_EXCEPTIONS = (
    *BLEAK_EXCEPTIONS,
    EOFError,
    BrokenPipeError,
    asyncio.TimeoutError,
)

_LOGGER = logging.getLogger(__name__)

MAX_TRANSIENT_ERRORS = 9

# Shorter time outs and more attempts
# seems to be better for dbus, and corebluetooth
# is happy either way. Ideally we want everything
# to finish in < 60s or declare we cannot connect

MAX_CONNECT_ATTEMPTS = 4
BLEAK_TIMEOUT = 20.0

# Bleak may not always timeout
# since the dbus connection can stall
# so we have an additional timeout to
# be sure we do not block forever
# This is likely fixed in https://github.com/hbldh/bleak/pull/1092
#
# This also accounts for the time it
# takes for the esp32s to disconnect
#
BLEAK_SAFETY_TIMEOUT = 30.0

TRANSIENT_ERRORS_LONG_BACKOFF = {
    "ESP_GATT_ERROR",
}

TRANSIENT_ERRORS_MEDIUM_BACKOFF = {
    "ESP_GATT_CONN_TIMEOUT",
    "ESP_GATT_CONN_FAIL_ESTABLISH",
}

DEVICE_MISSING_ERRORS = {"org.freedesktop.DBus.Error.UnknownObject"}

OUT_OF_SLOTS_ERRORS = {"available connection", "connection slot"}

TRANSIENT_ERRORS = {
    "le-connection-abort-by-local",
    "br-connection-canceled",
    "ESP_GATT_CONN_FAIL_ESTABLISH",
    "ESP_GATT_CONN_TERMINATE_PEER_USER",
    "ESP_GATT_CONN_TERMINATE_LOCAL_HOST",
    "ESP_GATT_CONN_CONN_CANCEL",
} | OUT_OF_SLOTS_ERRORS

# Currently the same as transient error
ABORT_ERRORS = (
    TRANSIENT_ERRORS | TRANSIENT_ERRORS_MEDIUM_BACKOFF | TRANSIENT_ERRORS_LONG_BACKOFF
)


ABORT_ADVICE = (
    "Interference/range; "
    "External Bluetooth adapter w/extension may help; "
    "Extension cables reduce USB 3 port interference"
)

DEVICE_MISSING_ADVICE = (
    "The device disappeared; " "Try restarting the scanner or moving the device closer"
)

OUT_OF_SLOTS_ADVICE = (
    "The proxy/adapter is out of connection slots; "
    "Add additional proxies near this device"
)

NORMAL_DISCONNECT = "Disconnected"


class BleakNotFoundError(BleakError):
    """The device was not found."""


class BleakConnectionError(BleakError):
    """The device was not found."""


class BleakAbortedError(BleakError):
    """The connection was aborted."""


class BleakOutOfConnectionSlotsError(BleakError):
    """The proxy/adapter is out of connection slots."""


class BleakClientWithServiceCache(BleakClient):
    """A BleakClient that implements service caching."""

    def set_cached_services(self, services: BleakGATTServiceCollection | None) -> None:
        """Set the cached services.

        No longer used since bleak 0.17+ has service caching built-in.

        This was only kept for backwards compatibility.
        """

    async def clear_cache(self) -> None:
        """Clear the cached services."""


def ble_device_has_changed(original: BLEDevice, new: BLEDevice) -> bool:
    """Check if the device has changed."""
    return bool(
        original.address != new.address
        or (
            isinstance(original.details, dict)
            and isinstance(new.details, dict)
            and "path" in original.details
            and "path" in new.details
            and original.details["path"] != new.details["path"]
        )
    )


async def clear_cache(address: str) -> bool:
    """Clear the cache for a device."""
    if not IS_LINUX or not await get_device(address):
        return False
    with contextlib.suppress(Exception):
        manager = await get_global_bluez_manager()
        manager._services_cache.pop(
            address.upper(), None
        )  # pylint: disable=protected-access
        return True
    return False


def ble_device_description(device: BLEDevice) -> str:
    """Get the device description."""
    details = device.details
    address = device.address
    name = device.name
    if name != address:
        base_name = f"{address} - {name}"
    else:
        base_name = address
    if isinstance(details, dict):
        if path := details.get("path"):
            # /org/bluez/hci2
            return f"{base_name} -> {path[0:15]}"
        if source := details.get("source"):
            return f"{base_name} -> {source}"
    return base_name


def _get_possible_paths(path: str) -> Generator[str, None, None]:
    """Get the possible paths."""
    # The path is deterministic so we splice up the string
    # /org/bluez/hci2/dev_FA_23_9D_AA_45_46
    for i in range(0, 9):
        yield f"{path[0:14]}{i}{path[15:]}"


async def freshen_ble_device(device: BLEDevice) -> BLEDevice | None:
    """Freshen the device.

    There may be a better path to the device on another adapter
    that was seen after the code that provided the BLEDevice to
    the establish_connection function was run.
    """
    if (
        not IS_LINUX
        or not isinstance(device.details, dict)
        or "path" not in device.details
    ):
        return None
    return await get_bluez_device(
        device.name or device.address, device.details["path"], _get_rssi(device)
    )


def address_to_bluez_path(address: str, adapter: str | None = None) -> str:
    """Convert an address to a BlueZ path."""
    return f"/org/bluez/{adapter or 'hciX'}/dev_{address.upper().replace(':', '_')}"


def calculate_backoff_time(exc: Exception) -> float:
    """Calculate the backoff time based on the exception."""

    if isinstance(
        exc, (BleakDBusError, EOFError, asyncio.TimeoutError, BrokenPipeError)
    ):
        return BLEAK_DBUS_BACKOFF_TIME
    # If the adapter runs out of slots can get a BleakDeviceNotFoundError
    # since the device is no longer visible on the adapter. Almost none of
    # the adapters document how many connection slots they have so we cannot
    # know if we are out of slots or not. We can only guess based on the
    # error message and backoff.
    if isinstance(exc, BleakDeviceNotFoundError):
        return BLEAK_OUT_OF_SLOTS_BACKOFF_TIME
    if isinstance(exc, BleakError):
        bleak_error = str(exc)
        if any(error in bleak_error for error in OUT_OF_SLOTS_ERRORS):
            return BLEAK_OUT_OF_SLOTS_BACKOFF_TIME
        if any(error in bleak_error for error in TRANSIENT_ERRORS_MEDIUM_BACKOFF):
            return BLEAK_TRANSIENT_MEDIUM_BACKOFF_TIME
        if any(error in bleak_error for error in TRANSIENT_ERRORS_LONG_BACKOFF):
            return BLEAK_TRANSIENT_LONG_BACKOFF_TIME
        if any(error in bleak_error for error in TRANSIENT_ERRORS):
            return BLEAK_TRANSIENT_BACKOFF_TIME
        if NORMAL_DISCONNECT in bleak_error:
            return BLEAK_DISCONNECTED_BACKOFF_TIME
    return BLEAK_BACKOFF_TIME


async def get_device(address: str) -> BLEDevice | None:
    """Get the device."""
    if not IS_LINUX:
        return None
    return await get_bluez_device(
        address, address_to_bluez_path(address), _log_disappearance=False
    )


async def get_device_by_adapter(address: str, adapter: str) -> BLEDevice | None:
    """Get the device by adapter and address."""
    if not IS_LINUX:
        return None
    with contextlib.suppress(Exception):
        manager = await get_global_bluez_manager()
        device_path = address_to_bluez_path(address, adapter)
        properties = manager._properties
        if device_path in properties and (
            device_props := properties[device_path].get(defs.DEVICE_INTERFACE)
        ):
            return ble_device_from_properties(device_path, device_props)
    return None


def _reset_dbus_socket_cache() -> None:
    """Reset the dbus socket cache."""
    setattr(get_bluez_device, "_has_dbus_socket", None)


async def get_bluez_device(
    name: str, path: str, rssi: int | None = None, _log_disappearance: bool = True
) -> BLEDevice | None:
    """Get a BLEDevice object for a BlueZ DBus path."""
    if getattr(get_bluez_device, "_has_dbus_socket", None) is False:
        # We are not running on a system with DBus do don't
        # keep trying to call get_global_bluez_manager as it
        # waits for a bit trying to connect to DBus.
        return None

    best_path = device_path = path
    rssi_to_beat: int = rssi or NO_RSSI_VALUE

    try:
        manager = await get_global_bluez_manager()
        properties = manager._properties
        if (
            device_path not in properties
            or defs.DEVICE_INTERFACE not in properties[device_path]
        ):
            # device has disappeared so take
            # anything over the current path
            if _log_disappearance:
                _LOGGER.debug("%s - %s: Device has disappeared", name, device_path)
            rssi_to_beat = NO_RSSI_VALUE

        for path in _get_possible_paths(device_path):
            if path not in properties or not (
                device_props := properties[path].get(defs.DEVICE_INTERFACE)
            ):
                continue

            if device_props.get("Connected"):
                # device is connected so take it
                _LOGGER.debug("%s - %s: Device is already connected", name, path)
                if path == device_path:
                    # device is connected to the path we were given
                    # so we can just return None so it will be used
                    return None
                return ble_device_from_properties(path, device_props)

            if path == device_path:
                # Device is not connected and is the original path
                # so no need to check it since returning None will
                # cause the device to be used anyways.
                continue

            alternate_device_rssi: int = device_props.get("RSSI") or NO_RSSI_VALUE
            if (
                rssi_to_beat != NO_RSSI_VALUE
                and alternate_device_rssi - RSSI_SWITCH_THRESHOLD < rssi_to_beat
            ):
                continue
            best_path = path
            _LOGGER.debug(
                "%s - %s: Found path %s with better RSSI %s > %s",
                name,
                device_path,
                path,
                alternate_device_rssi,
                rssi_to_beat,
            )
            rssi_to_beat = alternate_device_rssi

        if best_path == device_path:
            return None

        return ble_device_from_properties(
            best_path, properties[best_path][defs.DEVICE_INTERFACE]
        )
    except FileNotFoundError as ex:
        setattr(get_bluez_device, "_has_dbus_socket", False)
        _LOGGER.debug(
            "Dbus socket at %s not found, will not try again until next restart: %s",
            ex.filename,
            ex,
        )
    except Exception as ex:  # pylint: disable=broad-except
        _LOGGER.debug(
            "%s - %s: get_bluez_device failed: %s", name, device_path, ex, exc_info=True
        )

    return None


def ble_device_from_properties(path: str, props: dict[str, Any]) -> BLEDevice:
    """Get a BLEDevice from a dict of properties."""
    return BLEDevice(
        props["Address"],
        props["Alias"],
        {"path": path, "props": props},
        props.get("RSSI") or NO_RSSI_VALUE,
        uuids=props.get("UUIDs", []),
        manufacturer_data={
            k: bytes(v) for k, v in props.get("ManufacturerData", {}).items()
        },
    )


async def get_connected_devices(device: BLEDevice) -> list[BLEDevice]:
    """Check if the device is connected."""
    connected: list[BLEDevice] = []

    if not isinstance(device.details, dict) or "path" not in device.details:
        return connected
    try:
        manager = await get_global_bluez_manager()
        properties = manager._properties
        device_path = device.details["path"]
        for path in _get_possible_paths(device_path):
            if path not in properties or defs.DEVICE_INTERFACE not in properties[path]:
                continue
            props = properties[path][defs.DEVICE_INTERFACE]
            if props.get("Connected"):
                connected.append(ble_device_from_properties(path, props))
        return connected
    except Exception:  # pylint: disable=broad-except
        return connected


async def _disconnect_devices(devices: list[BLEDevice]) -> None:
    """Disconnect the devices."""
    await disconnect_devices(devices)


async def close_stale_connections(
    device: BLEDevice, only_other_adapters: bool = False
) -> None:
    """Close stale connections."""
    if not IS_LINUX or not (devices := await get_connected_devices(device)):
        return
    to_disconnect: list[BLEDevice] = []
    for connected_device in devices:
        if only_other_adapters and not ble_device_has_changed(connected_device, device):
            _LOGGER.debug(
                "%s - %s: unexpectedly connected, not disconnecting since only_other_adapters is set",
                connected_device.name,
                connected_device.address,
            )
        else:
            _LOGGER.debug(
                "%s - %s: unexpectedly connected, disconnecting",
                connected_device.name,
                connected_device.address,
            )
            to_disconnect.append(connected_device)

    if not to_disconnect:
        return
    await _disconnect_devices(to_disconnect)


async def wait_for_disconnect(device: BLEDevice, min_wait_time: float) -> None:
    """Wait for the device to disconnect.

    After a connection failure, the device may not have
    had time to disconnect so we wait for it to do so.

    If we do not wait, we may end up connecting to the
    same device again before it has had time to disconnect.
    """
    if (
        not IS_LINUX
        or not isinstance(device.details, dict)
        or "path" not in device.details
    ):
        await asyncio.sleep(min_wait_time)
        return
    start = time.monotonic() if min_wait_time else 0
    try:
        manager = await get_global_bluez_manager()
        async with async_timeout.timeout(DISCONNECT_TIMEOUT):
            await manager._wait_condition(device.details["path"], "Connected", False)
        end = time.monotonic() if min_wait_time else 0
        waited = end - start
        _LOGGER.debug(
            "%s - %s: Waited %s seconds to disconnect",
            device.name,
            device.address,
            waited,
        )
        if min_wait_time and waited < min_wait_time:
            await asyncio.sleep(min_wait_time - waited)
    except KeyError as ex:
        # Device was removed from bus
        #
        # In testing it was found that most of the CSR adapters
        # only support 5 slots and the broadcom only support 7 slots.
        #
        # When they run out of slots the device they are trying to
        # connect to disappears from the bus so we must backoff
        _LOGGER.debug(
            "%s - %s: Device was removed from bus, waiting %s for it to re-appear: %s",
            device.name,
            device.address,
            min_wait_time,
            ex,
        )
        await asyncio.sleep(min_wait_time)
    except Exception:  # pylint: disable=broad-except
        _LOGGER.debug(
            "%s - %s: Failed waiting for disconnect",
            device.name,
            device.address,
            exc_info=True,
        )


def _get_rssi(device: BLEDevice) -> int:
    """Get the RSSI for the device."""
    if not isinstance(device.details, dict) or "props" not in device.details:
        return device.rssi
    return device.details["props"].get("RSSI") or device.rssi or NO_RSSI_VALUE


async def establish_connection(
    client_class: type[BleakClient],
    device: BLEDevice,
    name: str,
    disconnected_callback: Callable[[BleakClient], None] | None = None,
    max_attempts: int = MAX_CONNECT_ATTEMPTS,
    cached_services: BleakGATTServiceCollection | None = None,
    ble_device_callback: Callable[[], BLEDevice] | None = None,
    use_services_cache: bool = True,
    **kwargs: Any,
) -> BleakClient:
    """Establish a connection to the device."""
    timeouts = 0
    connect_errors = 0
    transient_errors = 0
    attempt = 0

    def _raise_if_needed(name: str, description: str, exc: Exception) -> None:
        """Raise if we reach the max attempts."""
        if (
            timeouts + connect_errors < max_attempts
            and transient_errors < MAX_TRANSIENT_ERRORS
        ):
            return
        msg = f"{name} - {description}: Failed to connect: {exc}"
        # Sure would be nice if bleak gave us typed exceptions
        if isinstance(exc, asyncio.TimeoutError) or "not found" in str(exc):
            raise BleakNotFoundError(msg) from exc
        if isinstance(exc, BleakError):
            if any(error in str(exc) for error in OUT_OF_SLOTS_ERRORS):
                raise BleakOutOfConnectionSlotsError(
                    f"{msg}: {OUT_OF_SLOTS_ADVICE}"
                ) from exc
            if any(error in str(exc) for error in ABORT_ERRORS):
                raise BleakAbortedError(f"{msg}: {ABORT_ADVICE}") from exc
            if any(error in str(exc) for error in DEVICE_MISSING_ERRORS):
                raise BleakNotFoundError(f"{msg}: {DEVICE_MISSING_ADVICE}") from exc
        raise BleakConnectionError(msg) from exc

    create_client = True
    debug_enabled = _LOGGER.isEnabledFor(logging.DEBUG)
    rssi: int | None = None

    while True:
        attempt += 1
        original_device = device

        # Its possible the BLEDevice can change between
        # between connection attempts so we do not want
        # to keep trying to connect to the old one if it has changed.
        if ble_device_callback is not None:
            device = ble_device_callback()

        if fresh_device := await freshen_ble_device(device):
            device = fresh_device

        if not create_client:
            create_client = ble_device_has_changed(original_device, device)

        if debug_enabled:
            _LOGGER.debug(
                "%s - %s: Connection attempt: %s",
                name,
                device.address,
                attempt,
            )

        if create_client:
            client = client_class(
                device, disconnected_callback=disconnected_callback, **kwargs
            )
            create_client = False

        if IS_LINUX:
            # Bleak 0.17 will handle already connected devices for us, but
            # we still need to disconnect if its unexpectedly connected to another
            # adapter.

            await close_stale_connections(device, only_other_adapters=True)

        try:
            async with async_timeout.timeout(BLEAK_SAFETY_TIMEOUT):
                await client.connect(
                    timeout=BLEAK_TIMEOUT,
                    dangerous_use_bleak_cache=use_services_cache
                    or bool(cached_services),
                )
        except asyncio.TimeoutError as exc:
            timeouts += 1
            if debug_enabled:
                _LOGGER.debug(
                    "%s - %s: Timed out trying to connect (attempt: %s, last rssi: %s)",
                    name,
                    device.address,
                    attempt,
                    rssi,
                )
            backoff_time = calculate_backoff_time(exc)
            await wait_for_disconnect(device, backoff_time)
            _raise_if_needed(name, device.address, exc)
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
            if debug_enabled:
                _LOGGER.debug(
                    "%s - %s: Failed to connect: %s (attempt: %s, last rssi: %s)",
                    name,
                    device.address,
                    str(exc),
                    attempt,
                    rssi,
                )
            _raise_if_needed(name, device.address, exc)
        except EOFError as exc:
            transient_errors += 1
            backoff_time = calculate_backoff_time(exc)
            if debug_enabled:
                _LOGGER.debug(
                    "%s - %s: Failed to connect: %s, backing off: %s (attempt: %s, last rssi: %s)",
                    name,
                    device.address,
                    str(exc),
                    backoff_time,
                    attempt,
                    rssi,
                )
            await wait_for_disconnect(device, backoff_time)
            _raise_if_needed(name, device.address, exc)
        except BLEAK_EXCEPTIONS as exc:
            bleak_error = str(exc)
            # BleakDeviceNotFoundError can mean that the adapter has run out of
            # connection slots.
            if isinstance(exc, BleakDeviceNotFoundError) or any(
                error in bleak_error for error in TRANSIENT_ERRORS
            ):
                transient_errors += 1
            else:
                connect_errors += 1
            backoff_time = calculate_backoff_time(exc)
            if debug_enabled:
                _LOGGER.debug(
                    "%s - %s: Failed to connect: %s, backing off: %s (attempt: %s, last rssi: %s)",
                    name,
                    device.address,
                    bleak_error,
                    backoff_time,
                    attempt,
                    rssi,
                )
            await wait_for_disconnect(device, backoff_time)
            _raise_if_needed(name, device.address, exc)
        else:
            return client
        # Ensure the disconnect callback
        # has a chance to run before we try to reconnect
        await asyncio.sleep(0)

    raise RuntimeError("This should never happen")


WrapFuncType = TypeVar("WrapFuncType", bound=Callable[..., Any])


def retry_bluetooth_connection_error(attempts: int = DEFAULT_ATTEMPTS) -> WrapFuncType:
    """Define a wrapper to retry on bluetooth connection error."""

    def _decorator_retry_bluetooth_connection_error(func: WrapFuncType) -> WrapFuncType:
        """Define a wrapper to retry on bleak error.

        The accessory is allowed to disconnect us any time so
        we need to retry the operation.
        """

        async def _async_wrap_bluetooth_connection_error_retry(
            *args: Any, **kwargs: Any
        ) -> Any:
            for attempt in range(attempts):
                try:
                    return await func(*args, **kwargs)
                except BLEAK_EXCEPTIONS as ex:
                    backoff_time = calculate_backoff_time(ex)
                    if attempt == attempts - 1:
                        raise
                    _LOGGER.debug(
                        "Bleak error calling %s, backing off: %s, retrying...",
                        func,
                        backoff_time,
                        exc_info=True,
                    )
                    await asyncio.sleep(backoff_time)

        return cast(WrapFuncType, _async_wrap_bluetooth_connection_error_retry)

    return cast(WrapFuncType, _decorator_retry_bluetooth_connection_error)
