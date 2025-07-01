from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from bleak.backends.bluezdbus import defs
from bleak.backends.bluezdbus.manager import DeviceWatcher
from bleak.backends.device import BLEDevice

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
    path_from_ble_device,
    stop_discovery,
    wait_for_device_to_reappear,
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


def test_device_source():
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


def test_path_from_ble_device():
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
