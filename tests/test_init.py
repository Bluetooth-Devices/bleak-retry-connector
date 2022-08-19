import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from bleak import BleakClient, BleakError
from bleak.backends.bluezdbus import defs
from bleak.backends.device import BLEDevice
from bleak.backends.service import BleakGATTServiceCollection

import bleak_retry_connector
from bleak_retry_connector import (
    MAX_TRANSIENT_ERRORS,
    BleakAbortedError,
    BleakClientWithServiceCache,
    BleakConnectionError,
    BleakNotFoundError,
    ble_device_has_changed,
    establish_connection,
)


@pytest.mark.asyncio
async def test_establish_connection_works_first_time():
    class FakeBleakClient(BleakClient):
        def __init__(self, *args, **kwargs):
            pass

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

    with patch.object(bleak_retry_connector, "CAN_CACHE_SERVICES", True):
        client = await establish_connection(
            FakeBleakClientWithServiceCache,
            MagicMock(),
            "test",
            disconnected_callback=MagicMock(),
            cached_services=collection,
        )

    assert isinstance(client, FakeBleakClientWithServiceCache)
    assert client._cached_services is collection
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

    with patch.object(
        bleak_retry_connector, "BLEAK_HAS_SERVICE_CACHE_SUPPORT", False
    ), patch.object(bleak_retry_connector, "CAN_CACHE_SERVICES", True):
        client = await establish_connection(
            FakeBleakClientWithServiceCache,
            MagicMock(),
            "test",
            disconnected_callback=MagicMock(),
            cached_services=collection,
        )

    assert isinstance(client, FakeBleakClientWithServiceCache)
    assert client._cached_services is None
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

    with patch.object(bleak_retry_connector, "CAN_CACHE_SERVICES", True):
        client = await establish_connection(
            FakeBleakClientWithServiceCache,
            MagicMock(),
            "test",
            disconnected_callback=MagicMock(),
            cached_services=collection,
        )

        assert isinstance(client, FakeBleakClientWithServiceCache)
        assert client._cached_services is collection
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

    with patch.object(bleak_retry_connector, "CAN_CACHE_SERVICES", True):
        client = await establish_connection(
            FakeBleakClientWithServiceCache,
            MagicMock(),
            "test",
            disconnected_callback=MagicMock(),
            cached_services=collection,
        )

        assert isinstance(client, FakeBleakClientWithServiceCache)
        assert client._cached_services is None
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

    with patch.object(bleak_retry_connector, "CAN_CACHE_SERVICES", True), patch.object(
        bleak_retry_connector, "BLEAK_HAS_SERVICE_CACHE_SUPPORT", True
    ):
        client = await establish_connection(
            FakeBleakClientWithServiceCache,
            MagicMock(),
            "test",
            disconnected_callback=MagicMock(),
            cached_services=collection,
        )

        assert isinstance(client, FakeBleakClientWithServiceCache)
        assert client._cached_services is collection
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

    with patch.object(bleak_retry_connector, "CAN_CACHE_SERVICES", True):
        client = await establish_connection(
            FakeBleakClientWithServiceCache,
            MagicMock(),
            "test",
            disconnected_callback=MagicMock(),
        )

    assert isinstance(client, FakeBleakClientWithServiceCache)
    assert client._cached_services is not None
    await client.get_services() is client._cached_services


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

    with patch.object(bleak_retry_connector, "CAN_CACHE_SERVICES", False):
        client = await establish_connection(
            FakeBleakClientWithServiceCache,
            MagicMock(),
            "test",
            disconnected_callback=MagicMock(),
        )

    assert isinstance(client, FakeBleakClientWithServiceCache)
    assert client._cached_services is not None
    await client.get_services() is not client._cached_services


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
