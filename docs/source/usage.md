# Usage Guide

## Why Use bleak-retry-connector?

This package provides robust retry logic and intelligent backoff strategies for establishing BLE connections. Key benefits include:

- **Automatic retry with backoff** - Handles transient connection failures with intelligent retry timing
- **Connection slot management** - Critical for ESPHome Bluetooth proxies that have limited connection slots
- **Service caching** - Speeds up reconnections by caching GATT services
- **Platform-specific optimizations** - Special handling for Linux/BlueZ, macOS, and ESP32 devices
- **Error categorization** - Distinguishes between transient errors, missing devices, and out-of-slots conditions

### Essential for ESPHome Bluetooth Proxies

If you're using ESPHome Bluetooth proxies, this package is **critical** because:

1. **Proper slot management** - ESP32 devices have limited connection slots that must be carefully managed
2. **Handles ESP-specific errors** - Recognizes ESP32 error codes like `ESP_GATT_CONN_CONN_CANCEL` (out of slots)
3. **Appropriate backoff timing** - Uses longer backoff (4 seconds) when slots are exhausted to allow proper cleanup
4. **Prevents slot exhaustion** - Manages connection attempts to avoid overwhelming the proxy

## BleakClientWithServiceCache

`BleakClientWithServiceCache` is a subclass of `BleakClient` that provides service caching capabilities for faster reconnections.

### Basic Usage

```python
from bleak_retry_connector import BleakClientWithServiceCache
from bleak.backends.device import BLEDevice

async def connect_with_cache(device: BLEDevice):
    client = BleakClientWithServiceCache(device)
    await client.connect()

    # Use the client normally
    services = client.services

    # Clear cache if needed (e.g., after service changes)
    await client.clear_cache()

    await client.disconnect()
```

### Key Features

- **Automatic service caching**: Services are cached between connections for faster reconnections
- **Cache clearing**: Call `clear_cache()` to force a fresh service discovery
- **Drop-in replacement**: Can be used anywhere `BleakClient` is used

## establish_connection

`establish_connection` is the main function for establishing robust BLE connections with automatic retry logic.

### Function Signature

```python
async def establish_connection(
    client_class: type[BleakClient],
    device: BLEDevice,
    name: str,
    disconnected_callback: Callable[[BleakClient], None] | None = None,
    max_attempts: int = 4,
    cached_services: BleakGATTServiceCollection | None = None,
    ble_device_callback: Callable[[], BLEDevice] | None = None,
    use_services_cache: bool = True,
    **kwargs: Any
) -> BleakClient
```

### Parameters

- **client_class**: The BleakClient class to use (typically `BleakClientWithServiceCache`)
- **device**: The BLE device to connect to
- **name**: A descriptive name for the device (used in logging)
- **disconnected_callback**: Optional callback when device disconnects unexpectedly
- **max_attempts**: Maximum connection attempts before giving up (default: 4)
- **cached_services**: Pre-cached services to use (deprecated, use `use_services_cache`)
- **ble_device_callback**: Callback to get updated device info if it changes
- **use_services_cache**: Whether to use service caching (default: True)
- **kwargs**: Additional arguments passed to the client class constructor

### Return Value

Returns the connected client instance of the specified `client_class`.

### Exceptions

`establish_connection` can raise the following exceptions after exhausting retry attempts:

- **BleakNotFoundError**: Device was not found or disappeared

  - Raised when the device cannot be found
  - Raised on `asyncio.TimeoutError` after all retries
  - Raised when `BleakDeviceNotFoundError` occurs
  - Raised when device is missing from the adapter

- **BleakOutOfConnectionSlotsError**: Adapter/proxy has no available connection slots

  - Raised when local Bluetooth adapters or ESP32 proxies are out of connection slots
  - Common with errors containing "ESP_GATT_CONN_CONN_CANCEL", "connection slot", or "available connection"
  - For local adapters: disconnect unused devices or use a different adapter
  - For ESP32 proxies: add more proxies or disconnect other devices

- **BleakAbortedError**: Connection was aborted due to interference or range issues

  - Raised for transient connection failures that suggest environmental issues
  - Common with errors like "le-connection-abort-by-local", "br-connection-canceled"
  - Indicates interference, range problems, or USB 3.0 port interference

- **BleakConnectionError**: General connection failure after all retries
  - Raised for any other connection errors that don't fit the above categories
  - The fallback exception when connection cannot be established

### Basic Example

```python
from bleak_retry_connector import establish_connection, BleakClientWithServiceCache
from bleak.backends.device import BLEDevice

async def connect_to_device(device: BLEDevice):
    # Simple connection with retry
    client = await establish_connection(
        BleakClientWithServiceCache,
        device,
        name=device.name or device.address
    )

    # Use the client
    services = client.services

    # Disconnect when done
    await client.disconnect()

    return client
```

### Example with Disconnection Callback

```python
async def connect_with_callback(device: BLEDevice):
    def on_disconnect(client):
        print(f"Device {device.address} disconnected unexpectedly")

    client = await establish_connection(
        BleakClientWithServiceCache,
        device,
        name=device.name or device.address,
        disconnected_callback=on_disconnect,
        max_attempts=5  # Try up to 5 times
    )

    return client
```

### Example with Device Callback

Use a device callback when the device information might change (e.g., path changes on Linux):

