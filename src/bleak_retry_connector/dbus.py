from __future__ import annotations

import contextlib

import async_timeout
from bleak.backends.bluezdbus import defs
from bleak.backends.device import BLEDevice
from dbus_fast.aio.message_bus import MessageBus
from dbus_fast.constants import BusType
from dbus_fast.message import Message

DISCONNECT_TIMEOUT = 5


async def disconnect_devices(devices: list[BLEDevice]) -> None:
    """Disconnect a list of devices."""
    valid_devices = [
        device
        for device in devices
        if isinstance(device.details, dict) and "path" in device.details
    ]
    if not valid_devices:
        return
    bus = await MessageBus(bus_type=BusType.SYSTEM, negotiate_unix_fd=True).connect()
    for device in valid_devices:
        with contextlib.suppress(Exception):
            async with async_timeout.timeout(DISCONNECT_TIMEOUT):
                await bus.call(
                    Message(
                        destination=defs.BLUEZ_SERVICE,
                        path=device.details["path"],
                        interface=defs.DEVICE_INTERFACE,
                        member="Disconnect",
                    )
                )
    bus.disconnect()
