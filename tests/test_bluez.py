from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from bleak.backends.bluezdbus import defs
from bleak.backends.bluezdbus.manager import DeviceWatcher
from bleak.backends.device import BLEDevice
from bleak.exc import BleakError

import bleak_retry_connector
from bleak_retry_connector import (
    AllocationChange,
    AllocationChangeEvent,
    Allocations,
    BleakSlotManager,
    device_source,
)
from bleak_retry_connector.bluez import (
    adapter_path_from_device_path,
    ble_device_from_properties,
    clear_cache,
    get_bluez_device,
    get_connected_devices,
    get_device_by_adapter,
    path_from_ble_device,
    stop_discovery,
    wait_for_device_to_reappear,
    wait_for_disconnect,
)

pytestmark = pytest.mark.asyncio


async def test_slot_manager(mock_linux):
    """Test the slot manager"""

    class FakeBluezManager:
        def __init__(self):
            self.watchers: set[DeviceWatcher] = set()
            self._properties = {
                "/org/bluez/hci0/dev_FA_23_9D_AA_45_46": {
                    "UUID": "service",
                    "Primary": True,
                    "Characteristics": [],
                    defs.DEVICE_INTERFACE: {
                        "Address": "FA:23:9D:AA:45:46",
                        "Alias": "FA:23:9D:AA:45:46",
                        "RSSI": -30,
                    },
                    defs.GATT_SERVICE_INTERFACE: True,
                },
                "/org/bluez/hci1/dev_FA_23_9D_AA_45_46": {
                    "UUID": "service",
                    "Primary": True,
                    "Characteristics": [],
                    defs.DEVICE_INTERFACE: {
                        "Connected": True,
                        "Address": "FA:23:9D:AA:45:46",
                        "Alias": "FA:23:9D:AA:45:46",
                        "RSSI": -79,
                    },
                    defs.GATT_SERVICE_INTERFACE: True,
                },
                "/org/bluez/hci2/dev_FA_23_9D_AA_45_46": {
                    "UUID": "service",
                    "Primary": True,
                    "Characteristics": [],
                    defs.DEVICE_INTERFACE: {
                        "Connected": True,
                        "Address": "FA:23:9D:AA:45:46",
                        "Alias": "FA:23:9D:AA:45:46",
                        "RSSI": -80,
                    },
                    defs.GATT_SERVICE_INTERFACE: True,
                },
                "/org/bluez/hci3/dev_FA_23_9D_AA_45_46": {
                    "UUID": "service",
                    "Primary": True,
                    "Characteristics": [],
                    defs.DEVICE_INTERFACE: {
                        "Address": "FA:23:9D:AA:45:46",
                        "Alias": "FA:23:9D:AA:45:46",
                        "RSSI": -31,
                    },
                    defs.GATT_SERVICE_INTERFACE: True,
                },
            }

        def add_device_watcher(self, path: str, **kwargs: Any) -> DeviceWatcher:
            """Add a watcher for device changes."""
            watcher = DeviceWatcher(path, **kwargs)
            self.watchers.add(watcher)
            return watcher

        def remove_device_watcher(self, watcher: DeviceWatcher) -> None:
            """Remove a watcher for device changes."""
            self.watchers.remove(watcher)

        def is_connected(self, path: str) -> bool:
            """Check if device is connected."""
            return False

    bleak_retry_connector.bleak_manager.get_global_bluez_manager = AsyncMock(
        return_value=FakeBluezManager()
    )
    bleak_retry_connector.bluez.defs = defs

    slot_manager = BleakSlotManager()

    await slot_manager.async_setup()
    slot_manager.register_adapter("hci0", 1)
    slot_manager.register_adapter("hci1", 2)
    slot_manager.register_adapter("hci2", 1)
    changes = []

    def _failing_allocation_callback(event: AllocationChangeEvent) -> None:
        raise Exception("Test")

    def _allocation_callback(event: AllocationChangeEvent) -> None:
        change = event.change
        path = event.path
        adapter = event.adapter
        address = event.address

        changes.append((change, path, adapter, address))

    cancel_fail = slot_manager.register_allocation_callback(
        _failing_allocation_callback
    )
    cancel = slot_manager.register_allocation_callback(_allocation_callback)

    ble_device_hci2 = ble_device_from_properties(
        "/org/bluez/hci2/dev_FA_23_9D_AA_45_45",
        {
            "Address": "FA:23:9D:AA:45:45",
            "Alias": "FA:23:9D:AA:45:45",
            "RSSI": -30,
        },
    )
    ble_device_hci2_already_connected = ble_device_from_properties(
        "/org/bluez/hci2/dev_FA_23_9D_AA_45_46",
        {
            "Address": "FA:23:9D:AA:45:46",
            "Alias": "FA:23:9D:AA:45:46",
            "RSSI": -30,
        },
    )
    ble_device_hci0 = ble_device_from_properties(
        "/org/bluez/hci0/dev_FA_23_9D_AA_45_46",
        {
            "Address": "FA:23:9D:AA:45:46",
            "Alias": "FA:23:9D:AA:45:46",
            "RSSI": -30,
        },
    )
    ble_device_hci0_2 = ble_device_from_properties(
        "/org/bluez/hci0/dev_FA_23_9D_AA_45_47",
        {
            "Address": "FA:23:9D:AA:45:47",
            "Alias": "FA:23:9D:AA:45:47",
            "RSSI": -30,
        },
    )

    assert slot_manager.allocate_slot(ble_device_hci2) is False
    assert not changes
    # Make sure we can allocate an already connected device
    # since there is always a race condition between the
    # slot manager and the device connecting
    assert slot_manager.allocate_slot(ble_device_hci2_already_connected) is True
    assert not changes

    assert slot_manager.allocate_slot(ble_device_hci0) is True
    assert changes == [
        (
            AllocationChange.ALLOCATED,
            "/org/bluez/hci0/dev_FA_23_9D_AA_45_46",
            "hci0",
            "FA:23:9D:AA:45:46",
        )
    ]
    assert slot_manager._get_allocations("hci0") == [
        "/org/bluez/hci0/dev_FA_23_9D_AA_45_46"
    ]
    assert slot_manager.get_allocations("hci0") == Allocations(
        "hci0",
        1,
        0,
        ["FA:23:9D:AA:45:46"],
    )

    # Make sure we can allocate the same device again
    assert slot_manager.allocate_slot(ble_device_hci0) is True
    assert changes == [
        (
            AllocationChange.ALLOCATED,
            "/org/bluez/hci0/dev_FA_23_9D_AA_45_46",
            "hci0",
            "FA:23:9D:AA:45:46",
        ),
    ]
    assert slot_manager._get_allocations("hci0") == [
        "/org/bluez/hci0/dev_FA_23_9D_AA_45_46"
    ]
    assert slot_manager.get_allocations("hci0") == Allocations(
        "hci0",
        1,
        0,
        ["FA:23:9D:AA:45:46"],
    )
    assert slot_manager.allocate_slot(ble_device_hci0_2) is False
    assert changes == [
        (
            AllocationChange.ALLOCATED,
            "/org/bluez/hci0/dev_FA_23_9D_AA_45_46",
            "hci0",
            "FA:23:9D:AA:45:46",
        ),
    ]
    assert slot_manager._get_allocations("hci0") == [
        "/org/bluez/hci0/dev_FA_23_9D_AA_45_46"
    ]
    assert slot_manager.get_allocations("hci0") == Allocations(
        "hci0",
        1,
        0,
        ["FA:23:9D:AA:45:46"],
    )
    watcher: DeviceWatcher = slot_manager._allocations_by_adapter["hci0"][
        "/org/bluez/hci0/dev_FA_23_9D_AA_45_46"
    ]
    watcher.on_connected_changed(True)
    assert slot_manager._get_allocations("hci0") == [
        "/org/bluez/hci0/dev_FA_23_9D_AA_45_46"
    ]
    assert slot_manager.get_allocations("hci0") == Allocations(
        "hci0",
        1,
        0,
        ["FA:23:9D:AA:45:46"],
    )
    assert changes == [
        (
            AllocationChange.ALLOCATED,
            "/org/bluez/hci0/dev_FA_23_9D_AA_45_46",
            "hci0",
            "FA:23:9D:AA:45:46",
        ),
    ]
    watcher.on_connected_changed(False)
    assert changes == [
        (
            AllocationChange.ALLOCATED,
            "/org/bluez/hci0/dev_FA_23_9D_AA_45_46",
            "hci0",
            "FA:23:9D:AA:45:46",
        ),
        (
            AllocationChange.RELEASED,
            "/org/bluez/hci0/dev_FA_23_9D_AA_45_46",
            "hci0",
            "FA:23:9D:AA:45:46",
        ),
    ]
    assert slot_manager._get_allocations("hci0") == []
    assert slot_manager.get_allocations("hci0") == Allocations(
        "hci0",
        1,
        1,
        [],
    )
    assert slot_manager.allocate_slot(ble_device_hci0) is True
    assert slot_manager._get_allocations("hci0") == [
        "/org/bluez/hci0/dev_FA_23_9D_AA_45_46"
    ]
    assert slot_manager.get_allocations("hci0") == Allocations(
        "hci0",
        1,
        0,
        ["FA:23:9D:AA:45:46"],
    )
    assert changes == [
        (
            AllocationChange.ALLOCATED,
            "/org/bluez/hci0/dev_FA_23_9D_AA_45_46",
            "hci0",
            "FA:23:9D:AA:45:46",
        ),
        (
            AllocationChange.RELEASED,
            "/org/bluez/hci0/dev_FA_23_9D_AA_45_46",
            "hci0",
            "FA:23:9D:AA:45:46",
        ),
        (
            AllocationChange.ALLOCATED,
            "/org/bluez/hci0/dev_FA_23_9D_AA_45_46",
            "hci0",
            "FA:23:9D:AA:45:46",
        ),
    ]

    assert slot_manager.diagnostics() == {
        "adapter_slots": {"hci0": 1, "hci1": 2, "hci2": 1},
        "allocations_by_adapter": {
            "hci0": ["/org/bluez/hci0/dev_FA_23_9D_AA_45_46"],
            "hci1": ["/org/bluez/hci1/dev_FA_23_9D_AA_45_46"],
            "hci2": ["/org/bluez/hci2/dev_FA_23_9D_AA_45_46"],
        },
        "manager": True,
    }

    slot_manager.release_slot(ble_device_hci0)
    assert changes == [
        (
            AllocationChange.ALLOCATED,
            "/org/bluez/hci0/dev_FA_23_9D_AA_45_46",
            "hci0",
            "FA:23:9D:AA:45:46",
        ),
        (
            AllocationChange.RELEASED,
            "/org/bluez/hci0/dev_FA_23_9D_AA_45_46",
            "hci0",
            "FA:23:9D:AA:45:46",
        ),
        (
            AllocationChange.ALLOCATED,
            "/org/bluez/hci0/dev_FA_23_9D_AA_45_46",
            "hci0",
            "FA:23:9D:AA:45:46",
        ),
        (
            AllocationChange.RELEASED,
            "/org/bluez/hci0/dev_FA_23_9D_AA_45_46",
            "hci0",
            "FA:23:9D:AA:45:46",
        ),
    ]
    assert slot_manager._get_allocations("hci0") == []
    assert slot_manager.get_allocations("hci0") == Allocations(
        "hci0",
        1,
        1,
        [],
    )
    assert slot_manager.allocate_slot(ble_device_hci0) is True
    assert changes == [
        (
            AllocationChange.ALLOCATED,
            "/org/bluez/hci0/dev_FA_23_9D_AA_45_46",
            "hci0",
            "FA:23:9D:AA:45:46",
        ),
        (
            AllocationChange.RELEASED,
            "/org/bluez/hci0/dev_FA_23_9D_AA_45_46",
            "hci0",
            "FA:23:9D:AA:45:46",
        ),
        (
            AllocationChange.ALLOCATED,
            "/org/bluez/hci0/dev_FA_23_9D_AA_45_46",
            "hci0",
            "FA:23:9D:AA:45:46",
        ),
        (
            AllocationChange.RELEASED,
            "/org/bluez/hci0/dev_FA_23_9D_AA_45_46",
            "hci0",
            "FA:23:9D:AA:45:46",
        ),
        (
            AllocationChange.ALLOCATED,
            "/org/bluez/hci0/dev_FA_23_9D_AA_45_46",
            "hci0",
            "FA:23:9D:AA:45:46",
        ),
    ]
    assert slot_manager._get_allocations("hci0") == [
        "/org/bluez/hci0/dev_FA_23_9D_AA_45_46"
    ]
    assert slot_manager.get_allocations("hci0") == Allocations(
        "hci0",
        1,
        0,
        ["FA:23:9D:AA:45:46"],
    )
    slot_manager.remove_adapter("hci0")
    assert changes == [
        (
            AllocationChange.ALLOCATED,
            "/org/bluez/hci0/dev_FA_23_9D_AA_45_46",
            "hci0",
            "FA:23:9D:AA:45:46",
        ),
        (
            AllocationChange.RELEASED,
            "/org/bluez/hci0/dev_FA_23_9D_AA_45_46",
            "hci0",
            "FA:23:9D:AA:45:46",
        ),
        (
            AllocationChange.ALLOCATED,
            "/org/bluez/hci0/dev_FA_23_9D_AA_45_46",
            "hci0",
            "FA:23:9D:AA:45:46",
        ),
        (
            AllocationChange.RELEASED,
            "/org/bluez/hci0/dev_FA_23_9D_AA_45_46",
            "hci0",
            "FA:23:9D:AA:45:46",
        ),
        (
            AllocationChange.ALLOCATED,
            "/org/bluez/hci0/dev_FA_23_9D_AA_45_46",
            "hci0",
            "FA:23:9D:AA:45:46",
        ),
    ]
    assert slot_manager.allocate_slot(ble_device_hci0) is True
    assert changes == [
        (
            AllocationChange.ALLOCATED,
            "/org/bluez/hci0/dev_FA_23_9D_AA_45_46",
            "hci0",
            "FA:23:9D:AA:45:46",
        ),
        (
            AllocationChange.RELEASED,
            "/org/bluez/hci0/dev_FA_23_9D_AA_45_46",
            "hci0",
            "FA:23:9D:AA:45:46",
        ),
        (
            AllocationChange.ALLOCATED,
            "/org/bluez/hci0/dev_FA_23_9D_AA_45_46",
            "hci0",
            "FA:23:9D:AA:45:46",
        ),
        (
            AllocationChange.RELEASED,
            "/org/bluez/hci0/dev_FA_23_9D_AA_45_46",
            "hci0",
            "FA:23:9D:AA:45:46",
        ),
        (
            AllocationChange.ALLOCATED,
            "/org/bluez/hci0/dev_FA_23_9D_AA_45_46",
            "hci0",
            "FA:23:9D:AA:45:46",
        ),
    ]
    assert slot_manager.allocate_slot(ble_device_hci0_2) is True
    assert changes == [
        (
            AllocationChange.ALLOCATED,
            "/org/bluez/hci0/dev_FA_23_9D_AA_45_46",
            "hci0",
            "FA:23:9D:AA:45:46",
        ),
        (
            AllocationChange.RELEASED,
            "/org/bluez/hci0/dev_FA_23_9D_AA_45_46",
            "hci0",
            "FA:23:9D:AA:45:46",
        ),
        (
            AllocationChange.ALLOCATED,
            "/org/bluez/hci0/dev_FA_23_9D_AA_45_46",
            "hci0",
            "FA:23:9D:AA:45:46",
        ),
        (
            AllocationChange.RELEASED,
            "/org/bluez/hci0/dev_FA_23_9D_AA_45_46",
            "hci0",
            "FA:23:9D:AA:45:46",
        ),
        (
            AllocationChange.ALLOCATED,
            "/org/bluez/hci0/dev_FA_23_9D_AA_45_46",
            "hci0",
            "FA:23:9D:AA:45:46",
        ),
    ]
    cancel_fail()
    cancel()


