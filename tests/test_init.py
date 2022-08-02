import asyncio
from unittest.mock import MagicMock, patch

import pytest
from bleak import BleakClient, BleakError

import bleak_retry_connector
from bleak_retry_connector import (
    MAX_TRANSIENT_ERRORS,
    BleakConnectionError,
    BleakNotFoundError,
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
