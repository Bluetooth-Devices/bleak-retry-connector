from __future__ import annotations

import asyncio
import contextlib
import logging
import time
from collections.abc import Generator
from typing import Any

import async_timeout
from bleak.backends.device import BLEDevice

from .const import IS_LINUX, NO_RSSI_VALUE, RSSI_SWITCH_THRESHOLD

DISCONNECT_TIMEOUT = 5
DBUS_CONNECT_TIMEOUT = 8.5

_LOGGER = logging.getLogger(__name__)


DEFAULT_ATTEMPTS = 2


if IS_LINUX:
    with contextlib.suppress(ImportError):  # pragma: no cover
        from bleak.backends.bluezdbus import defs  # pragma: no cover
        from bleak.backends.bluezdbus.manager import (  # pragma: no cover
            BlueZManager,
            DeviceWatcher,
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


def device_source(device: BLEDevice) -> str | None:
    """Return the device source."""
    return _device_details_value_or_none(device, "source")


def _device_details_value_or_none(device: BLEDevice, key: str) -> Any | None:
    """Return a value from device details or None."""
    details = device.details
    if not isinstance(details, dict) or key not in details:
        return None
    key_value: str = device.details[key]
    return key_value


def _reset_dbus_socket_cache() -> None:
    """Reset the dbus socket cache."""
    setattr(get_global_bluez_manager_with_timeout, "_has_dbus_socket", None)


def adapter_from_path(path: str) -> str:
    """Get the adapter from a ble device path."""
    return path.split("/")[3]


def path_from_ble_device(device: BLEDevice) -> str | None:
    """Get the adapter from a ble device."""
    return _device_details_value_or_none(device, "path")


def _on_characteristic_value_changed(*args: Any, **kwargs: Any) -> None:
    """Dummy callback for registering characteristic value changed."""


class BleakSlotManager:

    """A class to manage the connection slots."""

    def __init__(self) -> None:
        """Initialize the class."""
        self._adapter_slots: dict[str, int] = {}
        self._allocations_by_adapter: dict[str, dict[str, DeviceWatcher]] = {}
        self._manager: BlueZManager | None = None

    async def async_setup(self) -> None:
        """Set up the class."""
        self._manager = await get_global_bluez_manager_with_timeout()

    def diagnostics(self) -> dict[str, Any]:
        """Return diagnostics."""
        return {
            "manager": self._manager is not None,
            "adapter_slots": self._adapter_slots,
            "allocations_by_adapter": {
                adapter: self._get_allocations(adapter)
                for adapter in self._adapter_slots
            },
        }

    def _get_allocations(self, adapter: str) -> list[str]:
        """Get connected path allocations."""
        if self._manager is None:
            return []
        return list(self._allocations_by_adapter[adapter])

    def remove_adapter(self, adapter: str) -> None:
        """Remove an adapter."""
        del self._adapter_slots[adapter]
        watchers = self._allocations_by_adapter[adapter]
        if self._manager is None:
            return
        for watcher in watchers.values():
            self._manager.remove_device_watcher(watcher)
        del self._allocations_by_adapter[adapter]

    def register_adapter(self, adapter: str, slots: int) -> None:
        """Register an adapter."""
        self._allocations_by_adapter[adapter] = {}
        self._adapter_slots[adapter] = slots
        if self._manager is None:
            return
        for path, device in self._manager._properties.items():
            if (
                defs.DEVICE_INTERFACE in device
                and device[defs.DEVICE_INTERFACE].get("Connected")
                and adapter_from_path(path) == adapter
            ):
                self._allocate_and_watch_slot(path)

    def _allocate_and_watch_slot(self, path: str) -> None:
        """Setup a device watcher."""
        assert self._manager is not None  # nosec
        adapter = adapter_from_path(path)
        allocations = self._allocations_by_adapter[adapter]

        def _on_device_connected_changed(connected: bool) -> None:
            if not connected:
                self._release_slot(path)

        allocations[path] = self._manager.add_device_watcher(
            path,
            on_connected_changed=_on_device_connected_changed,
            on_characteristic_value_changed=_on_characteristic_value_changed,
        )

    def release_slot(self, device: BLEDevice) -> None:
        """Release a slot."""
        if (
            self._manager is None
            or not (path := path_from_ble_device(device))
            or self._manager.is_connected(path)
        ):
            return
        self._release_slot(path)

    def _release_slot(self, path: str) -> None:
        """Unconditional release of the slot."""
        assert self._manager is not None  # nosec
        adapter = adapter_from_path(path)
        allocations = self._allocations_by_adapter[adapter]
        if watcher := allocations.pop(path, None):
            self._manager.remove_device_watcher(watcher)

    def allocate_slot(self, device: BLEDevice) -> bool:
        """Allocate a slot."""
        if (
            self._manager is None
            or not (path := path_from_ble_device(device))
            or not (adapter := adapter_from_path(path))
            or adapter not in self._allocations_by_adapter
        ):
            return True
        allocations = self._allocations_by_adapter[adapter]
        if path in allocations:
            # Already connected
            return True
        if len(allocations) >= self._adapter_slots[adapter]:
            _LOGGER.debug(
                "No slots available for %s (used by: %s)",
                path,
                self._get_allocations(adapter),
            )
            return False
        self._allocate_and_watch_slot(path)
        return True


async def _get_properties() -> dict[str, dict[str, dict[str, Any]]] | None:
    """Get the properties."""
    if bluez_manager := await get_global_bluez_manager_with_timeout():
        return bluez_manager._properties  # pylint: disable=protected-access
    return None


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


async def get_device_by_adapter(address: str, adapter: str) -> BLEDevice | None:
    """Get the device by adapter and address."""
    if not IS_LINUX:
        return None
    if not (properties := await _get_properties()):
        return None
    device_path = address_to_bluez_path(address, adapter)
    if device_path in properties and (
        device_props := properties[device_path].get(defs.DEVICE_INTERFACE)
    ):
        return ble_device_from_properties(device_path, device_props)
    return None


async def get_bluez_device(
    name: str, path: str, rssi: int | None = None, _log_disappearance: bool = True
) -> BLEDevice | None:
    """Get a BLEDevice object for a BlueZ DBus path."""

    best_path = device_path = path
    rssi_to_beat: int = rssi or NO_RSSI_VALUE

    if not (properties := await _get_properties()):
        return None

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


async def get_connected_devices(device: BLEDevice) -> list[BLEDevice]:
    """Check if the device is connected."""
    connected: list[BLEDevice] = []

    if not isinstance(device.details, dict) or "path" not in device.details:
        return connected
    if not (properties := await _get_properties()):
        return connected
    device_path = device.details["path"]
    for path in _get_possible_paths(device_path):
        if path not in properties or defs.DEVICE_INTERFACE not in properties[path]:
            continue
        props = properties[path][defs.DEVICE_INTERFACE]
        if props.get("Connected"):
            connected.append(ble_device_from_properties(path, props))
    return connected


async def get_device(address: str) -> BLEDevice | None:
    """Get the device."""
    if not IS_LINUX:
        return None
    return await get_bluez_device(
        address, address_to_bluez_path(address), _log_disappearance=False
    )


def address_to_bluez_path(address: str, adapter: str | None = None) -> str:
    """Convert an address to a BlueZ path."""
    return f"/org/bluez/{adapter or 'hciX'}/dev_{address.upper().replace(':', '_')}"


def _get_possible_paths(path: str) -> Generator[str, None, None]:
    """Get the possible paths."""
    # The path is deterministic so we splice up the string
    # /org/bluez/hci2/dev_FA_23_9D_AA_45_46
    for i in range(0, 9):
        yield f"{path[0:14]}{i}{path[15:]}"


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