async def test_slot_manager_adapter_removal_during_disconnect(mock_linux):
    """Test that adapter removal during disconnect doesn't cause KeyError."""

    class FakeBluezManager:
        def __init__(self):
            self.watchers: set[DeviceWatcher] = set()
            self._properties = {
                "/org/bluez/hci1/dev_FA_23_9D_AA_45_46": {
                    defs.DEVICE_INTERFACE: {
                        "Connected": True,
                        "Address": "FA:23:9D:AA:45:46",
                        "Alias": "Test Device",
                        "RSSI": -60,
                    },
                },
            }

        def add_device_watcher(self, path: str, **kwargs: Any) -> DeviceWatcher:
            """Add a watcher for device changes."""
            watcher = DeviceWatcher(path, **kwargs)
            self.watchers.add(watcher)
            return watcher

        def remove_device_watcher(self, watcher: DeviceWatcher) -> None:
            """Remove a watcher for device changes."""
            self.watchers.discard(watcher)

        def is_connected(self, path: str) -> bool:
            """Check if device is connected."""
            return False

    bleak_retry_connector.bleak_manager.get_global_bluez_manager = AsyncMock(
        return_value=FakeBluezManager()
    )
    bleak_retry_connector.bluez.defs = defs

    slot_manager = BleakSlotManager()
    await slot_manager.async_setup()

    # Register adapter and allocate a slot
    slot_manager.register_adapter("hci1", 5)

    ble_device = ble_device_from_properties(
        "/org/bluez/hci1/dev_FA_23_9D_AA_45_46",
        {
            "Address": "FA:23:9D:AA:45:46",
            "Alias": "Test Device",
            "RSSI": -60,
        },
    )

    # Allocate the slot
    assert slot_manager.allocate_slot(ble_device) is True

    # Store the watcher to simulate disconnect event later
    watcher: DeviceWatcher = slot_manager._allocations_by_adapter["hci1"][
        "/org/bluez/hci1/dev_FA_23_9D_AA_45_46"
    ]

    # Simulate adapter removal (e.g., adapter unplugged)
    slot_manager.remove_adapter("hci1")

    # Now simulate the disconnect event firing after adapter removal
    # This should not raise a KeyError
    watcher.on_connected_changed(False)

    # Verify the adapter is gone and methods handle it gracefully
    assert slot_manager._get_allocations("hci1") == []
    assert slot_manager.get_allocations("hci1") == Allocations("hci1", 0, 0, [])


