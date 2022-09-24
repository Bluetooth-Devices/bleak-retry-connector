from __future__ import annotations

__version__ = "1.17.3"


import asyncio
import contextlib
import inspect
import logging
import platform
import time
from collections.abc import Callable, Generator
from typing import Any

import async_timeout
from bleak import BleakClient, BleakError
from bleak.backends.device import BLEDevice
from bleak.backends.service import BleakGATTServiceCollection
from bleak.exc import BleakDBusError

DISCONNECT_TIMEOUT = 5

IS_LINUX = CAN_CACHE_SERVICES = platform.system() == "Linux"

if IS_LINUX:
    from .dbus import disconnect_devices

if CAN_CACHE_SERVICES:
    with contextlib.suppress(ImportError):  # pragma: no cover
        from bleak.backends.bluezdbus import defs  # pragma: no cover
        from bleak.backends.bluezdbus.manager import (  # pragma: no cover
            get_global_bluez_manager,
        )

UNREACHABLE_RSSI = -1000


BLEAK_HAS_ALREADY_CONNECTED_SUPPORT = BLEAK_HAS_SERVICE_CACHE_SUPPORT = bool(
    "dangerous_use_bleak_cache" in inspect.signature(BleakClient.connect).parameters
)


# Make sure bleak and dbus-next have time
# to run their cleanup callbacks or the
# retry call will just fail in the same way.
BLEAK_DBUS_BACKOFF_TIME = 0.25
BLEAK_BACKOFF_TIME = 0.1


RSSI_SWITCH_THRESHOLD = 6

