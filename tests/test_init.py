import asyncio
import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from bleak import BleakClient, BleakError
from bleak.backends.bluezdbus import defs
from bleak.backends.device import BLEDevice
from bleak.backends.service import BleakGATTServiceCollection
from bleak.exc import BleakDBusError

import bleak_retry_connector
from bleak_retry_connector import (
    BLEAK_BACKOFF_TIME,
    BLEAK_DBUS_BACKOFF_TIME,
    MAX_TRANSIENT_ERRORS,
    BleakAbortedError,
    BleakClientWithServiceCache,
    BleakConnectionError,
    BleakNotFoundError,
    ble_device_has_changed,
    calculate_backoff_time,
    establish_connection,
    get_connected_devices,
    get_device,
    get_device_by_adapter,
    retry_bluetooth_connection_error,
)


@pytest.fixture(autouse=True)
def configure_test_logging(caplog):
    caplog.set_level(logging.DEBUG)


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
            self._properties = {
                "/dev/test/service/1": {
                    "UUID": "service",
                    "Primary": True,
                    "Characteristics": [],
                    defs.GATT_SERVICE_INTERFACE: True,
                },
            }

    bleak_retry_connector.get_global_bluez_manager = AsyncMock(
        return_value=FakeBluezManager()
    )
    bleak_retry_connector.defs = defs

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
            self._properties = {}

    bleak_retry_connector.get_global_bluez_manager = AsyncMock(
        return_value=FakeBluezManager()
    )
    bleak_retry_connector.defs = defs

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
            self._properties = {
                "/dev/test/service/1": {
                    "UUID": "service",
                    "Primary": True,
                    "Characteristics": [],
                    defs.GATT_SERVICE_INTERFACE: True,
                },
            }

    bleak_retry_connector.get_global_bluez_manager = AsyncMock(
        return_value=FakeBluezManager()
    )
    bleak_retry_connector.defs = defs

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
            self._properties = {
                "/dev/test2/service/1": {
                    "UUID": "service",
                    "Primary": True,
                    "Characteristics": [],
                },
            }

    bleak_retry_connector.get_global_bluez_manager = AsyncMock(
        return_value=FakeBluezManager()
    )
    bleak_retry_connector.defs = defs

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

    with pytest.raises(BleakConnectionError):
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

    with pytest.raises(BleakNotFoundError):
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
async def test_establish_connection_has_transient_error_had_advice():
    class FakeBleakClient(BleakClient):
        def __init__(self, *args, **kwargs):
            pass

        async def connect(self, *args, **kwargs):
            raise BleakError("le-connection-abort-by-local")

        async def disconnect(self, *args, **kwargs):
            pass

    try:
        await establish_connection(
            FakeBleakClient,
            BLEDevice("aa:bb:cc:dd:ee:ff", "name", {"path": "/dev/1"}),
            "test",
        )
    except BleakError as e:
        exc = e

    assert isinstance(exc, BleakAbortedError)
    assert str(exc) == (
        "test - /dev/1: "
        "Failed to connect: "
        "le-connection-abort-by-local: "
        "Interference/range; "
        "External Bluetooth adapter w/extension may help; "
        "Extension cables reduce USB 3 port interference"
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

    try:
        await establish_connection(
            FakeBleakClient,
            BLEDevice("aa:bb:cc:dd:ee:ff", "name", {"path": "/dev/1"}),
            "test",
        )
    except BleakError as e:
        exc = e

    assert isinstance(exc, BleakNotFoundError)
    assert str(exc) == (
        "test - /dev/1: "
        "Failed to connect: "
        "[org.freedesktop.DBus.Error.UnknownObject] "
        'Method "Connect" with signature "" on interface "org.bluez.Device1" '
        "doesn't exist: The device disappeared; "
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

    with pytest.raises(BleakConnectionError):
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

    with patch.object(bleak_retry_connector, "BLEAK_SAFETY_TIMEOUT", 0), pytest.raises(
        BleakNotFoundError
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
async def test_establish_connection_ble_device_changed():
    """Test we switch BLEDevice when the underlying device has changed."""

    attempts = 0

    ble_device_1 = BLEDevice("aa:bb:cc:dd:ee:ff", "name", {"path": "/dev/1"})
    ble_device_2 = BLEDevice("aa:bb:cc:dd:ee:ff", "name", {"path": "/dev/2"})
    ble_device_3 = BLEDevice("aa:bb:cc:dd:ee:ff", "name", {"path": "/dev/3"})

    def _get_ble_device():
        nonlocal attempts

        if attempts == 0:
            return ble_device_1
        if attempts == 1:
            return ble_device_2
        return ble_device_3

    class FakeBleakClient(BleakClient):
        def __init__(self, ble_device_or_address, *args, **kwargs):
            self.ble_device_or_address = ble_device_or_address
            pass

        async def connect(self, *args, **kwargs):
            nonlocal attempts
            attempts += 1
            if self.ble_device_or_address != ble_device_3:
                raise BleakError("le-connection-abort-by-local")
            pass

        async def disconnect(self, *args, **kwargs):
            pass

    client = await establish_connection(
        FakeBleakClient, ble_device_1, "test", ble_device_callback=_get_ble_device
    )
    assert isinstance(client, FakeBleakClient)
    assert attempts == 3


@pytest.mark.asyncio
async def test_establish_connection_better_rssi_available():

    device: BLEDevice | None = None

    class FakeBleakClient(BleakClient):
        def __init__(self, ble_device_or_address, *args, **kwargs):
            ble_device_or_address.metadata["delegate"] = 0
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

    bleak_retry_connector.get_global_bluez_manager = AsyncMock(
        return_value=FakeBluezManager()
    )
    bleak_retry_connector.defs = defs

    with patch.object(bleak_retry_connector, "IS_LINUX", True):

        client = await establish_connection(
            FakeBleakClientWithServiceCache,
            BLEDevice(
                "aa:bb:cc:dd:ee:ff",
                "name",
                {"path": "/org/bluez/hci2/dev_FA_23_9D_AA_45_46"},
                -80,
                delegate=False,
            ),
            "test",
            disconnected_callback=MagicMock(),
            cached_services=collection,
        )

    assert isinstance(client, FakeBleakClientWithServiceCache)
    await client.get_services() is collection
    assert device is not None
    assert device.details["path"] == "/org/bluez/hci0/dev_FA_23_9D_AA_45_46"


@pytest.mark.asyncio
async def test_establish_connection_other_adapter_already_connected():

    device: BLEDevice | None = None

    class FakeBleakClient(BleakClient):
        def __init__(self, ble_device_or_address, *args, **kwargs):
            ble_device_or_address.metadata["delegate"] = 0
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

    bleak_retry_connector.get_global_bluez_manager = AsyncMock(
        return_value=FakeBluezManager()
    )
    bleak_retry_connector.defs = defs

    with patch.object(bleak_retry_connector, "IS_LINUX", True):
        client = await establish_connection(
            FakeBleakClientWithServiceCache,
            BLEDevice(
                "aa:bb:cc:dd:ee:ff",
                "name",
                {"path": "/org/bluez/hci2/dev_FA_23_9D_AA_45_46"},
                -80,
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
async def test_establish_connection_device_disappeared():
    class FakeBleakClient(BleakClient):
        def __init__(self, ble_device_or_address, *args, **kwargs):
            ble_device_or_address.metadata["delegate"] = 0
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

    bleak_retry_connector.get_global_bluez_manager = AsyncMock(
        return_value=FakeBluezManager()
    )
    bleak_retry_connector.defs = defs

    with patch.object(bleak_retry_connector, "IS_LINUX", True):
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
async def test_get_device():
    class FakeBluezManager:
        def __init__(self):
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

    bleak_retry_connector.get_global_bluez_manager = AsyncMock(
        return_value=FakeBluezManager()
    )
    bleak_retry_connector.defs = defs

    with patch.object(bleak_retry_connector, "IS_LINUX", True):
        device = await get_device("FA:23:9D:AA:45:46")

    assert device is not None
    assert device.details["path"] == "/org/bluez/hci0/dev_FA_23_9D_AA_45_46"


@pytest.mark.asyncio
async def test_get_device_mac_os():
    class FakeBluezManager:
        def __init__(self):
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

    bleak_retry_connector.get_global_bluez_manager = AsyncMock(
        return_value=FakeBluezManager()
    )
    bleak_retry_connector.defs = defs

    with patch.object(bleak_retry_connector, "IS_LINUX", False):
        device = await get_device("FA:23:9D:AA:45:46")

    assert device is None


@pytest.mark.asyncio
async def test_get_device_already_connected():
    class FakeBluezManager:
        def __init__(self):
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

    bleak_retry_connector.get_global_bluez_manager = AsyncMock(
        return_value=FakeBluezManager()
    )
    bleak_retry_connector.defs = defs

    with patch.object(bleak_retry_connector, "IS_LINUX", True):
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

    bleak_retry_connector.get_global_bluez_manager = AsyncMock(
        return_value=FakeBluezManager()
    )
    bleak_retry_connector.defs = defs

    with patch.object(bleak_retry_connector, "IS_LINUX", True):
        device = await get_device("00:00:00:00:00:00")

    assert device is None


@pytest.mark.asyncio
async def test_establish_connection_better_rssi_available_already_connected_supported_different_adapter():

    device: BLEDevice | None = None

    class FakeBleakClient(BleakClient):
        def __init__(self, ble_device_or_address, *args, **kwargs):
            ble_device_or_address.metadata["delegate"] = 0
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

    bleak_retry_connector.get_global_bluez_manager = AsyncMock(
        return_value=FakeBluezManager()
    )
    bleak_retry_connector.defs = defs

    mock_device = BLEDevice(
        "aa:bb:cc:dd:ee:ff",
        "name",
        {"path": "/org/bluez/hci2/dev_FA_23_9D_AA_45_46"},
        -80,
        delegate=False,
    )

    connected = await get_connected_devices(mock_device)
    assert len(connected) == 2
    assert isinstance(connected[0], BLEDevice)
    assert connected[0].details["path"] == "/org/bluez/hci1/dev_FA_23_9D_AA_45_46"
    assert connected[1].details["path"] == "/org/bluez/hci2/dev_FA_23_9D_AA_45_46"

    with patch(
        "bleak_retry_connector._disconnect_devices"
    ) as mock_disconnect_device, patch.object(bleak_retry_connector, "IS_LINUX", True):
        client = await establish_connection(
            FakeBleakClientWithServiceCache,
            BLEDevice(
                "FA:23:9D:AA:45:46",
                "name",
                {"path": "/org/bluez/hci2/dev_FA_23_9D_AA_45_46"},
                -80,
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
    assert len(mock_disconnect_device.mock_calls) == 1
    assert (
        mock_disconnect_device.mock_calls[0][1][0][0].details["path"]
        == "/org/bluez/hci2/dev_FA_23_9D_AA_45_46"
    )


@pytest.mark.asyncio
async def test_establish_connection_better_rssi_available_already_connected_supported_same_adapter():

    device: BLEDevice | None = None

    class FakeBleakClient(BleakClient):
        def __init__(self, ble_device_or_address, *args, **kwargs):
            ble_device_or_address.metadata["delegate"] = 0
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

    bleak_retry_connector.get_global_bluez_manager = AsyncMock(
        return_value=FakeBluezManager()
    )
    bleak_retry_connector.defs = defs

    mock_device = BLEDevice(
        "aa:bb:cc:dd:ee:ff",
        "name",
        {"path": "/org/bluez/hci2/dev_FA_23_9D_AA_45_46"},
        -80,
        delegate=False,
    )

    connected = await get_connected_devices(mock_device)
    assert len(connected) == 2
    assert isinstance(connected[0], BLEDevice)
    assert connected[0].details["path"] == "/org/bluez/hci1/dev_FA_23_9D_AA_45_46"
    assert connected[1].details["path"] == "/org/bluez/hci2/dev_FA_23_9D_AA_45_46"

    with patch(
        "bleak_retry_connector._disconnect_devices"
    ) as mock_disconnect_device, patch(
        "bleak.get_platform_client_backend_type"
    ), patch.object(
        bleak_retry_connector, "IS_LINUX", True
    ):
        client = await establish_connection(
            FakeBleakClientWithServiceCache,
            BLEDevice(
                "FA:23:9D:AA:45:46",
                "name",
                {"path": "/org/bluez/hci1/dev_FA_23_9D_AA_45_46"},
                -80,
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
    assert len(mock_disconnect_device.mock_calls) == 1
    assert (
        mock_disconnect_device.mock_calls[0][1][0][0].details["path"]
        == "/org/bluez/hci2/dev_FA_23_9D_AA_45_46"
    )


@pytest.mark.asyncio
async def test_get_device_by_adapter():
    class FakeBluezManager:
        def __init__(self):
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

    bleak_retry_connector.get_global_bluez_manager = AsyncMock(
        return_value=FakeBluezManager()
    )
    bleak_retry_connector.defs = defs

    with patch.object(bleak_retry_connector, "IS_LINUX", True):
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


@pytest.mark.asyncio
async def test_retry_bluetooth_connection_error():
    """Test that the retry_bluetooth_connection_error decorator works correctly."""

    @retry_bluetooth_connection_error()  # type: ignore[misc]
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

    @retry_bluetooth_connection_error(4)  # type: ignore[misc]
    async def test_function():
        raise BleakDBusError(MagicMock(), MagicMock())

    with patch(
        "bleak_retry_connector.calculate_backoff_time"
    ) as mock_calculate_backoff_time:
        mock_calculate_backoff_time.return_value = 0
        with pytest.raises(BleakDBusError):
            await test_function()

        assert mock_calculate_backoff_time.call_count == 4