async def test_slot_manager_mac_os():
    """Test the slot manager"""

    bleak_retry_connector.bleak_manager.get_global_bluez_manager = AsyncMock(
        return_value=None
    )
    bleak_retry_connector.bluez.defs = defs

    slot_manager = BleakSlotManager()

    await slot_manager.async_setup()
    slot_manager.register_adapter("hci0", 1)
    slot_manager.register_adapter("hci1", 2)
    slot_manager.register_adapter("hci2", 1)

    ble_device_hci0 = ble_device_from_properties(
        "/org/bluez/hci0/dev_FA_23_9D_AA_45_46",
        {
            "Address": "FA:23:9D:AA:45:46",
            "Alias": "FA:23:9D:AA:45:46",
            "RSSI": -30,
        },
    )
    ble_device_hci0_2 = ble_device_from_properties(
        "/org/bluez/hci0/dev_FA_23_9D_AA_45_47",
        {
            "Address": "FA:23:9D:AA:45:47",
            "Alias": "FA:23:9D:AA:45:47",
            "RSSI": -30,
        },
    )

    assert slot_manager.allocate_slot(ble_device_hci0) is True
    assert slot_manager._get_allocations("hci0") == []
    assert slot_manager.allocate_slot(ble_device_hci0_2) is True
    assert slot_manager._get_allocations("hci0") == []

    assert slot_manager.allocate_slot(ble_device_hci0) is True
    assert slot_manager._get_allocations("hci0") == []
    slot_manager.release_slot(ble_device_hci0)
    assert slot_manager._get_allocations("hci0") == []
    slot_manager.remove_adapter("hci0")


