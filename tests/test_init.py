from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from bleak import BleakClient, BleakError
from bleak.backends.bluezdbus import defs
from bleak.backends.bluezdbus.manager import DeviceWatcher
from bleak.backends.device import BLEDevice
from bleak.backends.scanner import AdvertisementData
from bleak.backends.service import BleakGATTService, BleakGATTServiceCollection
from bleak.exc import BleakDBusError, BleakDeviceNotFoundError

import bleak_retry_connector
from bleak_retry_connector import (
    BLEAK_BACKOFF_TIME,
    BLEAK_DBUS_BACKOFF_TIME,
    BLEAK_OUT_OF_SLOTS_BACKOFF_TIME,
    BLEAK_TRANSIENT_BACKOFF_TIME,
    BLEAK_TRANSIENT_LONG_BACKOFF_TIME,
    BLEAK_TRANSIENT_MEDIUM_BACKOFF_TIME,
    MAX_TRANSIENT_ERRORS,
    BleakAbortedError,
    BleakClientWithServiceCache,
    BleakConnectionError,
    BleakNotFoundError,
    BleakOutOfConnectionSlotsError,
    ble_device_description,
    ble_device_has_changed,
    calculate_backoff_time,
    clear_cache,
    close_stale_connections_by_address,
    establish_connection,
    get_connected_devices,
    get_device,
    get_device_by_adapter,
    restore_discoveries,
    retry_bluetooth_connection_error,
)
from bleak_retry_connector.bleak_manager import _reset_dbus_socket_cache


@pytest.mark.asyncio
async def test_establish_connection_works_first_time():
    class FakeBleakClient(BleakClient):
        async def connect(self, *args, **kwargs):
            pass

        async def disconnect(self, *args, **kwargs):
            pass

    client = await establish_connection(
        FakeBleakClient, MagicMock(), "test", disconnected_callback=MagicMock()
    )
    assert isinstance(client, FakeBleakClient)


@pytest.mark.asyncio
async def test_establish_connection_passes_retry_client_flag():
    """Test that establish_connection passes _is_retry_client=True to the client."""
    received_kwargs = {}

    class FakeBleakClient(BleakClient):
        def __init__(self, *args, **kwargs):
            # Capture the kwargs passed to __init__
            received_kwargs.update(kwargs)
            # Remove _is_retry_client before calling super() if it exists
            # since the base BleakClient doesn't expect it
            kwargs.pop("_is_retry_client", None)
            # Don't call super().__init__ to avoid platform-specific initialization
            self._device_path = None
            self._device_info = None
            self._backend = None

        async def connect(self, *args, **kwargs):
            pass

        async def disconnect(self, *args, **kwargs):
            pass

    device = MagicMock(spec=BLEDevice)
    device.address = "00:00:00:00:00:01"

    client = await establish_connection(
        FakeBleakClient, device, "test", disconnected_callback=MagicMock()
    )

    assert isinstance(client, FakeBleakClient)
    assert "_is_retry_client" in received_kwargs
    assert received_kwargs["_is_retry_client"] is True


@pytest.mark.asyncio
async def test_establish_connection_with_cached_services():
    class FakeBleakClient(BleakClient):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self._device_path = "/dev/test"

        async def connect(self, *args, **kwargs):
            return True

        async def disconnect(self, *args, **kwargs):
            pass

        async def get_services(self, *args, **kwargs):
            return []

    class FakeBleakClientWithServiceCache(BleakClientWithServiceCache, FakeBleakClient):
        """Fake BleakClientWithServiceCache."""

        async def get_services(self, *args, **kwargs):
            return []

    collection = BleakGATTServiceCollection()

    class FakeBluezManager:
        def __init__(self):
            self._services_cache = {}
            self._properties = {
                "/dev/test/service/1": {
                    "UUID": "service",
                    "Primary": True,
                    "Characteristics": [],
                    defs.GATT_SERVICE_INTERFACE: True,
                },
            }

    bluez_manager = FakeBluezManager()

    bleak_retry_connector.bleak_manager.get_global_bluez_manager = AsyncMock(
        return_value=bluez_manager
    )

    bleak_retry_connector.bleak_manager.get_global_bluez_manager_with_timeout = (
        AsyncMock(return_value=bluez_manager)
    )
    bleak_retry_connector.bluez.defs = defs

    client = await establish_connection(
        FakeBleakClientWithServiceCache,
        MagicMock(),
        "test",
        disconnected_callback=MagicMock(),
        cached_services=collection,
    )

    assert isinstance(client, FakeBleakClientWithServiceCache)
    await client.get_services() is collection


@pytest.mark.asyncio
async def test_establish_connection_with_cached_services_that_have_vanished():
    class FakeBleakClient(BleakClient):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self._device_path = "/dev/test"

        async def connect(self, *args, **kwargs):
            return True

        async def disconnect(self, *args, **kwargs):
            pass

        async def get_services(self, *args, **kwargs):
            return []

    class FakeBleakClientWithServiceCache(BleakClientWithServiceCache, FakeBleakClient):
        """Fake BleakClientWithServiceCache."""

        async def get_services(self, *args, **kwargs):
            return []

    collection = BleakGATTServiceCollection()

    class FakeBluezManager:
        def __init__(self):
            self._services_cache = {}
            self._properties = {}

    bluez_manager = FakeBluezManager()

    bleak_retry_connector.bleak_manager.get_global_bluez_manager = AsyncMock(
        return_value=bluez_manager
    )

    bleak_retry_connector.bleak_manager.get_global_bluez_manager_with_timeout = (
        AsyncMock(return_value=bluez_manager)
    )
    bleak_retry_connector.bluez.defs = defs

    client = await establish_connection(
        FakeBleakClientWithServiceCache,
        MagicMock(),
        "test",
        disconnected_callback=MagicMock(),
        cached_services=collection,
    )

    assert isinstance(client, FakeBleakClientWithServiceCache)
    await client.get_services() is collection


@pytest.mark.asyncio
async def test_establish_connection_can_cache_services_always_patched():
    class FakeBleakClient(BleakClient):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self._device_path = "/dev/test"

        async def connect(self, *args, **kwargs):
            return True

        async def disconnect(self, *args, **kwargs):
            pass

        async def get_services(self, *args, **kwargs):
            return []

    class FakeBleakClientWithServiceCache(BleakClientWithServiceCache, FakeBleakClient):
        """Fake BleakClientWithServiceCache."""

    collection = BleakGATTServiceCollection()

    class FakeBluezManager:
        def __init__(self):
            self._services_cache = {}
            self._properties = {
                "/dev/test/service/1": {
                    "UUID": "service",
                    "Primary": True,
                    "Characteristics": [],
                    defs.GATT_SERVICE_INTERFACE: True,
                },
            }

    bluez_manager = FakeBluezManager()

    bleak_retry_connector.bleak_manager.get_global_bluez_manager = AsyncMock(
        return_value=bluez_manager
    )

    bleak_retry_connector.bleak_manager.get_global_bluez_manager_with_timeout = (
        AsyncMock(return_value=bluez_manager)
    )
    bleak_retry_connector.bluez.defs = defs

    client = await establish_connection(
        FakeBleakClientWithServiceCache,
        MagicMock(),
        "test",
        disconnected_callback=MagicMock(),
        cached_services=collection,
    )

    assert isinstance(client, FakeBleakClientWithServiceCache)
    await client.get_services() is collection


