from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from bleak.backends.bluezdbus import defs
from bleak.backends.device import BLEDevice

import bleak_retry_connector
from bleak_retry_connector.dbus import disconnect_devices

pytestmark = pytest.mark.asyncio


def _device(path: str | None = "/org/bluez/hci0/dev_FA_23_9D_AA_45_46") -> BLEDevice:
    details: dict[str, str] = {"source": "aa:bb:cc:dd:ee:ff"}
    if path is not None:
        details["path"] = path
    return BLEDevice("FA:23:9D:AA:45:46", "FA:23:9D:AA:45:46", details)


async def test_disconnect_devices_empty_list() -> None:
    """Empty list returns early without touching the bluez manager."""
    with patch(
        "bleak_retry_connector.dbus.get_global_bluez_manager_with_timeout",
        new=AsyncMock(),
    ) as mock_manager:
        await disconnect_devices([])
    mock_manager.assert_not_called()


async def test_disconnect_devices_filters_invalid_devices() -> None:
    """Devices without dict details or a 'path' key are skipped."""
    no_dict_details = BLEDevice("AA:BB", "AA:BB", "not-a-dict")
    no_path = BLEDevice("CC:DD", "CC:DD", {"source": "xx"})
    with patch(
        "bleak_retry_connector.dbus.get_global_bluez_manager_with_timeout",
        new=AsyncMock(),
    ) as mock_manager:
        await disconnect_devices([no_dict_details, no_path])
    mock_manager.assert_not_called()


async def test_disconnect_devices_no_bluez_manager() -> None:
    """If the bluez manager times out (returns None), do nothing."""
    with patch(
        "bleak_retry_connector.dbus.get_global_bluez_manager_with_timeout",
        new=AsyncMock(return_value=None),
    ):
        await disconnect_devices([_device()])


async def test_disconnect_devices_calls_bus_for_each_valid_device() -> None:
    """Each valid device gets a BlueZ Disconnect call with the right path."""
    bus = MagicMock()
    bus.call = AsyncMock()
    bluez_manager = MagicMock()
    bluez_manager._bus = bus

    device_a = _device("/org/bluez/hci0/dev_AA")
    device_b = _device("/org/bluez/hci0/dev_BB")
    invalid = BLEDevice("EE:FF", "EE:FF", {"source": "x"})

    fake_message_cls = MagicMock()
    with (
        patch(
            "bleak_retry_connector.dbus.get_global_bluez_manager_with_timeout",
            new=AsyncMock(return_value=bluez_manager),
        ),
        patch("bleak_retry_connector.dbus.Message", new=fake_message_cls),
    ):
        await disconnect_devices([device_a, invalid, device_b])

    assert bus.call.await_count == 2
    paths = [
        kwargs["path"] if "path" in kwargs else args[0]
        for args, kwargs in [(call.args, call.kwargs) for call in fake_message_cls.call_args_list]
    ]
    assert paths == ["/org/bluez/hci0/dev_AA", "/org/bluez/hci0/dev_BB"]
    for call in fake_message_cls.call_args_list:
        assert call.kwargs["destination"] == defs.BLUEZ_SERVICE
        assert call.kwargs["interface"] == defs.DEVICE_INTERFACE
        assert call.kwargs["member"] == "Disconnect"


async def test_disconnect_devices_suppresses_exceptions() -> None:
    """An exception from bus.call must not stop the loop."""
    bus = MagicMock()
    bus.call = AsyncMock(side_effect=RuntimeError("boom"))
    bluez_manager = MagicMock()
    bluez_manager._bus = bus

    devices = [_device("/org/bluez/hci0/dev_A"), _device("/org/bluez/hci0/dev_B")]

    with (
        patch(
            "bleak_retry_connector.dbus.get_global_bluez_manager_with_timeout",
            new=AsyncMock(return_value=bluez_manager),
        ),
        patch("bleak_retry_connector.dbus.Message", new=MagicMock()),
    ):
        await disconnect_devices(devices)

    assert bus.call.await_count == 2


async def test_disconnect_devices_suppresses_timeout() -> None:
    """A timeout from the inner asyncio_timeout context must be suppressed."""
    import asyncio

    async def slow(*args, **kwargs):
        await asyncio.sleep(10)

    bus = MagicMock()
    bus.call = AsyncMock(side_effect=slow)
    bluez_manager = MagicMock()
    bluez_manager._bus = bus

    with (
        patch(
            "bleak_retry_connector.dbus.get_global_bluez_manager_with_timeout",
            new=AsyncMock(return_value=bluez_manager),
        ),
        patch("bleak_retry_connector.dbus.Message", new=MagicMock()),
        patch("bleak_retry_connector.dbus.DISCONNECT_TIMEOUT", 0.01),
    ):
        await disconnect_devices([_device()])

    assert bus.call.await_count == 1