async def test_device_source():
    ble_device_hci0_2 = BLEDevice(
        "FA:23:9D:AA:45:46",
        "FA:23:9D:AA:45:46",
        {
            "source": "aa:bb:cc:dd:ee:ff",
            "path": "/org/bluez/hci0/dev_FA_23_9D_AA_45_47",
            "props": {},
        },
    )

    assert device_source(ble_device_hci0_2) == "aa:bb:cc:dd:ee:ff"


async def test_path_from_ble_device():
    ble_device_hci0_2 = BLEDevice(
        "FA:23:9D:AA:45:46",
        "FA:23:9D:AA:45:46",
        {
            "source": "aa:bb:cc:dd:ee:ff",
            "path": "/org/bluez/hci0/dev_FA_23_9D_AA_45_47",
            "props": {},
        },
    )

    assert (
        path_from_ble_device(ble_device_hci0_2)
        == "/org/bluez/hci0/dev_FA_23_9D_AA_45_47"
    )


async def test_wait_for_device_to_reappear(mock_linux):
    class FakeBluezManager:
        def __init__(self):
            self.watchers: set[DeviceWatcher] = set()
            self._properties = {
                "/org/bluez/hci0/dev_FA_23_9D_AA_45_46": {
                    "UUID": "service",
                    "Primary": True,
                    "Characteristics": [],
                    defs.DEVICE_INTERFACE: {
                        "Address": "FA:23:9D:AA:45:46",
                        "Alias": "FA:23:9D:AA:45:46",
                        "RSSI": -30,
                    },
                    defs.GATT_SERVICE_INTERFACE: True,
                },
                "/org/bluez/hci1/dev_FA_23_9D_AA_45_46": {
                    "UUID": "service",
                    "Primary": True,
                    "Characteristics": [],
                    defs.DEVICE_INTERFACE: {
                        "Connected": True,
                        "Address": "FA:23:9D:AA:45:46",
                        "Alias": "FA:23:9D:AA:45:46",
                        "RSSI": -79,
                    },
                    defs.GATT_SERVICE_INTERFACE: True,
                },
            }

        def add_device_watcher(self, path: str, **kwargs: Any) -> DeviceWatcher:
            """Add a watcher for device changes."""
            watcher = DeviceWatcher(path, **kwargs)
            self.watchers.add(watcher)
            return watcher

        def remove_device_watcher(self, watcher: DeviceWatcher) -> None:
            """Remove a watcher for device changes."""
            self.watchers.remove(watcher)

        def is_connected(self, path: str) -> bool:
            """Check if device is connected."""
            return False

    bluez_manager = FakeBluezManager()
    bleak_retry_connector.bleak_manager.get_global_bluez_manager = AsyncMock(
        return_value=bluez_manager
    )
    bleak_retry_connector.bluez.defs = defs

    ble_device_hci0 = BLEDevice(
        "FA:23:9D:AA:45:46",
        "FA:23:9D:AA:45:46",
        {
            "source": "aa:bb:cc:dd:ee:ff",
            "path": "/org/bluez/hci0/dev_FA_23_9D_AA_45_46",
            "props": {},
        },
    )

    assert await wait_for_device_to_reappear(ble_device_hci0, 1) is True
    del bluez_manager._properties["/org/bluez/hci0/dev_FA_23_9D_AA_45_46"]
    assert await wait_for_device_to_reappear(ble_device_hci0, 1) is True
    del bluez_manager._properties["/org/bluez/hci1/dev_FA_23_9D_AA_45_46"]
    with patch.object(bleak_retry_connector.bluez, "REAPPEAR_WAIT_INTERVAL", 0.025):
        assert await wait_for_device_to_reappear(ble_device_hci0, 0.1) is False


async def test_adapter_path_from_device_path(mock_linux):
    assert (
        adapter_path_from_device_path("/org/bluez/hci1/dev_FA_23_9D_AA_45_46")
        == "/org/bluez/hci1"
    )


