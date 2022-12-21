from __future__ import annotations

import asyncio
import contextlib
import logging
import platform
from typing import Any

import async_timeout
from bleak.backends.device import BLEDevice

DISCONNECT_TIMEOUT = 5
DBUS_CONNECT_TIMEOUT = 8.5

_LOGGER = logging.getLogger(__name__)

IS_LINUX = platform.system() == "Linux"
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


def _reset_dbus_socket_cache() -> None:
    """Reset the dbus socket cache."""
    setattr(get_global_bluez_manager_with_timeout, "_has_dbus_socket", None)


def adapter_from_path(path: str) -> str:
    """Get the adapter from a ble device path."""
    return path.partition("/")[2]


def path_from_ble_device(device: BLEDevice) -> str | None:
    """Get the adapter from a ble device."""
    if not isinstance(device.details, dict):
        return None
    if "path" not in device.details:
        return None
    path: str = device.details["path"]
    return path


def _on_characteristic_value_changed(
    interface: str, changed: dict[str, Any], invalidated: list[str]
) -> None:
    pass


class BleakSlotManager:

    """A class to manage the connection slots."""

    def __init__(self) -> None:
        """Initialize the class."""
        self._adapter_slots: dict[str, int] = {}
        self._allocations_by_adapter: dict[str, dict[str, DeviceWatcher]] = {}
        self._slots: dict[str, asyncio.Semaphore] = {}
        self._manager: BlueZManager | None = None

    async def async_setup(self) -> None:
        """Set up the class."""
        self._manager = await get_global_bluez_manager_with_timeout()

    def diagnostics(self) -> dict[str, int]:
        """Return diagnostics."""
        return {address: slot._value for address, slot in self._slots.items()}

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
            if defs.DEVICE_INTERFACE in device and device[defs.DEVICE_INTERFACE].get(
                "Connected"
            ):
                self._allocate_and_watch_slot(path)

    def _allocate_and_watch_slot(self, path: str) -> None:
        """Setup a device watcher."""
        if not self._manager:
            return
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
        if not self._manager:
            return
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
            return False
        self._allocate_and_watch_slot(path)
        return True