@pytest.mark.asyncio
async def test_establish_connection_can_cache_services_services_missing():
    class FakeBleakClient(BleakClient):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self._device_path = "/dev/test"

        async def connect(self, *args, **kwargs):
            return True

        async def disconnect(self, *args, **kwargs):
            pass

        async def get_services(self, *args, **kwargs):
            return []

    class FakeBleakClientWithServiceCache(BleakClientWithServiceCache, FakeBleakClient):
        """Fake BleakClientWithServiceCache."""

    collection = BleakGATTServiceCollection()

    class FakeBluezManager:
        def __init__(self):
            self._services_cache = {}
            self._properties = {
                "/dev/test2/service/1": {
                    "UUID": "service",
                    "Primary": True,
                    "Characteristics": [],
                },
            }

    bluez_manager = FakeBluezManager()

    bleak_retry_connector.bleak_manager.get_global_bluez_manager = AsyncMock(
        return_value=bluez_manager
    )

    bleak_retry_connector.bleak_manager.get_global_bluez_manager_with_timeout = (
        AsyncMock(return_value=bluez_manager)
    )
    bleak_retry_connector.bluez.defs = defs

    client = await establish_connection(
        FakeBleakClientWithServiceCache,
        MagicMock(),
        "test",
        disconnected_callback=MagicMock(),
        cached_services=collection,
    )

    assert isinstance(client, FakeBleakClientWithServiceCache)
    await client.get_services() is collection


@pytest.mark.asyncio
async def test_establish_connection_can_cache_services_newer_bleak():
    class FakeBleakClient(BleakClient):
        async def connect(self, *args, **kwargs):
            return True

        async def disconnect(self, *args, **kwargs):
            pass

        async def get_services(self, *args, **kwargs):
            return []

    class FakeBleakClientWithServiceCache(BleakClientWithServiceCache, FakeBleakClient):
        """Fake BleakClientWithServiceCache."""

    collection = BleakGATTServiceCollection()

    client = await establish_connection(
        FakeBleakClientWithServiceCache,
        MagicMock(),
        "test",
        disconnected_callback=MagicMock(),
        cached_services=collection,
    )

    assert isinstance(client, FakeBleakClientWithServiceCache)
    await client.get_services() is collection


@pytest.mark.asyncio
async def test_establish_connection_with_dangerous_use_cached_services():
    class FakeBleakClient(BleakClient):
        async def connect(self, *args, **kwargs):
            return True

        async def disconnect(self, *args, **kwargs):
            pass

        async def get_services(self, *args, **kwargs):
            return []

    class FakeBleakClientWithServiceCache(BleakClientWithServiceCache, FakeBleakClient):
        """Fake BleakClientWithServiceCache."""

    client = await establish_connection(
        FakeBleakClientWithServiceCache,
        MagicMock(),
        "test",
        disconnected_callback=MagicMock(),
    )

    assert isinstance(client, FakeBleakClientWithServiceCache)


@pytest.mark.asyncio
async def test_establish_connection_without_dangerous_use_cached_services():
    class FakeBleakClient(BleakClient):
        async def connect(self, *args, **kwargs):
            return True

        async def disconnect(self, *args, **kwargs):
            pass

        async def get_services(self, *args, **kwargs):
            return []

    class FakeBleakClientWithServiceCache(BleakClientWithServiceCache, FakeBleakClient):
        """Fake BleakClientWithServiceCache."""

    client = await establish_connection(
        FakeBleakClientWithServiceCache,
        MagicMock(),
        "test",
        disconnected_callback=MagicMock(),
    )

    assert isinstance(client, FakeBleakClientWithServiceCache)


@pytest.mark.asyncio
async def test_establish_connection_fails():
    class FakeBleakClient(BleakClient):
        def __init__(self, *args, **kwargs):
            pass

        async def connect(self, *args, **kwargs):
            raise BleakError("test")
            pass

        async def disconnect(self, *args, **kwargs):
            pass

    with (
        patch("bleak_retry_connector.calculate_backoff_time", return_value=0),
        pytest.raises(BleakConnectionError),
    ):
        await establish_connection(FakeBleakClient, MagicMock(), "test")


@pytest.mark.asyncio
async def test_establish_connection_times_out():
    class FakeBleakClient(BleakClient):
        def __init__(self, *args, **kwargs):
            pass

        async def connect(self, *args, **kwargs):
            raise asyncio.TimeoutError()

        async def disconnect(self, *args, **kwargs):
            pass

    with (
        patch("bleak_retry_connector.calculate_backoff_time", return_value=0),
        pytest.raises(BleakNotFoundError),
    ):
        await establish_connection(FakeBleakClient, MagicMock(), "test")


@pytest.mark.asyncio
async def test_establish_connection_has_transient_error():
    attempts = 0

    class FakeBleakClient(BleakClient):
        def __init__(self, *args, **kwargs):
            pass

        async def connect(self, *args, **kwargs):
            nonlocal attempts
            attempts += 1
            if attempts < MAX_TRANSIENT_ERRORS:
                raise BleakError("le-connection-abort-by-local")
            pass

        async def disconnect(self, *args, **kwargs):
            pass

    with patch("bleak_retry_connector.calculate_backoff_time", return_value=0):
        client = await establish_connection(FakeBleakClient, MagicMock(), "test")
    assert isinstance(client, FakeBleakClient)
    assert attempts == 9


@pytest.mark.asyncio
async def test_establish_connection_has_transient_broken_pipe_error():
    attempts = 0

    class FakeBleakClient(BleakClient):
        def __init__(self, *args, **kwargs):
            pass

        async def connect(self, *args, **kwargs):
            nonlocal attempts
            attempts += 1
            if attempts < MAX_TRANSIENT_ERRORS:
                raise BrokenPipeError
            pass

        async def disconnect(self, *args, **kwargs):
            pass

    client = await establish_connection(FakeBleakClient, MagicMock(), "test")
    assert isinstance(client, FakeBleakClient)
    assert attempts == 9


@pytest.mark.asyncio
async def test_establish_connection_services_changed():
    attempts = 0
    disconnect_calls = 0
    clear_cache_calls = 0

    class FakeBleakClient(BleakClientWithServiceCache):
        def __init__(self, *args, **kwargs):
            pass

        async def connect(self, *args, **kwargs):
            nonlocal attempts
            attempts += 1
            if attempts < MAX_TRANSIENT_ERRORS:
                raise KeyError

        async def disconnect(self, *args, **kwargs):
            nonlocal disconnect_calls
            disconnect_calls += 1

        async def clear_cache(self) -> bool:
            nonlocal clear_cache_calls
            clear_cache_calls += 1
            return True

    client = await establish_connection(FakeBleakClient, MagicMock(), "test")
    assert isinstance(client, FakeBleakClient)
    assert attempts == 9
    assert disconnect_calls == 8
    assert clear_cache_calls == 8