async def test_stop_discovery(mock_linux):
    """Test stopping discovery"""

    class FakeBluezManager:
        def __init__(self) -> None:
            """Mock initializer."""
            self._bus = MagicMock(send=AsyncMock())

    manager = FakeBluezManager()

    bleak_retry_connector.bleak_manager.get_global_bluez_manager = AsyncMock(
        return_value=manager
    )
    bleak_retry_connector.bluez.defs = defs
    bleak_retry_connector.bluez.Message = MagicMock()

    await stop_discovery("hci0")
    assert manager._bus.send.called


async def test_stop_discovery_no_manager(
    mock_linux: None, caplog: pytest.LogCaptureFixture
) -> None:
    """Test stopping discovery no manager."""

    bleak_retry_connector.bleak_manager.get_global_bluez_manager = AsyncMock(
        return_value=None
    )
    bleak_retry_connector.bluez.defs = defs
    bleak_retry_connector.bluez.Message = MagicMock()

    await stop_discovery("hci0")
    assert "Failed to stop discovery" in caplog.text


async def test_wait_for_disconnect_not_linux(mock_macos):
    """Non-Linux platforms fall back to a plain sleep."""
    device = BLEDevice("AA:BB:CC:DD:EE:FF", "name", {"path": "/org/bluez/hci0/dev_x"})
    sleeps: list[float] = []

    async def fake_sleep(delay: float) -> None:
        sleeps.append(delay)

    with patch("bleak_retry_connector.bluez.asyncio.sleep", side_effect=fake_sleep):
        await wait_for_disconnect(device, 0.25)

    assert sleeps == [0.25]


async def test_wait_for_disconnect_no_path(mock_linux):
    """Devices without a 'path' entry in details fall back to a plain sleep."""
    device = BLEDevice("AA:BB:CC:DD:EE:FF", "name", {"source": "aa:bb:cc:dd:ee:ff"})
    sleeps: list[float] = []

    async def fake_sleep(delay: float) -> None:
        sleeps.append(delay)

    with patch("bleak_retry_connector.bluez.asyncio.sleep", side_effect=fake_sleep):
        await wait_for_disconnect(device, 0.1)

    assert sleeps == [0.1]


async def test_wait_for_disconnect_no_manager(
    mock_linux: None, caplog: pytest.LogCaptureFixture
) -> None:
    """If no BlueZ manager is available, log and return without sleeping."""
    device = BLEDevice(
        "FA:23:9D:AA:45:46",
        "FA:23:9D:AA:45:46",
        {"path": "/org/bluez/hci0/dev_FA_23_9D_AA_45_46"},
    )
    with patch(
        "bleak_retry_connector.bluez.get_global_bluez_manager_with_timeout",
        AsyncMock(return_value=None),
    ):
        await wait_for_disconnect(device, 1.0)

    assert "Failed to wait for disconnect because no manager" in caplog.text


async def test_wait_for_disconnect_waits_remaining_min_wait_time(mock_linux):
    """When the device disconnects sooner than min_wait_time, sleep the remainder."""
    device = BLEDevice(
        "FA:23:9D:AA:45:46",
        "FA:23:9D:AA:45:46",
        {"path": "/org/bluez/hci0/dev_FA_23_9D_AA_45_46"},
    )
    manager = MagicMock()
    manager._wait_condition = AsyncMock()
    # Only wait_for_disconnect-issued sleeps land here (we don't patch global sleep).
    sleeps: list[float] = []

    async def fake_sleep(delay: float) -> None:
        sleeps.append(delay)

    # Patch the time module bound on bluez to return start=100.0, end=100.2
    # without affecting asyncio internals that read the real clock.
    fake_time = MagicMock()
    fake_time.monotonic = MagicMock(side_effect=[100.0, 100.2])

    with (
        patch(
            "bleak_retry_connector.bluez.get_global_bluez_manager_with_timeout",
            AsyncMock(return_value=manager),
        ),
        patch.object(bleak_retry_connector.bluez, "time", fake_time),
        patch("bleak_retry_connector.bluez.asyncio.sleep", side_effect=fake_sleep),
    ):
        await wait_for_disconnect(device, 1.0)

    manager._wait_condition.assert_awaited_once_with(
        "/org/bluez/hci0/dev_FA_23_9D_AA_45_46", "Connected", False
    )
    # waited = 0.2, min_wait_time = 1.0, so remaining sleep should be 0.8.
    assert sleeps == [pytest.approx(0.8)]


async def test_wait_for_disconnect_skips_extra_sleep_when_already_waited(mock_linux):
    """If we already waited long enough, no extra sleep is issued."""
    device = BLEDevice(
        "FA:23:9D:AA:45:46",
        "FA:23:9D:AA:45:46",
        {"path": "/org/bluez/hci0/dev_FA_23_9D_AA_45_46"},
    )
    manager = MagicMock()
    manager._wait_condition = AsyncMock()
    sleeps: list[float] = []

    async def fake_sleep(delay: float) -> None:
        sleeps.append(delay)

    fake_time = MagicMock()
    fake_time.monotonic = MagicMock(side_effect=[100.0, 105.0])

    with (
        patch(
            "bleak_retry_connector.bluez.get_global_bluez_manager_with_timeout",
            AsyncMock(return_value=manager),
        ),
        patch.object(bleak_retry_connector.bluez, "time", fake_time),
        patch("bleak_retry_connector.bluez.asyncio.sleep", side_effect=fake_sleep),
    ):
        await wait_for_disconnect(device, 1.0)

    assert sleeps == []


async def test_wait_for_disconnect_zero_min_wait_time(mock_linux):
    """min_wait_time=0 bypasses the timing branch entirely."""
    device = BLEDevice(
        "FA:23:9D:AA:45:46",
        "FA:23:9D:AA:45:46",
        {"path": "/org/bluez/hci0/dev_FA_23_9D_AA_45_46"},
    )
    manager = MagicMock()
    manager._wait_condition = AsyncMock()
    sleeps: list[float] = []

    async def fake_sleep(delay: float) -> None:
        sleeps.append(delay)

    with (
        patch(
            "bleak_retry_connector.bluez.get_global_bluez_manager_with_timeout",
            AsyncMock(return_value=manager),
        ),
        patch("bleak_retry_connector.bluez.asyncio.sleep", side_effect=fake_sleep),
    ):
        await wait_for_disconnect(device, 0)

    manager._wait_condition.assert_awaited_once()
    assert sleeps == []