__all__ = [
    "establish_connection",
    "close_stale_connections",
    "get_device",
    "BleakClientWithServiceCache",
    "BleakAbortedError",
    "BleakNotFoundError",
    "BleakDisconnectedError",
    "BLEAK_RETRY_EXCEPTIONS",
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
BLEAK_TIMEOUT = 14.25

# Bleak may not always timeout
# since the dbus connection can stall
# so we have an additional timeout to
# be sure we do not block forever
BLEAK_SAFETY_TIMEOUT = 20

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

        try:
            return await super().get_services(
                *args, dangerous_use_bleak_cache=dangerous_use_bleak_cache, **kwargs
            )
        except Exception:  # pylint: disable=broad-except
            # If getting services fails, we must disconnect
            # to avoid a connection leak
            _LOGGER.debug("Disconnecting from device since get_services failed")
            await self.disconnect()
            raise

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


def ble_device_description(device: BLEDevice) -> str:
    """Get the device description."""
    if isinstance(device.details, dict) and "path" in device.details:
        return device.details["path"]
    return device.address


def _get_possible_paths(path: str) -> Generator[str, None, None]:
    """Get the possible paths."""
    # The path is deterministic so we splice up the string
    # /org/bluez/hci2/dev_FA_23_9D_AA_45_46
    for i in range(0, 9):
        yield f"{path[0:14]}{i}{path[15:]}"


async def freshen_ble_device(device: BLEDevice) -> BLEDevice | None:
    """Freshen the device.

    If the device is from BlueZ it may be stale
    because bleak does not send callbacks if only
    the RSSI changes so we may need to find the
    path to the device ourselves.
    """
    if (
        not IS_LINUX
        or not isinstance(device.details, dict)
        or "path" not in device.details
    ):
        return None
    return await get_bluez_device(device.name, device.details["path"], device.rssi)


def address_to_bluez_path(address: str) -> str:
    """Convert an address to a BlueZ path."""
    return f"/org/bluez/hciX/dev_{address.upper().replace(':', '_')}"


async def get_device(address: str) -> BLEDevice | None:
    """Get the device."""
    if not IS_LINUX:
        return None
    return await get_bluez_device(
        address, address_to_bluez_path(address), _log_disappearance=False
    )


async def get_bluez_device(
    name: str, path: str, rssi: int | None = None, _log_disappearance: bool = True
) -> BLEDevice | None:
    """Get a BLEDevice object for a BlueZ DBus path."""
    best_path = device_path = path
    rssi_to_beat = device_rssi = rssi or UNREACHABLE_RSSI

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
            rssi_to_beat = device_rssi = UNREACHABLE_RSSI

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

            rssi = device_props.get("RSSI")
            if rssi_to_beat != UNREACHABLE_RSSI and (
                not rssi
                or rssi - RSSI_SWITCH_THRESHOLD < device_rssi
                or rssi < rssi_to_beat
            ):
                continue
            best_path = path
            rssi_to_beat = rssi or UNREACHABLE_RSSI
            _LOGGER.debug(
                "%s - %s: Found path %s with better RSSI %s",
                name,
                device_path,
                path,
                rssi,
            )

        if best_path == device_path:
            return None

        return ble_device_from_properties(
            best_path, properties[best_path][defs.DEVICE_INTERFACE]
        )
    except Exception as ex:  # pylint: disable=broad-except
        _LOGGER.debug(
            "%s - %s: Freshen failed: %s", name, device_path, ex, exc_info=True
        )

    return None


def ble_device_from_properties(path: str, props: dict[str, Any]) -> BLEDevice:
    """Get a BLEDevice from a dict of properties."""
    return BLEDevice(
        props["Address"],
        props["Alias"],
        {"path": path, "props": props},
        props.get("RSSI", UNREACHABLE_RSSI),
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
        description = ble_device_description(connected_device)
        if only_other_adapters and not ble_device_has_changed(connected_device, device):
            _LOGGER.debug(
                "%s - %s: unexpectedly connected, not disconnecting since only_other_adapters is set",
                connected_device.name,
                description,
            )
        else:
            _LOGGER.debug(
                "%s - %s: unexpectedly connected, disconnecting",
                connected_device.name,
                description,
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
            ble_device_description(device),
            waited,
        )
        if min_wait_time and waited < min_wait_time:
            await asyncio.sleep(min_wait_time - waited)
    except KeyError:
        # Device was removed from bus
        pass
    except Exception:  # pylint: disable=broad-except
        _LOGGER.debug(
            "%s - %s: Failed waiting for disconnect",
            device.name,
            ble_device_description(device),
            exc_info=True,
        )


async def establish_connection(
    client_class: type[BleakClient],
    device: BLEDevice,
    name: str,
    disconnected_callback: Callable[[BleakClient], None] | None = None,
    max_attempts: int = MAX_CONNECT_ATTEMPTS,
    cached_services: BleakGATTServiceCollection | None = None,
    ble_device_callback: Callable[[], BLEDevice] | None = None,
    use_services_cache: bool = False,
    **kwargs: Any,
) -> BleakClient:
    """Establish a connection to the device."""
    timeouts = 0
    connect_errors = 0
    transient_errors = 0
    attempt = 0
    can_use_cached_services = True

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
        if isinstance(exc, BleakError) and any(
            error in str(exc) for error in ABORT_ERRORS
        ):
            raise BleakAbortedError(f"{msg}: {ABORT_ADVICE}") from exc
        if isinstance(exc, BleakError) and any(
            error in str(exc) for error in DEVICE_MISSING_ERRORS
        ):
            raise BleakNotFoundError(f"{msg}: {DEVICE_MISSING_ADVICE}") from exc
        raise BleakConnectionError(msg) from exc

    create_client = True

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
            can_use_cached_services = False

        if not create_client:
            create_client = ble_device_has_changed(original_device, device)

        description = ble_device_description(device)

        _LOGGER.debug(
            "%s - %s: Connecting (attempt: %s, last rssi: %s)",
            name,
            description,
            attempt,
            device.rssi,
        )

        if create_client:
            client = client_class(device, **kwargs)
            if disconnected_callback:
                client.set_disconnected_callback(disconnected_callback)
            if (
                can_use_cached_services
                and cached_services
                and isinstance(client, BleakClientWithServiceCache)
            ):
                client.set_cached_services(cached_services)
            create_client = False

        if IS_LINUX:
            # Bleak 0.17 will handle already connected devices for us, but
            # we still need to disconnect if its unexpectedly connected to another
            # adapter.

            await close_stale_connections(
                device, only_other_adapters=BLEAK_HAS_ALREADY_CONNECTED_SUPPORT
            )

        try:
            async with async_timeout.timeout(BLEAK_SAFETY_TIMEOUT):
                await client.connect(
                    timeout=BLEAK_TIMEOUT,
                    dangerous_use_bleak_cache=use_services_cache
                    or bool(cached_services),
                )
        except asyncio.TimeoutError as exc:
            timeouts += 1
            _LOGGER.debug(
                "%s - %s: Timed out trying to connect (attempt: %s, last rssi: %s)",
                name,
                description,
                attempt,
                device.rssi,
            )
            await wait_for_disconnect(device, BLEAK_DBUS_BACKOFF_TIME)
            _raise_if_needed(name, description, exc)
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
                "%s - %s: Failed to connect: %s (attempt: %s, last rssi: %s)",
                name,
                description,
                str(exc),
                attempt,
                device.rssi,
            )
            _raise_if_needed(name, description, exc)
        except EOFError as exc:
            transient_errors += 1
            _LOGGER.debug(
                "%s - %s: Failed to connect: %s, backing off: %s (attempt: %s, last rssi: %s)",
                name,
                description,
                str(exc),
                BLEAK_DBUS_BACKOFF_TIME,
                attempt,
                device.rssi,
            )
            await wait_for_disconnect(device, BLEAK_DBUS_BACKOFF_TIME)
            _raise_if_needed(name, description, exc)
        except BLEAK_EXCEPTIONS as exc:
            bleak_error = str(exc)
            if any(error in bleak_error for error in TRANSIENT_ERRORS):
                transient_errors += 1
            else:
                connect_errors += 1
            if isinstance(exc, BleakDBusError):
                _LOGGER.debug(
                    "%s - %s: Failed to connect: %s, backing off: %s (attempt: %s, last rssi: %s)",
                    name,
                    description,
                    bleak_error,
                    BLEAK_DBUS_BACKOFF_TIME,
                    attempt,
                    device.rssi,
                )
                await wait_for_disconnect(device, BLEAK_DBUS_BACKOFF_TIME)
            else:
                _LOGGER.debug(
                    "%s - %s: Failed to connect: %s, backing off: %s (attempt: %s, last rssi: %s)",
                    name,
                    description,
                    bleak_error,
                    BLEAK_BACKOFF_TIME,
                    attempt,
                    device.rssi,
                )
                await wait_for_disconnect(device, BLEAK_BACKOFF_TIME)
            _raise_if_needed(name, description, exc)
        else:
            _LOGGER.debug(
                "%s - %s: Connected (attempt: %s, last rssi: %s)",
                name,
                description,
                attempt,
                device.rssi,
            )
            return client
        # Ensure the disconnect callback
        # has a chance to run before we try to reconnect
        await asyncio.sleep(0)

    raise RuntimeError("This should never happen")