@pytest.mark.asyncio
async def test_establish_connection_has_transient_error_had_advice():
    class FakeBleakClient(BleakClient):
        def __init__(self, *args, **kwargs):
            pass

        async def connect(self, *args, **kwargs):
            raise BleakError("le-connection-abort-by-local")

        async def disconnect(self, *args, **kwargs):
            pass

    with patch("bleak_retry_connector.calculate_backoff_time", return_value=0):
        try:
            await establish_connection(
                FakeBleakClient,
                BLEDevice(
                    "aa:bb:cc:dd:ee:ff",
                    "name",
                    {"path": "/org/bluez/hci2/dev_FA_23_9D_AA_45_46"},
                ),
                "test",
            )
        except BleakError as e:
            exc = e

    assert isinstance(exc, BleakAbortedError)
    assert str(exc) == (
        "test - aa:bb:cc:dd:ee:ff: "
        "Failed to connect after 9 attempt(s): "
        "le-connection-abort-by-local: "
        "Interference/range; "
        "External Bluetooth adapter w/extension may help; "
        "Extension cables reduce USB 3 port interference"
    )


@pytest.mark.asyncio
async def test_establish_connection_out_of_slots_advice():
    class FakeBleakClient(BleakClient):
        def __init__(self, *args, **kwargs):
            pass

        async def connect(self, *args, **kwargs):
            raise BleakError("out of connection slots")

        async def disconnect(self, *args, **kwargs):
            pass

    with patch("bleak_retry_connector.calculate_backoff_time", return_value=0):
        try:
            await establish_connection(
                FakeBleakClient,
                BLEDevice("aa:bb:cc:dd:ee:ff", "name", {"source": "esphome_proxy_1"}),
                "test",
            )
        except BleakError as e:
            exc = e

    assert isinstance(exc, BleakOutOfConnectionSlotsError)
    assert str(exc) == (
        "test - aa:bb:cc:dd:ee:ff: Failed to connect after 9 attempt(s): "
        "out of connection slots: The proxy/adapter is "
        "out of connection slots or the device is no "
        "longer reachable; Add additional proxies "
        "(https://esphome.github.io/bluetooth-proxies/) near this device"
    )


@pytest.mark.asyncio
async def test_establish_connection_esp_gatt_conn_conn_cancel_out_of_slots():
    """Test ESP_GATT_CONN_CONN_CANCEL is treated as out of slots error."""

    class FakeBleakClient(BleakClient):
        def __init__(self, *args, **kwargs):
            pass

        async def connect(self, *args, **kwargs):
            raise BleakError("ESP_GATT_CONN_CONN_CANCEL")

        async def disconnect(self, *args, **kwargs):
            pass

    with patch("bleak_retry_connector.calculate_backoff_time", return_value=0):
        try:
            await establish_connection(
                FakeBleakClient,
                BLEDevice("aa:bb:cc:dd:ee:ff", "name", {"source": "esphome_proxy_1"}),
                "test",
            )
        except BleakError as e:
            exc = e

    assert isinstance(exc, BleakOutOfConnectionSlotsError)
    assert str(exc) == (
        "test - aa:bb:cc:dd:ee:ff: Failed to connect after 9 attempt(s): "
        "ESP_GATT_CONN_CONN_CANCEL: The proxy/adapter is "
        "out of connection slots or the device is no "
        "longer reachable; Add additional proxies "
        "(https://esphome.github.io/bluetooth-proxies/) near this device"
    )


@pytest.mark.asyncio
async def test_device_disappeared_error():
    class FakeBleakClient(BleakClient):
        def __init__(self, *args, **kwargs):
            pass

        async def connect(self, *args, **kwargs):
            raise BleakError(
                '[org.freedesktop.DBus.Error.UnknownObject] Method "Connect" with '
                'signature "" on interface '
                '"org.bluez.Device1" '
                "doesn't exist"
            )

        async def disconnect(self, *args, **kwargs):
            pass

    with patch("bleak_retry_connector.calculate_backoff_time", return_value=0):
        try:
            await establish_connection(
                FakeBleakClient,
                BLEDevice(
                    "aa:bb:cc:dd:ee:ff",
                    "name",
                    {"path": "/org/bluez/hci2/dev_FA_23_9D_AA_45_46"},
                ),
                "test",
            )
        except BleakError as e:
            exc = e

    assert isinstance(exc, BleakNotFoundError)
    assert str(exc) == (
        "test - aa:bb:cc:dd:ee:ff: "
        "Failed to connect after 4 attempt(s): "
        "[org.freedesktop.DBus.Error.UnknownObject] "
        'Method "Connect" with signature "" on interface "org.bluez.Device1" '
        "doesn't exist: The device disappeared; "
        "Try restarting the scanner or moving the device closer"
    )


@pytest.mark.asyncio
@patch.object(bleak_retry_connector.bluez, "IS_LINUX", True)
async def test_device_disappeared_and_reappears():
    class FakeBluezManager:
        def __init__(self):
            self._services_cache = {}
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

        async def _wait_condition(self, *args: Any, **kwargs: Any) -> None:
            """Wait for a condition to be met."""
            raise KeyError

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
    bleak_retry_connector.bleak_manager.get_global_bluez_manager_with_timeout = (
        AsyncMock(return_value=bluez_manager)
    )
    bleak_retry_connector.bluez.defs = defs

    class FakeBleakClient(BleakClient):
        def __init__(self, *args, **kwargs):
            pass

        async def connect(self, *args, **kwargs):
            raise BleakDeviceNotFoundError(
                '[org.freedesktop.DBus.Error.UnknownObject] Method "Connect" with '
                'signature "" on interface '
                '"org.bluez.Device1" '
                "doesn't exist"
            )

        async def disconnect(self, *args, **kwargs):
            pass

    with (
        patch("bleak_retry_connector.calculate_backoff_time", return_value=0.01),
        patch.object(bleak_retry_connector.bluez, "REAPPEAR_WAIT_INTERVAL", 0.0025),
    ):
        try:
            await establish_connection(
                FakeBleakClient,
                BLEDevice(
                    "FA:23:9D:AA:45:46",
                    "name",
                    {"path": "/org/bluez/hci2/dev_FA_23_9D_AA_45_46"},
                ),
                "test",
            )
        except BleakError as e:
            exc = e

    assert isinstance(exc, BleakNotFoundError)
    assert str(exc) == (
        "test - FA:23:9D:AA:45:46: "
        "Failed to connect after 9 attempt(s): "
        "BleakDeviceNotFoundError: "
        "The device disappeared; "
        "Try restarting the scanner or moving the device closer"
    )


@pytest.mark.asyncio
async def test_establish_connection_has_one_unknown_error():
    attempts = 0

    class FakeBleakClient(BleakClient):
        def __init__(self, *args, **kwargs):
            pass

        async def connect(self, *args, **kwargs):
            nonlocal attempts
            attempts += 1
            if attempts == 1:
                raise BleakError("unknown")
            pass

        async def disconnect(self, *args, **kwargs):
            pass

    client = await establish_connection(FakeBleakClient, MagicMock(), "test")
    assert isinstance(client, FakeBleakClient)
    assert attempts == 2


@pytest.mark.asyncio
async def test_establish_connection_has_one_many_error():
    attempts = 0

    class FakeBleakClient(BleakClient):
        def __init__(self, *args, **kwargs):
            pass

        async def connect(self, *args, **kwargs):
            nonlocal attempts
            attempts += 1
            if attempts < 10:
                raise BleakError("unknown")
            pass

        async def disconnect(self, *args, **kwargs):
            pass

    with (
        patch("bleak_retry_connector.calculate_backoff_time", return_value=0),
        pytest.raises(BleakConnectionError),
    ):
        await establish_connection(FakeBleakClient, MagicMock(), "test")