async def test_wait_for_disconnect_bleak_error_triggers_reappear(
    mock_linux: None, caplog: pytest.LogCaptureFixture
) -> None:
    """A BleakError from _wait_condition routes through wait_for_device_to_reappear."""
    device = BLEDevice(
        "FA:23:9D:AA:45:46",
        "FA:23:9D:AA:45:46",
        {"path": "/org/bluez/hci0/dev_FA_23_9D_AA_45_46"},
    )
    manager = MagicMock()
    manager._wait_condition = AsyncMock(side_effect=BleakError("gone"))
    reappear_calls: list[tuple[BLEDevice, float]] = []

    async def fake_reappear(d, t):
        reappear_calls.append((d, t))
        return True

    with (
        patch(
            "bleak_retry_connector.bluez.get_global_bluez_manager_with_timeout",
            AsyncMock(return_value=manager),
        ),
        patch(
            "bleak_retry_connector.bluez.wait_for_device_to_reappear",
            side_effect=fake_reappear,
        ),
    ):
        await wait_for_disconnect(device, 0.5)

    assert reappear_calls == [(device, 0.5)]
    assert "Device was removed from bus" in caplog.text


async def test_wait_for_disconnect_key_error_triggers_reappear(mock_linux):
    """KeyError is treated the same as BleakError."""
    device = BLEDevice(
        "FA:23:9D:AA:45:46",
        "FA:23:9D:AA:45:46",
        {"path": "/org/bluez/hci0/dev_FA_23_9D_AA_45_46"},
    )
    manager = MagicMock()
    manager._wait_condition = AsyncMock(side_effect=KeyError("missing"))
    called = False

    async def fake_reappear(d, t):
        nonlocal called
        called = True
        return False

    with (
        patch(
            "bleak_retry_connector.bluez.get_global_bluez_manager_with_timeout",
            AsyncMock(return_value=manager),
        ),
        patch(
            "bleak_retry_connector.bluez.wait_for_device_to_reappear",
            side_effect=fake_reappear,
        ),
    ):
        await wait_for_disconnect(device, 0.1)

    assert called


async def test_wait_for_disconnect_unexpected_exception_swallowed(
    mock_linux: None, caplog: pytest.LogCaptureFixture
) -> None:
    """Any other exception is logged and swallowed — no reappear fallback."""
    device = BLEDevice(
        "FA:23:9D:AA:45:46",
        "FA:23:9D:AA:45:46",
        {"path": "/org/bluez/hci0/dev_FA_23_9D_AA_45_46"},
    )
    manager = MagicMock()
    manager._wait_condition = AsyncMock(side_effect=RuntimeError("boom"))
    reappear_called = False

    async def fake_reappear(d, t):
        nonlocal reappear_called
        reappear_called = True

    with (
        patch(
            "bleak_retry_connector.bluez.get_global_bluez_manager_with_timeout",
            AsyncMock(return_value=manager),
        ),
        patch(
            "bleak_retry_connector.bluez.wait_for_device_to_reappear",
            side_effect=fake_reappear,
        ),
    ):
        await wait_for_disconnect(device, 0.1)

    assert reappear_called is False
    assert "Failed waiting for disconnect" in caplog.text


async def test_wait_for_device_to_reappear_debug_logging(mock_linux, caplog):
    """Debug-level branches in wait_for_device_to_reappear log per iteration."""
    import logging

    caplog.set_level(logging.DEBUG, logger="bleak_retry_connector.bluez")

    class BluezManager:
        # Non-empty so _get_properties() returns truthy, but the device path
        # is intentionally absent so the loop exhausts without finding it.
        _properties: dict[str, dict[str, dict[str, str]]] = {
            "/org/bluez/hci0/dev_OTHER": {defs.DEVICE_INTERFACE: {"Address": "x"}}
        }

        def is_connected(self, path):
            return False

    bleak_retry_connector.bleak_manager.get_global_bluez_manager = AsyncMock(
        return_value=BluezManager()
    )
    bleak_retry_connector.bluez.defs = defs

    device = BLEDevice(
        "FA:23:9D:AA:45:46",
        "FA:23:9D:AA:45:46",
        {"path": "/org/bluez/hci0/dev_FA_23_9D_AA_45_46"},
    )
    # Force the function-local `debug` flag True even if the logger level
    # isn't picked up via caplog (matches how real callers see it).
    with (
        patch.object(bleak_retry_connector.bluez, "REAPPEAR_WAIT_INTERVAL", 0.01),
        patch.object(
            bleak_retry_connector.bluez._LOGGER, "isEnabledFor", return_value=True
        ),
    ):
        result = await wait_for_device_to_reappear(device, 0.03)

    assert result is False
    assert "Waiting" in caplog.text
    assert "did not re-appear" in caplog.text


async def test_clear_cache_not_linux(mock_macos: None) -> None:
    """Non-Linux short-circuits and returns False."""
    assert await clear_cache("FA:23:9D:AA:45:46") is False


