from typing import Any
from unittest.mock import AsyncMock

import pytest
from bleak.backends.bluezdbus import defs
from bleak.backends.bluezdbus.manager import DeviceWatcher

import bleak_retry_connector
from bleak_retry_connector import BleakSlotManager
from bleak_retry_connector.bluez import ble_device_from_properties

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

    bleak_retry_connector.bluez.get_global_bluez_manager = AsyncMock(
        return_value=FakeBluezManager()
    )
    bleak_retry_connector.bluez.defs = defs

    slot_manager = BleakSlotManager()

    await slot_manager.async_setup()
    slot_manager.register_adapter("hci0", 1)
    slot_manager.register_adapter("hci1", 2)
    slot_manager.register_adapter("hci2", 1)

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
    # Make sure we can allocate an already connected device
    # since there is always a race condition between the
    # slot manager and the device connecting
    assert slot_manager.allocate_slot(ble_device_hci2_already_connected) is True

    assert slot_manager.allocate_slot(ble_device_hci0) is True
    assert slot_manager._get_allocations("hci0") == [
        "/org/bluez/hci0/dev_FA_23_9D_AA_45_46"
    ]

    # Make sure we can allocate the same device again
    assert slot_manager.allocate_slot(ble_device_hci0) is True
    assert slot_manager._get_allocations("hci0") == [
        "/org/bluez/hci0/dev_FA_23_9D_AA_45_46"
    ]

    assert slot_manager.allocate_slot(ble_device_hci0_2) is False
    assert slot_manager._get_allocations("hci0") == [
        "/org/bluez/hci0/dev_FA_23_9D_AA_45_46"
    ]

    watcher: DeviceWatcher = slot_manager._allocations_by_adapter["hci0"][
        "/org/bluez/hci0/dev_FA_23_9D_AA_45_46"
    ]
    watcher.on_connected_changed(True)
    assert slot_manager._get_allocations("hci0") == [
        "/org/bluez/hci0/dev_FA_23_9D_AA_45_46"
    ]

    watcher.on_connected_changed(False)
    assert slot_manager._get_allocations("hci0") == []

    assert slot_manager.allocate_slot(ble_device_hci0) is True
    assert slot_manager._get_allocations("hci0") == [
        "/org/bluez/hci0/dev_FA_23_9D_AA_45_46"
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
    assert slot_manager._get_allocations("hci0") == []

    assert slot_manager.allocate_slot(ble_device_hci0) is True
    assert slot_manager._get_allocations("hci0") == [
        "/org/bluez/hci0/dev_FA_23_9D_AA_45_46"
    ]
    slot_manager.remove_adapter("hci0")
    assert slot_manager.allocate_slot(ble_device_hci0) is True
    assert slot_manager.allocate_slot(ble_device_hci0_2) is True


async def test_slot_manager_mac_os():
    """Test the slot manager"""

    bleak_retry_connector.bluez.get_global_bluez_manager = AsyncMock(return_value=None)
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