@pytest.mark.asyncio
async def test_bleak_connect_overruns_timeout():
    class FakeBleakClient(BleakClient):
        def __init__(self, *args, **kwargs):
            pass

        async def connect(self, *args, **kwargs):
            await asyncio.sleep(40)

        async def disconnect(self, *args, **kwargs):
            pass

    with (
        patch("bleak_retry_connector.calculate_backoff_time", return_value=0),
        patch.object(bleak_retry_connector, "BLEAK_SAFETY_TIMEOUT", 0),
        pytest.raises(BleakNotFoundError),
    ):
        await establish_connection(FakeBleakClient, MagicMock(), "test")


def test_ble_device_has_changed():
    """Test that the BLEDevice has changed when the underlying device has changed."""
    assert not ble_device_has_changed(
        BLEDevice("aa:bb:cc:dd:ee:ff", "name", {"path": "/dev/1"}),
        BLEDevice("aa:bb:cc:dd:ee:ff", "name", {"path": "/dev/1"}),
    )
    assert ble_device_has_changed(
        BLEDevice("aa:bb:cc:dd:ee:ff", "name", {"path": "/dev/1"}),
        BLEDevice("ab:bb:cc:dd:ee:ff", "name", {"path": "/dev/1"}),
    )
    assert ble_device_has_changed(
        BLEDevice("aa:bb:cc:dd:ee:ff", "name", {"path": "/dev/1"}),
        BLEDevice("aa:bb:cc:dd:ee:ff", "name", {"path": "/dev/2"}),
    )