async def test_clear_cache_no_device(
    mock_linux: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """If get_device returns None, clear_cache returns False without touching cache."""
    monkeypatch.setattr(
        bleak_retry_connector.bleak_manager,
        "get_global_bluez_manager",
        AsyncMock(return_value=None),
    )
    monkeypatch.setattr(
        bleak_retry_connector.bleak_manager,
        "get_global_bluez_manager_with_timeout",
        AsyncMock(return_value=None),
    )
    assert await clear_cache("FA:23:9D:AA:45:46") is False


async def test_clear_cache_no_services_cache(
    mock_linux: None,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """get_device succeeds but services cache is unavailable → warn + False."""

    class FakeBluezManager:
        def __init__(self) -> None:
            self._properties = {
                "/org/bluez/hci0/dev_FA_23_9D_AA_45_46": {
                    defs.DEVICE_INTERFACE: {
                        "Address": "FA:23:9D:AA:45:46",
                        "Alias": "FA:23:9D:AA:45:46",
                    },
                },
            }

    manager = FakeBluezManager()
    monkeypatch.setattr(
        bleak_retry_connector.bleak_manager,
        "get_global_bluez_manager",
        AsyncMock(return_value=manager),
    )
    monkeypatch.setattr(
        bleak_retry_connector.bleak_manager,
        "get_global_bluez_manager_with_timeout",
        AsyncMock(return_value=manager),
    )
    monkeypatch.setattr(bleak_retry_connector.bluez, "defs", defs)
    monkeypatch.setattr(
        bleak_retry_connector.bluez,
        "_get_services_cache",
        AsyncMock(return_value=None),
    )

    assert await clear_cache("FA:23:9D:AA:45:46") is False
    assert "no services cache" in caplog.text


async def test_clear_cache_no_manager(
    mock_linux: None,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """services cache returns dict but the manager fetch fails → warn + False."""
    fake_device = BLEDevice(
        "FA:23:9D:AA:45:46",
        "FA:23:9D:AA:45:46",
        {"path": "/org/bluez/hci0/dev_FA_23_9D_AA_45_46"},
    )
    monkeypatch.setattr(
        bleak_retry_connector.bluez,
        "get_device",
        AsyncMock(return_value=fake_device),
    )
    monkeypatch.setattr(
        bleak_retry_connector.bluez,
        "_get_services_cache",
        AsyncMock(return_value={}),
    )
    monkeypatch.setattr(
        bleak_retry_connector.bluez,
        "get_global_bluez_manager_with_timeout",
        AsyncMock(return_value=None),
    )

    assert await clear_cache("FA:23:9D:AA:45:46") is False
    assert "no manager" in caplog.text


async def test_clear_cache_sends_remove_device(
    mock_linux: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Happy path: matching paths are popped from cache and RemoveDevice is sent."""
    sent_kwargs: list[dict[str, Any]] = []

    class FakeBus:
        async def send(self, message: Any) -> None:
            return None

    class FakeBluezManager:
        def __init__(self) -> None:
            self._bus = FakeBus()
            self._services_cache = {
                "/org/bluez/hci0/dev_FA_23_9D_AA_45_46": "svc0",
                "/org/bluez/hci1/dev_FA_23_9D_AA_45_46": "svc1",
            }
            self._properties = {
                "/org/bluez/hci0/dev_FA_23_9D_AA_45_46": {
                    defs.DEVICE_INTERFACE: {
                        "Address": "FA:23:9D:AA:45:46",
                        "Alias": "FA:23:9D:AA:45:46",
                        "RSSI": -30,
                    },
                },
                "/org/bluez/hci1/dev_FA_23_9D_AA_45_46": {
                    defs.DEVICE_INTERFACE: {
                        "Address": "FA:23:9D:AA:45:46",
                        "Alias": "FA:23:9D:AA:45:46",
                        "RSSI": -60,
                    },
                },
            }

    manager = FakeBluezManager()

    def _record_message(**kw: Any) -> dict[str, Any]:
        sent_kwargs.append(kw)
        return kw

    fake_message = MagicMock(side_effect=_record_message)
    monkeypatch.setattr(
        bleak_retry_connector.bleak_manager,
        "get_global_bluez_manager",
        AsyncMock(return_value=manager),
    )
    monkeypatch.setattr(
        bleak_retry_connector.bleak_manager,
        "get_global_bluez_manager_with_timeout",
        AsyncMock(return_value=manager),
    )
    monkeypatch.setattr(bleak_retry_connector.bluez, "defs", defs)
    monkeypatch.setattr(bleak_retry_connector.bluez, "Message", fake_message)

    assert await clear_cache("FA:23:9D:AA:45:46") is True
    assert manager._services_cache == {}
    assert len(sent_kwargs) == 2
    assert {kw["path"] for kw in sent_kwargs} == {"/org/bluez/hci0", "/org/bluez/hci1"}
    assert all(kw["member"] == "RemoveDevice" for kw in sent_kwargs)


async def test_get_device_by_adapter_not_linux(mock_macos):
    """Non-Linux returns None immediately."""
    assert await get_device_by_adapter("FA:23:9D:AA:45:46", "hci0") is None


async def test_get_device_by_adapter_no_properties(mock_linux):
    """No bluez manager yields no properties → returns None."""
    bleak_retry_connector.bleak_manager.get_global_bluez_manager = AsyncMock(
        return_value=None
    )
    bleak_retry_connector.bleak_manager.get_global_bluez_manager_with_timeout = (
        AsyncMock(return_value=None)
    )
    assert await get_device_by_adapter("FA:23:9D:AA:45:46", "hci0") is None


async def test_get_device_by_adapter_path_missing(mock_linux):
    """Path absent from properties → returns None."""

    class FakeBluezManager:
        def __init__(self):
            self._properties = {
                "/org/bluez/hci0/dev_AA_BB_CC_DD_EE_FF": {
                    defs.DEVICE_INTERFACE: {
                        "Address": "AA:BB:CC:DD:EE:FF",
                        "Alias": "AA:BB:CC:DD:EE:FF",
                    },
                },
            }

    manager = FakeBluezManager()
    bleak_retry_connector.bleak_manager.get_global_bluez_manager = AsyncMock(
        return_value=manager
    )
    bleak_retry_connector.bleak_manager.get_global_bluez_manager_with_timeout = (
        AsyncMock(return_value=manager)
    )
    bleak_retry_connector.bluez.defs = defs

    assert await get_device_by_adapter("FA:23:9D:AA:45:46", "hci0") is None


async def test_get_device_by_adapter_returns_device(mock_linux):
    """Matching adapter+address returns the BLEDevice."""

    class FakeBluezManager:
        def __init__(self):
            self._properties = {
                "/org/bluez/hci1/dev_FA_23_9D_AA_45_46": {
                    defs.DEVICE_INTERFACE: {
                        "Address": "FA:23:9D:AA:45:46",
                        "Alias": "Test Device",
                        "RSSI": -60,
                    },
                },
            }

    manager = FakeBluezManager()
    bleak_retry_connector.bleak_manager.get_global_bluez_manager = AsyncMock(
        return_value=manager
    )
    bleak_retry_connector.bleak_manager.get_global_bluez_manager_with_timeout = (
        AsyncMock(return_value=manager)
    )
    bleak_retry_connector.bluez.defs = defs

    device = await get_device_by_adapter("FA:23:9D:AA:45:46", "hci1")
    assert device is not None
    assert device.details["path"] == "/org/bluez/hci1/dev_FA_23_9D_AA_45_46"


async def test_get_bluez_device_no_properties(mock_linux):
    """No properties → returns None early."""
    bleak_retry_connector.bleak_manager.get_global_bluez_manager = AsyncMock(
        return_value=None
    )
    bleak_retry_connector.bleak_manager.get_global_bluez_manager_with_timeout = (
        AsyncMock(return_value=None)
    )
    assert (
        await get_bluez_device(
            "Test", "/org/bluez/hci0/dev_FA_23_9D_AA_45_46"
        )
        is None
    )


async def test_get_bluez_device_disappeared_logs(
    mock_linux, caplog: pytest.LogCaptureFixture
):
    """Device path missing from props logs the disappearance and still scans alternates."""

    class FakeBluezManager:
        def __init__(self):
            self._properties = {
                "/org/bluez/hci1/dev_FA_23_9D_AA_45_46": {
                    defs.DEVICE_INTERFACE: {
                        "Address": "FA:23:9D:AA:45:46",
                        "Alias": "Test Device",
                        "RSSI": -60,
                    },
                },
            }

    manager = FakeBluezManager()
    bleak_retry_connector.bleak_manager.get_global_bluez_manager = AsyncMock(
        return_value=manager
    )
    bleak_retry_connector.bleak_manager.get_global_bluez_manager_with_timeout = (
        AsyncMock(return_value=manager)
    )
    bleak_retry_connector.bluez.defs = defs

    device = await get_bluez_device(
        "Test", "/org/bluez/hci0/dev_FA_23_9D_AA_45_46"
    )
    assert device is not None
    assert device.details["path"] == "/org/bluez/hci1/dev_FA_23_9D_AA_45_46"
    assert "Device has disappeared" in caplog.text


async def test_get_bluez_device_disappeared_silent_when_flag_false(mock_linux, caplog):
    """`_log_disappearance=False` suppresses the disappearance log."""

    class FakeBluezManager:
        def __init__(self):
            self._properties = {
                "/org/bluez/hci1/dev_FA_23_9D_AA_45_46": {
                    defs.DEVICE_INTERFACE: {
                        "Address": "FA:23:9D:AA:45:46",
                        "Alias": "Test Device",
                        "RSSI": -60,
                    },
                },
            }

    manager = FakeBluezManager()
    bleak_retry_connector.bleak_manager.get_global_bluez_manager = AsyncMock(
        return_value=manager
    )
    bleak_retry_connector.bleak_manager.get_global_bluez_manager_with_timeout = (
        AsyncMock(return_value=manager)
    )
    bleak_retry_connector.bluez.defs = defs

    caplog.clear()
    await get_bluez_device(
        "Test",
        "/org/bluez/hci0/dev_FA_23_9D_AA_45_46",
        _log_disappearance=False,
    )
    assert "Device has disappeared" not in caplog.text


async def test_get_bluez_device_connected_at_original_path(mock_linux):
    """Device already connected at the requested path → returns None (use original)."""

    class FakeBluezManager:
        def __init__(self):
            self._properties = {
                "/org/bluez/hci0/dev_FA_23_9D_AA_45_46": {
                    defs.DEVICE_INTERFACE: {
                        "Connected": True,
                        "Address": "FA:23:9D:AA:45:46",
                        "Alias": "Test Device",
                        "RSSI": -30,
                    },
                },
            }

    manager = FakeBluezManager()
    bleak_retry_connector.bleak_manager.get_global_bluez_manager = AsyncMock(
        return_value=manager
    )
    bleak_retry_connector.bleak_manager.get_global_bluez_manager_with_timeout = (
        AsyncMock(return_value=manager)
    )
    bleak_retry_connector.bluez.defs = defs

    assert (
        await get_bluez_device(
            "Test", "/org/bluez/hci0/dev_FA_23_9D_AA_45_46"
        )
        is None
    )


async def test_get_bluez_device_skips_unconnected_original_path(mock_linux):
    """The original path is skipped during alternate scoring when not connected."""

    class FakeBluezManager:
        def __init__(self):
            self._properties = {
                "/org/bluez/hci0/dev_FA_23_9D_AA_45_46": {
                    defs.DEVICE_INTERFACE: {
                        "Address": "FA:23:9D:AA:45:46",
                        "Alias": "Test Device",
                        "RSSI": -80,
                    },
                },
                "/org/bluez/hci1/dev_FA_23_9D_AA_45_46": {
                    defs.DEVICE_INTERFACE: {
                        "Address": "FA:23:9D:AA:45:46",
                        "Alias": "Test Device",
                        "RSSI": -30,
                    },
                },
            }

    manager = FakeBluezManager()
    bleak_retry_connector.bleak_manager.get_global_bluez_manager = AsyncMock(
        return_value=manager
    )
    bleak_retry_connector.bleak_manager.get_global_bluez_manager_with_timeout = (
        AsyncMock(return_value=manager)
    )
    bleak_retry_connector.bluez.defs = defs

    device = await get_bluez_device(
        "Test", "/org/bluez/hci0/dev_FA_23_9D_AA_45_46", rssi=-90
    )
    assert device is not None
    assert device.details["path"] == "/org/bluez/hci1/dev_FA_23_9D_AA_45_46"


async def test_get_connected_devices_no_properties(mock_linux):
    """No properties → returns empty list."""
    bleak_retry_connector.bleak_manager.get_global_bluez_manager = AsyncMock(
        return_value=None
    )
    bleak_retry_connector.bleak_manager.get_global_bluez_manager_with_timeout = (
        AsyncMock(return_value=None)
    )
    device = BLEDevice(
        "FA:23:9D:AA:45:46",
        "Test",
        {"path": "/org/bluez/hci0/dev_FA_23_9D_AA_45_46"},
    )
    assert await get_connected_devices(device) == []