```python
class DeviceTracker:
    def __init__(self, initial_device: BLEDevice):
        self.device = initial_device

    def get_device(self) -> BLEDevice:
        return self.device

    def update_device(self, new_device: BLEDevice):
        self.device = new_device

async def connect_with_device_tracking(tracker: DeviceTracker):
    client = await establish_connection(
        BleakClientWithServiceCache,
        tracker.device,
        name="TrackedDevice",
        ble_device_callback=tracker.get_device
    )

    return client
```

### Example with Custom Client Class

```python
from bleak import BleakClient

class CustomClient(BleakClient):
    async def custom_method(self):
        # Custom functionality
        pass

async def connect_with_custom_client(device: BLEDevice):
    client = await establish_connection(
        CustomClient,
        device,
        name=device.name,
        max_attempts=3
    )

    # Use custom methods
    await client.custom_method()

    return client
```

### Error Handling Example

```python
from bleak_retry_connector import (
    establish_connection,
    BleakClientWithServiceCache,
    BleakNotFoundError,
    BleakOutOfConnectionSlotsError,
    BleakAbortedError,
    BleakConnectionError
)

async def connect_with_error_handling(device: BLEDevice):
    try:
        client = await establish_connection(
            BleakClientWithServiceCache,
            device,
            name=device.name
        )
        return client

    except BleakNotFoundError:
        print("Device not found - it may have moved out of range")
        return None

    except BleakOutOfConnectionSlotsError:
        print("No connection slots available - try disconnecting other devices")
        return None

    except BleakAbortedError:
        print("Connection aborted - check for interference or move closer")
        return None

    except BleakConnectionError as e:
        print(f"Connection failed: {e}")
        return None
```

### Example with Cache Clearing on Missing Characteristic

When a device's firmware changes or services are updated, you might encounter missing characteristics. Here's how to handle this scenario by clearing the cache and retrying:

```python
from bleak_retry_connector import establish_connection, BleakClientWithServiceCache
from bleak.exc import BleakError

class CharacteristicMissingError(Exception):
    """Raised when a required characteristic is missing."""
    pass

async def connect_and_validate_services(device: BLEDevice):
    """Connect and validate required characteristics exist."""

    client = await establish_connection(
        BleakClientWithServiceCache,
        device,
        name=device.name or device.address,
        use_services_cache=True
    )

    try:
        # Check for required characteristics
        required_service_uuid = "cba20d00-224d-11e6-9fb8-0002a5d5c51b"
        required_char_uuid = "cba20002-224d-11e6-9fb8-0002a5d5c51b"

        service = client.services.get_service(required_service_uuid)
        if not service:
            raise CharacteristicMissingError(f"Service {required_service_uuid} not found")

        char = service.get_characteristic(required_char_uuid)
        if not char:
            raise CharacteristicMissingError(f"Characteristic {required_char_uuid} not found")

    except (CharacteristicMissingError, KeyError) as ex:
        # Services might have changed, clear cache and reconnect
        print(f"Characteristic missing, clearing cache: {ex}")
        await client.clear_cache()
        await client.disconnect()

        # Reconnect without cache
        client = await establish_connection(
            BleakClientWithServiceCache,
            device,
            name=device.name or device.address,
            use_services_cache=False  # Force fresh service discovery
        )

        # Validate again
        service = client.services.get_service(required_service_uuid)
        if not service:
            await client.disconnect()
            raise CharacteristicMissingError(f"Service {required_service_uuid} still not found after cache clear")

        char = service.get_characteristic(required_char_uuid)
        if not char:
            await client.disconnect()
            raise CharacteristicMissingError(f"Characteristic {required_char_uuid} still not found after cache clear")

    return client
```

### Advanced Configuration

```python
async def connect_with_full_options(device: BLEDevice):
    client = await establish_connection(
        BleakClientWithServiceCache,
        device,
        name="MyDevice",
        disconnected_callback=lambda c: print("Disconnected"),
        max_attempts=6,  # More attempts for difficult devices
        use_services_cache=True,  # Use caching for faster reconnects
        timeout=30.0  # Pass additional kwargs to BleakClient
    )

    return client
```

## Complete Working Example

```python
import asyncio
from bleak import BleakScanner
from bleak_retry_connector import (
    establish_connection,
    BleakClientWithServiceCache,
    BleakNotFoundError,
    BleakOutOfConnectionSlotsError,
    BleakAbortedError,
    BleakConnectionError
)

async def main():
    # Scan for devices
    print("Scanning for devices...")
    devices = await BleakScanner.discover()

    if not devices:
        print("No devices found")
        return

    # Connect to the first device found
    device = devices[0]
    print(f"Connecting to {device.name or device.address}...")

    try:
        # Establish connection with retry
        client = await establish_connection(
            BleakClientWithServiceCache,
            device,
            name=device.name or device.address,
            max_attempts=4
        )

        print("Connected successfully!")

        # List services
        for service in client.services:
            print(f"  Service: {service.uuid}")
            for char in service.characteristics:
                print(f"    Characteristic: {char.uuid}")

        # Disconnect
        await client.disconnect()
        print("Disconnected")

    except (BleakNotFoundError, BleakOutOfConnectionSlotsError,
            BleakAbortedError, BleakConnectionError) as e:
        print(f"Failed to connect: {e}")

if __name__ == "__main__":
    asyncio.run(main())
```