@pytest.mark.asyncio
async def test_establish_connection_other_adapter_already_connected(mock_linux):
    device: BLEDevice | None = None

    class FakeBleakClient(BleakClient):
        def __init__(self, ble_device_or_address, *args, **kwargs):
            ble_device_or_address.details["delegate"] = 0
            super().__init__(ble_device_or_address, *args, **kwargs)
            nonlocal device
            device = ble_device_or_address
            self._device_path = "/org/bluez/hci2/dev_FA_23_9D_AA_45_46"

        async def connect(self, *args, **kwargs):
            return True

        async def disconnect(self, *args, **kwargs):
            pass

        async def get_services(self, *args, **kwargs):
            return []

    class FakeBleakClientWithServiceCache(BleakClientWithServiceCache, FakeBleakClient):
        """Fake BleakClientWithServiceCache."""

        async def get_services(self, *args, **kwargs):
            return []

    collection = BleakGATTServiceCollection()

    class FakeBluezManager:
        def __init__(self):
            self._services_cache = {}
            self._properties = {
                "/org/bluez/hci0/dev_FA_23_9D_AA_45_46": {
                    "UUID": "service",
                    "Primary": True,
                    "Characteristics": [],
                    defs.DEVICE_INTERFACE: {
                        "Address": "FA:23:9D:AA:45:46",
                        "Alias": "FA:23:9D_AA:45:46",
                        "RSSI": -30,
                    },
                    defs.GATT_SERVICE_INTERFACE: True,
                },
                "/org/bluez/hci1/dev_FA_23_9D_AA_45_46": {
                    "UUID": "service",
                    "Primary": True,
                    "Characteristics": [],
                    defs.DEVICE_INTERFACE: {
                        "Address": "FA:23:9D:AA:45:46",
                        "Alias": "FA:23:9D:AA:45:46",
                        "Connected": True,
                        "RSSI": -79,
                    },
                    defs.GATT_SERVICE_INTERFACE: True,
                },
                "/org/bluez/hci2/dev_FA_23_9D_AA_45_46": {
                    "UUID": "service",
                    "Primary": True,
                    "Characteristics": [],
                    defs.DEVICE_INTERFACE: {
                        "Address": "FA:23:9D:AA:45:46",
                        "Alias": "FA:23:9D:AA:45:46",
                        "Connected": False,
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

    bluez_manager = FakeBluezManager()
    bleak_retry_connector.bleak_manager.get_global_bluez_manager = AsyncMock(
        return_value=bluez_manager
    )
    bleak_retry_connector.bleak_manager.get_global_bluez_manager_with_timeout = (
        AsyncMock(return_value=bluez_manager)
    )
    bleak_retry_connector.bluez.defs = defs

    client = await establish_connection(
        FakeBleakClientWithServiceCache,
        BLEDevice(
            "aa:bb:cc:dd:ee:ff",
            "name",
            {"path": "/org/bluez/hci2/dev_FA_23_9D_AA_45_46"},
            delegate=False,
        ),
        "test",
        disconnected_callback=MagicMock(),
        cached_services=collection,
    )

    assert isinstance(client, FakeBleakClientWithServiceCache)
    await client.get_services() is collection
    assert device is not None
    assert device.details["path"] == "/org/bluez/hci1/dev_FA_23_9D_AA_45_46"


@pytest.mark.asyncio
async def test_establish_connection_device_disappeared(mock_linux):
    class FakeBleakClient(BleakClient):
        def __init__(self, ble_device_or_address, *args, **kwargs):
            ble_device_or_address.details["delegate"] = 0
            super().__init__(ble_device_or_address, *args, **kwargs)
            self._device_path = "/org/bluez/hci2/dev_FA_23_9D_AA_45_46"

        async def connect(self, *args, **kwargs):
            return True

        async def disconnect(self, *args, **kwargs):
            pass

        async def get_services(self, *args, **kwargs):
            return []

    class FakeBleakClientWithServiceCache(BleakClientWithServiceCache, FakeBleakClient):
        """Fake BleakClientWithServiceCache."""

        async def get_services(self, *args, **kwargs):
            return []

    collection = BleakGATTServiceCollection()

    class FakeBluezManager:
        def __init__(self):
            self._services_cache = {}
            self._properties = {
                "/org/bluez/hci0/dev_FA_23_9D_AA_45_46": {
                    "UUID": "service",
                    "Primary": True,
                    "Characteristics": [],
                    defs.DEVICE_INTERFACE: {
                        "Address": "FA:23:9D:AA:45:46",
                        "Alias": "bob",
                        "RSSI": -30,
                    },
                    defs.GATT_SERVICE_INTERFACE: True,
                },
            }

    bluez_manager = FakeBluezManager()

    bleak_retry_connector.bleak_manager.get_global_bluez_manager = AsyncMock(
        return_value=bluez_manager
    )

    bleak_retry_connector.bleak_manager.get_global_bluez_manager_with_timeout = (
        AsyncMock(return_value=bluez_manager)
    )
    bleak_retry_connector.bluez.defs = defs

    with patch("bleak_retry_connector.calculate_backoff_time", return_value=0):
        client = await establish_connection(
            FakeBleakClientWithServiceCache,
            BLEDevice(
                "aa:bb:cc:dd:ee:ff",
                "name",
                {"path": "/org/bluez/hci2/dev_FA_23_9D_AA_45_46"},
                delegate=False,
            ),
            "test",
            disconnected_callback=MagicMock(),
            cached_services=collection,
        )

    assert isinstance(client, FakeBleakClientWithServiceCache)
    await client.get_services() is collection


@pytest.mark.asyncio
async def test_get_device(mock_linux):
    class FakeBluezManager:
        def __init__(self):
            self._services_cache = {}
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

    bluez_manager = FakeBluezManager()

    bleak_retry_connector.bleak_manager.get_global_bluez_manager = AsyncMock(
        return_value=bluez_manager
    )

    bleak_retry_connector.bleak_manager.get_global_bluez_manager_with_timeout = (
        AsyncMock(return_value=bluez_manager)
    )
    bleak_retry_connector.bluez.defs = defs

    device = await get_device("FA:23:9D:AA:45:46")

    assert device is not None
    assert device.details["path"] == "/org/bluez/hci0/dev_FA_23_9D_AA_45_46"


@pytest.mark.asyncio
async def test_clear_cache(mock_linux):
    class FakeBluezManager:
        def __init__(self):
            self._services_cache = {
                "/org/bluez/hci0/dev_FA_23_9D_AA_45_46": "test",
                "/org/bluez/hci1/dev_FA_23_9D_AA_45_46": "test",
            }
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

    bluez_manager = FakeBluezManager()

    bleak_retry_connector.bleak_manager.get_global_bluez_manager = AsyncMock(
        return_value=bluez_manager
    )
    bleak_retry_connector.bleak_manager.get_global_bluez_manager_with_timeout = (
        AsyncMock(return_value=bluez_manager)
    )
    bleak_retry_connector.bluez.defs = defs

    device = await get_device("FA:23:9D:AA:45:46")

    assert device is not None
    assert device.details["path"] == "/org/bluez/hci0/dev_FA_23_9D_AA_45_46"

    assert await clear_cache("FA:23:9D:AA:45:46")
    assert bluez_manager._services_cache == {}


@pytest.mark.asyncio
async def test_get_device_mac_os(mock_macos):
    class FakeBluezManager:
        def __init__(self):
            self._services_cache = {}
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

    bluez_manager = FakeBluezManager()

    bleak_retry_connector.bleak_manager.get_global_bluez_manager = AsyncMock(
        return_value=bluez_manager
    )

    bleak_retry_connector.bleak_manager.get_global_bluez_manager_with_timeout = (
        AsyncMock(return_value=bluez_manager)
    )
    bleak_retry_connector.bluez.defs = defs

    device = await get_device("FA:23:9D:AA:45:46")

    assert device is None


@pytest.mark.asyncio
async def test_get_device_already_connected(mock_linux):
    class FakeBluezManager:
        def __init__(self):
            self._services_cache = {}
            self._properties = {
                "/org/bluez/hci1/dev_BD_24_6F_85_AA_61": {
                    "org.freedesktop.DBus.Introspectable": {},
                    "org.bluez.Device1": {
                        "Address": "BD:24:6F:85:AA:61",
                        "AddressType": "public",
                        "Name": "Dream~BD246F85AA61",
                        "Alias": "Dream~BD246F85AA61",
                        "Appearance": 962,
                        "Icon": "input-mouse",
                        "Paired": False,
                        "Trusted": False,
                        "Blocked": False,
                        "LegacyPairing": False,
                        "Connected": True,
                        "UUIDs": [
                            "00001800-0000-1000-8000-00805f9b34fb",
                            "00001801-0000-1000-8000-00805f9b34fb",
                            "0000180a-0000-1000-8000-00805f9b34fb",
                            "0000ffd0-0000-1000-8000-00805f9b34fb",
                            "0000ffd5-0000-1000-8000-00805f9b34fb",
                        ],
                        "Modalias": "usb:v045Ep0040d0300",
                        "Adapter": "/org/bluez/hci1",
                        "ManufacturerData": {20808: bytearray(b"364656")},
                        "ServicesResolved": True,
                    },
                    "org.freedesktop.DBus.Properties": {},
                }
            }

    bluez_manager = FakeBluezManager()

    bleak_retry_connector.bleak_manager.get_global_bluez_manager = AsyncMock(
        return_value=bluez_manager
    )

    bleak_retry_connector.bleak_manager.get_global_bluez_manager_with_timeout = (
        AsyncMock(return_value=bluez_manager)
    )
    bleak_retry_connector.bluez.defs = defs

    device = await get_device("BD:24:6F:85:AA:61")

    assert device is not None
    assert device.details["path"] == "/org/bluez/hci1/dev_BD_24_6F_85_AA_61"
    connected = await get_connected_devices(device)
    assert len(connected) == 1
    assert isinstance(connected[0], BLEDevice)
    assert connected[0].details["path"] == "/org/bluez/hci1/dev_BD_24_6F_85_AA_61"


@pytest.mark.asyncio
async def test_get_device_not_there():
    class FakeBluezManager:
        def __init__(self):
            self._services_cache = {}
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

    bluez_manager = FakeBluezManager()

    bleak_retry_connector.bleak_manager.get_global_bluez_manager = AsyncMock(
        return_value=bluez_manager
    )

    bleak_retry_connector.bleak_manager.get_global_bluez_manager_with_timeout = (
        AsyncMock(return_value=bluez_manager)
    )
    bleak_retry_connector.bluez.defs = defs

    with patch.object(bleak_retry_connector.const, "IS_LINUX", True):
        device = await get_device("00:00:00:00:00:00")

    assert device is None


@pytest.mark.asyncio
async def test_establish_connection_better_rssi_available_already_connected_supported_different_adapter(
    mock_linux,
):
    device: BLEDevice | None = None

    class FakeBleakClient(BleakClient):
        def __init__(self, ble_device_or_address, *args, **kwargs):
            ble_device_or_address.details["delegate"] = 0
            super().__init__(ble_device_or_address, *args, **kwargs)
            nonlocal device
            device = ble_device_or_address
            self._device_path = "/org/bluez/hci2/dev_FA_23_9D_AA_45_46"

        async def connect(self, *args, **kwargs):
            return True

        async def disconnect(self, *args, **kwargs):
            pass

        async def get_services(self, *args, **kwargs):
            return []

    class FakeBleakClientWithServiceCache(BleakClientWithServiceCache, FakeBleakClient):
        """Fake BleakClientWithServiceCache."""

        async def get_services(self, *args, **kwargs):
            return []

    collection = BleakGATTServiceCollection()

    class FakeBluezManager:
        def __init__(self):
            self._services_cache = {}
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

    bluez_manager = FakeBluezManager()

    bleak_retry_connector.bleak_manager.get_global_bluez_manager = AsyncMock(
        return_value=bluez_manager
    )

    bleak_retry_connector.bleak_manager.get_global_bluez_manager_with_timeout = (
        AsyncMock(return_value=bluez_manager)
    )
    bleak_retry_connector.bluez.defs = defs

    mock_device = BLEDevice(
        "aa:bb:cc:dd:ee:ff",
        "name",
        {"path": "/org/bluez/hci2/dev_FA_23_9D_AA_45_46"},
        delegate=False,
    )

    connected = await get_connected_devices(mock_device)
    assert len(connected) == 2
    assert isinstance(connected[0], BLEDevice)
    assert connected[0].details["path"] == "/org/bluez/hci1/dev_FA_23_9D_AA_45_46"
    assert connected[1].details["path"] == "/org/bluez/hci2/dev_FA_23_9D_AA_45_46"

    with patch("bleak_retry_connector._disconnect_devices") as mock_disconnect_device:
        client = await establish_connection(
            FakeBleakClientWithServiceCache,
            BLEDevice(
                "FA:23:9D:AA:45:46",
                "name",
                {"path": "/org/bluez/hci2/dev_FA_23_9D_AA_45_46"},
                delegate=False,
            ),
            "test",
            disconnected_callback=MagicMock(),
            cached_services=collection,
        )

    assert isinstance(client, FakeBleakClientWithServiceCache)
    await client.get_services() is collection
    assert device is not None
    assert device.details["path"] == "/org/bluez/hci1/dev_FA_23_9D_AA_45_46"
    assert not mock_disconnect_device.mock_calls


@pytest.mark.asyncio
async def test_establish_connection_better_rssi_available_already_connected_supported_same_adapter(
    mock_linux,
):
    device: BLEDevice | None = None

    class FakeBleakClient(BleakClient):
        def __init__(self, ble_device_or_address, *args, **kwargs):
            ble_device_or_address.details["delegate"] = 0
            super().__init__(ble_device_or_address, *args, **kwargs)
            nonlocal device
            device = ble_device_or_address
            self._device_path = "/org/bluez/hci2/dev_FA_23_9D_AA_45_46"

        async def connect(self, *args, **kwargs):
            return True

        async def disconnect(self, *args, **kwargs):
            pass

        async def get_services(self, *args, **kwargs):
            return []

    class FakeBleakClientWithServiceCache(BleakClientWithServiceCache, FakeBleakClient):
        """Fake BleakClientWithServiceCache."""

        async def get_services(self, *args, **kwargs):
            return []

    collection = BleakGATTServiceCollection()

    class FakeBluezManager:
        def __init__(self):
            self._services_cache = {}
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

    bluez_manager = FakeBluezManager()

    bleak_retry_connector.bleak_manager.get_global_bluez_manager = AsyncMock(
        return_value=bluez_manager
    )

    bleak_retry_connector.bleak_manager.get_global_bluez_manager_with_timeout = (
        AsyncMock(return_value=bluez_manager)
    )
    bleak_retry_connector.bluez.defs = defs

    mock_device = BLEDevice(
        "aa:bb:cc:dd:ee:ff",
        "name",
        {"path": "/org/bluez/hci2/dev_FA_23_9D_AA_45_46"},
        delegate=False,
    )

    connected = await get_connected_devices(mock_device)
    assert len(connected) == 2
    assert isinstance(connected[0], BLEDevice)
    assert connected[0].details["path"] == "/org/bluez/hci1/dev_FA_23_9D_AA_45_46"
    assert connected[1].details["path"] == "/org/bluez/hci2/dev_FA_23_9D_AA_45_46"

    with (
        patch("bleak_retry_connector._disconnect_devices") as mock_disconnect_device,
        patch("bleak.get_platform_client_backend_type"),
    ):
        client = await establish_connection(
            FakeBleakClientWithServiceCache,
            BLEDevice(
                "FA:23:9D:AA:45:46",
                "name",
                {"path": "/org/bluez/hci1/dev_FA_23_9D_AA_45_46"},
                delegate=False,
            ),
            "test",
            disconnected_callback=MagicMock(),
            cached_services=collection,
        )

    assert isinstance(client, FakeBleakClientWithServiceCache)
    await client.get_services() is collection
    assert device is not None
    assert device.details["path"] == "/org/bluez/hci1/dev_FA_23_9D_AA_45_46"
    assert not mock_disconnect_device.mock_calls


@pytest.mark.asyncio
async def test_get_device_by_adapter(mock_linux):
    class FakeBluezManager:
        def __init__(self):
            self._services_cache = {}
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

    bluez_manager = FakeBluezManager()

    bleak_retry_connector.bleak_manager.get_global_bluez_manager = AsyncMock(
        return_value=bluez_manager
    )

    bleak_retry_connector.bleak_manager.get_global_bluez_manager_with_timeout = (
        AsyncMock(return_value=bluez_manager)
    )
    bleak_retry_connector.bluez.defs = defs

    device_hci0 = await get_device_by_adapter("FA:23:9D:AA:45:46", "hci0")
    device_hci1 = await get_device_by_adapter("FA:23:9D:AA:45:46", "hci1")

    assert device_hci0 is not None
    assert device_hci0.details["path"] == "/org/bluez/hci0/dev_FA_23_9D_AA_45_46"
    assert device_hci1 is not None
    assert device_hci1.details["path"] == "/org/bluez/hci1/dev_FA_23_9D_AA_45_46"


def test_calculate_backoff_time():
    """Test that the backoff time is calculated correctly."""
    assert calculate_backoff_time(Exception()) == BLEAK_BACKOFF_TIME
    assert (
        calculate_backoff_time(BleakDBusError(MagicMock(), MagicMock()))
        == BLEAK_DBUS_BACKOFF_TIME
    )
    assert (
        calculate_backoff_time(
            BleakError(
                "No backend with an available connection slot that can reach address EB:4A:D4:93:68:EF was found"
            )
        )
        == BLEAK_OUT_OF_SLOTS_BACKOFF_TIME
    )
    assert (
        calculate_backoff_time(BleakError("ESP_GATT_CONN_TERMINATE_PEER_USER"))
        == BLEAK_TRANSIENT_BACKOFF_TIME
    )
    assert (
        calculate_backoff_time(BleakError("ESP_GATT_CONN_FAIL_ESTABLISH"))
        == BLEAK_TRANSIENT_MEDIUM_BACKOFF_TIME
    )
    assert (
        calculate_backoff_time(BleakError("ESP_GATT_ERROR"))
        == BLEAK_TRANSIENT_LONG_BACKOFF_TIME
    )
    assert (
        calculate_backoff_time(BleakDeviceNotFoundError("Out of slots"))
        == BLEAK_OUT_OF_SLOTS_BACKOFF_TIME
    )
    assert (
        calculate_backoff_time(BleakError("ESP_GATT_CONN_CONN_CANCEL"))
        == BLEAK_OUT_OF_SLOTS_BACKOFF_TIME
    )


@pytest.mark.asyncio
async def test_retry_bluetooth_connection_error():
    """Test that the retry_bluetooth_connection_error decorator works correctly."""

    @retry_bluetooth_connection_error()
    async def test_function():
        raise BleakDBusError(MagicMock(), MagicMock())

    with patch(
        "bleak_retry_connector.calculate_backoff_time"
    ) as mock_calculate_backoff_time:
        mock_calculate_backoff_time.return_value = 0
        with pytest.raises(BleakDBusError):
            await test_function()

        assert mock_calculate_backoff_time.call_count == 2


@pytest.mark.asyncio
async def test_retry_bluetooth_connection_error_non_default_max_attempts():
    """Test that the retry_bluetooth_connection_error decorator works correctly with a different number of retries."""

    @retry_bluetooth_connection_error(4)
    async def test_function():
        raise BleakDBusError(MagicMock(), MagicMock())

    with patch(
        "bleak_retry_connector.calculate_backoff_time"
    ) as mock_calculate_backoff_time:
        mock_calculate_backoff_time.return_value = 0
        with pytest.raises(BleakDBusError):
            await test_function()

        assert mock_calculate_backoff_time.call_count == 4


@pytest.mark.asyncio
async def test_dbus_is_missing(mock_linux):
    """Test getting a device when dbus is missing."""

    bleak_retry_connector.bleak_manager.get_global_bluez_manager = AsyncMock(
        side_effect=FileNotFoundError("dbus not here")
    )
    bleak_retry_connector.bleak_manager.get_global_bluez_manager_with_timeout = (
        AsyncMock(side_effect=FileNotFoundError("dbus not here"))
    )
    bleak_retry_connector.bluez.defs = defs

    with patch.object(bleak_retry_connector.const, "IS_LINUX", True):
        device = await get_device("FA:23:9D:AA:45:46")

    assert device is None

    class FakeBluezManager:
        def __init__(self):
            self._services_cache = {}
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

    bluez_manager = FakeBluezManager()

    bleak_retry_connector.bleak_manager.get_global_bluez_manager = AsyncMock(
        return_value=bluez_manager
    )

    bleak_retry_connector.bleak_manager.get_global_bluez_manager_with_timeout = (
        AsyncMock(return_value=bluez_manager)
    )

    device = await get_device("FA:23:9D:AA:45:46")

    assert device is not None

    _reset_dbus_socket_cache()

    device = await get_device("FA:23:9D:AA:45:46")

    assert device is not None


@pytest.mark.asyncio
async def test_ble_device_description():
    device = BLEDevice(
        "aa:bb:cc:dd:ee:ff",
        "name",
        {"path": "/org/bluez/hci2/dev_FA_23_9D_AA_45_46"},
    )
    assert (
        ble_device_description(device) == "aa:bb:cc:dd:ee:ff - name -> /org/bluez/hci2"
    )
    device2 = BLEDevice(
        "aa:bb:cc:dd:ee:ff",
        "name",
        {"path": "/org/bluez/hci2/dev_FA_23_9D_AA_45_46"},
    )
    assert (
        ble_device_description(device2) == "aa:bb:cc:dd:ee:ff - name -> /org/bluez/hci2"
    )
    device3 = BLEDevice("aa:bb:cc:dd:ee:ff", "name", {"source": "esphome_proxy_1"})
    assert (
        ble_device_description(device3) == "aa:bb:cc:dd:ee:ff - name -> esphome_proxy_1"
    )


@pytest.mark.asyncio
@pytest.mark.skipif("not bleak_retry_connector.const.IS_LINUX")
async def test_restore_discoveries(mock_linux):
    class FakeBluezManager:
        def __init__(self):
            self._services_cache = {}
            self._properties = {
                "/org/bluez/hci1/dev_BD_24_6F_85_AA_61": {
                    "org.freedesktop.DBus.Introspectable": {},
                    "org.bluez.Device1": {
                        "Address": "BD:24:6F:85:AA:61",
                        "AddressType": "public",
                        "Name": "Dream~BD246F85AA61",
                        "Alias": "Dream~BD246F85AA61",
                        "Appearance": 962,
                        "Icon": "input-mouse",
                        "Paired": False,
                        "Trusted": False,
                        "Blocked": False,
                        "LegacyPairing": False,
                        "Connected": True,
                        "UUIDs": [
                            "00001800-0000-1000-8000-00805f9b34fb",
                            "00001801-0000-1000-8000-00805f9b34fb",
                            "0000180a-0000-1000-8000-00805f9b34fb",
                            "0000ffd0-0000-1000-8000-00805f9b34fb",
                            "0000ffd5-0000-1000-8000-00805f9b34fb",
                        ],
                        "Modalias": "usb:v045Ep0040d0300",
                        "Adapter": "/org/bluez/hci1",
                        "ManufacturerData": {20808: bytearray(b"364656")},
                        "ServicesResolved": True,
                    },
                    "org.freedesktop.DBus.Properties": {},
                },
                "/org/bluez/hci5/dev_BE_24_6F_85_AA_61": {
                    "org.freedesktop.DBus.Introspectable": {},
                    "org.bluez.Device1": {
                        "Address": "BE:24:6F:85:AA:61",
                        "AddressType": "public",
                        "Name": "Dream~BD246F85AA61",
                        "Alias": "Dream~BD246F85AA61",
                        "Appearance": 962,
                        "Icon": "input-mouse",
                        "Paired": False,
                        "Trusted": False,
                        "Blocked": False,
                        "LegacyPairing": False,
                        "Connected": True,
                        "UUIDs": [
                            "00001800-0000-1000-8000-00805f9b34fb",
                            "00001801-0000-1000-8000-00805f9b34fb",
                            "0000180a-0000-1000-8000-00805f9b34fb",
                            "0000ffd0-0000-1000-8000-00805f9b34fb",
                            "0000ffd5-0000-1000-8000-00805f9b34fb",
                        ],
                        "Modalias": "usb:v045Ep0040d0300",
                        "Adapter": "/org/bluez/hci1",
                        "ManufacturerData": {20808: bytearray(b"364656")},
                        "ServicesResolved": True,
                    },
                    "org.freedesktop.DBus.Properties": {},
                },
            }

    bluez_manager = FakeBluezManager()

    bleak_retry_connector.bleak_manager.get_global_bluez_manager = AsyncMock(
        return_value=bluez_manager
    )

    bleak_retry_connector.bleak_manager.get_global_bluez_manager_with_timeout = (
        AsyncMock(return_value=bluez_manager)
    )
    from bluetooth_adapters.history import load_history_from_managed_objects

    bleak_retry_connector.load_history_from_managed_objects = (
        load_history_from_managed_objects
    )
    bleak_retry_connector.bluez.defs = defs
    seen_devices: dict[str, tuple[BLEDevice, AdvertisementData]] = {}

    mock_backend = Mock(seen_devices=seen_devices)
    mock_scanner = Mock(_backend=mock_backend)

    await restore_discoveries(mock_scanner, "hci1")

    assert len(seen_devices) == 1


@pytest.mark.asyncio
async def test_close_stale_connections_by_address(mock_linux):
    class FakeBluezManager:
        def __init__(self):
            self._services_cache = {
                "/org/bluez/hci0/dev_FA_23_9D_AA_45_46": "test",
                "/org/bluez/hci1/dev_FA_23_9D_AA_45_46": "test",
            }
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
                        "Address": "FA:23:9D:AA:45:46",
                        "Alias": "FA:23:9D:AA:45:46",
                        "RSSI": -79,
                        "Connected": True,
                    },
                    defs.GATT_SERVICE_INTERFACE: True,
                },
                "/org/bluez/hci2/dev_FA_23_9D_AA_45_46": {
                    "UUID": "service",
                    "Primary": True,
                    "Characteristics": [],
                    defs.DEVICE_INTERFACE: {
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

    bluez_manager = FakeBluezManager()

    bleak_retry_connector.bleak_manager.get_global_bluez_manager = AsyncMock(
        return_value=bluez_manager
    )
    bleak_retry_connector.bleak_manager.get_global_bluez_manager_with_timeout = (
        AsyncMock(return_value=bluez_manager)
    )
    bleak_retry_connector.bluez.defs = defs

    with patch.object(
        bleak_retry_connector, "disconnect_devices", AsyncMock()
    ) as mock_disconnect_devices:
        await close_stale_connections_by_address("FA:23:9D:AA:45:46")
    assert len(mock_disconnect_devices.mock_calls) == 1


@pytest.mark.asyncio
async def test_has_valid_services_in_cache_success(mock_linux):
    """Test successful validation when all cached services are present in properties."""

    class FakeBleakClient(BleakClient):
        """Fake BleakClient."""

        async def connect(self, **kwargs):
            """Connect."""

        async def disconnect(self):
            """Disconnect."""

        async def get_services(self):
            """Get services."""
            return []

    # Create a proper BleakGATTServiceCollection with services
    collection = BleakGATTServiceCollection()

    # Add a service that will be present in properties
    service_path = "/org/bluez/hci0/dev_FA_23_9D_AA_45_46/service0001"
    service_props = {
        "UUID": "0000180a-0000-1000-8000-00805f9b34fb",
        "Primary": True,
        "Characteristics": [],
    }
    service = BleakGATTService(
        obj=(service_path, service_props),
        handle=1,
        uuid="0000180a-0000-1000-8000-00805f9b34fb",
    )
    collection.add_service(service)

    # Add another service
    service_path2 = "/org/bluez/hci0/dev_FA_23_9D_AA_45_46/service0002"
    service_props2 = {
        "UUID": "0000180f-0000-1000-8000-00805f9b34fb",
        "Primary": True,
        "Characteristics": [],
    }
    service2 = BleakGATTService(
        obj=(service_path2, service_props2),
        handle=2,
        uuid="0000180f-0000-1000-8000-00805f9b34fb",
    )
    collection.add_service(service2)

    class FakeBluezManager:
        def __init__(self):
            # Services cache contains our collection for the device
            self._services_cache = {"/org/bluez/hci0/dev_FA_23_9D_AA_45_46": collection}
            # Properties contain both service paths
            self._properties = {
                "/org/bluez/hci0/dev_FA_23_9D_AA_45_46": {
                    "org.bluez.Device1": {
                        "Address": "FA:23:9D:AA:45:46",
                        "Connected": False,
                    }
                },
                # Both services are present in properties
                service_path: service_props,
                service_path2: service_props2,
            }

    bluez_manager = FakeBluezManager()

    bleak_retry_connector.bluez.get_global_bluez_manager_with_timeout = AsyncMock(
        return_value=bluez_manager
    )
    bleak_retry_connector.bluez.defs = defs

    device = BLEDevice(
        address="FA:23:9D:AA:45:46",
        name="Test Device",
        details={"path": "/org/bluez/hci0/dev_FA_23_9D_AA_45_46"},
        rssi=-50,
    )

    # Capture the log to verify the success message
    with patch.object(
        bleak_retry_connector,
        "_has_valid_services_in_cache",
        wraps=bleak_retry_connector._has_valid_services_in_cache,
    ) as mock_validate:
        client = await bleak_retry_connector.establish_connection(
            FakeBleakClient,
            device,
            "Test Device",
            use_services_cache=True,
        )

        # Verify the validation was called
        mock_validate.assert_called_once()

        # Call the wrapped function directly to verify it returns True
        result = await bleak_retry_connector._has_valid_services_in_cache(device)
        assert result is True

    assert client is not None


@pytest.mark.asyncio
async def test_has_valid_services_in_cache_service_missing(mock_linux):
    """Test validation fails when a cached service is not in properties."""

    class FakeBleakClient(BleakClient):
        """Fake BleakClient."""

        async def connect(self, **kwargs):
            """Connect."""

        async def disconnect(self):
            """Disconnect."""

        async def get_services(self):
            """Get services."""
            return []

    # Create a proper BleakGATTServiceCollection with services
    collection = BleakGATTServiceCollection()

    # Add a service that will NOT be present in properties
    service_path = "/org/bluez/hci0/dev_FA_23_9D_AA_45_46/service0001"
    service_props = {
        "UUID": "0000180a-0000-1000-8000-00805f9b34fb",
        "Primary": True,
        "Characteristics": [],
    }
    service = BleakGATTService(
        obj=(service_path, service_props),
        handle=1,
        uuid="0000180a-0000-1000-8000-00805f9b34fb",
    )
    collection.add_service(service)

    class FakeBluezManager:
        def __init__(self):
            # Services cache contains our collection for the device
            self._services_cache = {"/org/bluez/hci0/dev_FA_23_9D_AA_45_46": collection}
            # Properties do NOT contain the service path - service is missing
            self._properties = {
                "/org/bluez/hci0/dev_FA_23_9D_AA_45_46": {
                    "org.bluez.Device1": {
                        "Address": "FA:23:9D:AA:45:46",
                        "Connected": False,
                    }
                },
                # service_path is NOT in properties
            }

    bluez_manager = FakeBluezManager()

    bleak_retry_connector.bluez.get_global_bluez_manager_with_timeout = AsyncMock(
        return_value=bluez_manager
    )
    bleak_retry_connector.bluez.defs = defs

    device = BLEDevice(
        address="FA:23:9D:AA:45:46",
        name="Test Device",
        details={"path": "/org/bluez/hci0/dev_FA_23_9D_AA_45_46"},
        rssi=-50,
    )

    # Call the function directly to verify it returns False
    result = await bleak_retry_connector._has_valid_services_in_cache(device)
    assert result is False

    # Verify that the cache is not used when validation fails
    client = await bleak_retry_connector.establish_connection(
        FakeBleakClient,
        device,
        "Test Device",
        use_services_cache=True,
    )
    assert client is not None


@pytest.mark.asyncio
async def test_has_valid_services_in_cache_no_services(mock_linux):
    """Test validation returns False when there are no services in the collection."""

    class FakeBleakClient(BleakClient):
        """Fake BleakClient."""

        async def connect(self, **kwargs):
            """Connect."""

        async def disconnect(self):
            """Disconnect."""

        async def get_services(self):
            """Get services."""
            return []

    # Create an empty BleakGATTServiceCollection (no services)
    collection = BleakGATTServiceCollection()

    class FakeBluezManager:
        def __init__(self):
            # Services cache contains an empty collection for the device
            self._services_cache = {"/org/bluez/hci0/dev_FA_23_9D_AA_45_46": collection}
            # Properties exist but collection has no services
            self._properties = {
                "/org/bluez/hci0/dev_FA_23_9D_AA_45_46": {
                    "org.bluez.Device1": {
                        "Address": "FA:23:9D:AA:45:46",
                        "Connected": False,
                    }
                },
            }

    bluez_manager = FakeBluezManager()

    bleak_retry_connector.bluez.get_global_bluez_manager_with_timeout = AsyncMock(
        return_value=bluez_manager
    )
    bleak_retry_connector.bluez.defs = defs

    device = BLEDevice(
        address="FA:23:9D:AA:45:46",
        name="Test Device",
        details={"path": "/org/bluez/hci0/dev_FA_23_9D_AA_45_46"},
        rssi=-50,
    )

    # Call the function directly to verify it returns False
    result = await bleak_retry_connector._has_valid_services_in_cache(device)
    assert result is False

    # Verify that the cache is not used when there are no services
    client = await bleak_retry_connector.establish_connection(
        FakeBleakClient,
        device,
        "Test Device",
        use_services_cache=True,
    )
    assert client is not None
