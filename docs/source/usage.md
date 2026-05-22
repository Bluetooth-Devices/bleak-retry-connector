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
- **Connection parameter tuning**: Call `set_connection_params()` to adjust BLE connection intervals
- **Drop-in replacement**: Can be used anywhere `BleakClient` is used

### Extension Methods

`BleakClientWithServiceCache` provides extension methods that are forwarded to the underlying backend (e.g., habluetooth). These methods allow integrations to control BLE behavior beyond what standard bleak provides.

#### clear_cache

```python
async def clear_cache(self) -> bool
```

Clears the cached GATT services, forcing a fresh service discovery on the next access. Useful when a device's firmware has been updated or services have changed.

Returns `True` if the cache was successfully cleared, `False` otherwise.

```python
client = await establish_connection(
    BleakClientWithServiceCache, device, name="MyDevice"
)

# If characteristics are missing, clear cache and reconnect
await client.clear_cache()
await client.disconnect()
```

#### set_connection_params

```python
async def set_connection_params(
    self,
    min_interval: int,
    max_interval: int,
    latency: int,
    timeout: int,
) -> None
```

Sets BLE connection parameters on a connected device. This is useful for "Always Connected" devices where battery conservation is important — switching from fast intervals (~7.5ms) to slow intervals (e.g., 1000ms) after the initial data sync can significantly reduce power consumption.

Parameters are in BLE units:

- **min_interval** / **max_interval**: Connection interval in units of 1.25ms (e.g., 800 = 1000ms)
- **latency**: Number of connection events the peripheral can skip (typically 0)
- **timeout**: Supervision timeout in units of 10ms (e.g., 600 = 6000ms)

```python
client = await establish_connection(
    BleakClientWithServiceCache, device, name="MyDevice"
)

# After initial sync, switch to slow intervals to save battery
await client.set_connection_params(
    min_interval=800,   # 1000ms
    max_interval=800,   # 1000ms
    latency=0,
    timeout=600,        # 6000ms
)
```

The method delegates to the backend (habluetooth), which routes to either:

- **ESPHome proxy**: Sends a protobuf message to the ESP32 to call `esp_ble_gap_update_conn_params()`
- **Local BlueZ adapter**: Uses the MGMT API (`MGMT_OP_LOAD_CONN_PARAM`)

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
    pair: bool = False,
    validate_connection: Callable[[BleakClient], Awaitable[bool]] | None = None,
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
- **pair**: Whether to pair with the device on connect (default: False)
- **validate_connection**: Optional async callback that decides whether a freshly
  connected client is actually usable. Useful when `connect()` succeeds but the
  link is non-functional — phantom BlueZ `Connected=True`, empty
  `client.services` after GATT discovery, dead firmware that never answers a
  read. When provided, it is awaited after each successful `connect()`; a
  return of `False` (or any raised exception) is treated as a connection
  failure, the client is disconnected, and the retry budget is shared with
  ordinary connect failures. The validator runs under the same
  `BLEAK_SAFETY_TIMEOUT` bound as `connect()` itself, so a hung validator
  cannot stall `establish_connection` indefinitely — but callers should still
  wrap their own GATT reads/writes in `asyncio.wait_for` to surface
  diagnostics earlier.
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

### Example with Connection Validation

Some failure modes leave `connect()` returning a client that looks healthy but
is actually unusable (phantom `Connected=True`, empty service discovery, dead
firmware). The `validate_connection` callback lets you verify the link before
the client is handed back — failed validation disconnects and retries on the
existing `max_attempts` budget.

```python
async def validate(client: BleakClient) -> bool:
    # Probe the device with the read your app needs to succeed. The validator
    # runs under BLEAK_SAFETY_TIMEOUT, but wrapping individual GATT calls in
    # asyncio.wait_for surfaces the diagnostic earlier than the safety bound.
    try:
        data = await asyncio.wait_for(
            client.read_gatt_char("0000fff1-0000-1000-8000-00805f9b34fb"),
            timeout=5.0,
        )
    except (BleakError, asyncio.TimeoutError):
        return False
    return len(data) > 0

client = await establish_connection(
    BleakClientWithServiceCache,
    device,
    name="MyDevice",
    validate_connection=validate,
)
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

## retry_bluetooth_connection_error

A decorator that wraps an async function and retries it on transient Bleak
errors. Useful for short GATT operations (reads, writes, notifications) that
can be disconnected mid-flight by the device.

### Function Signature

```python
def retry_bluetooth_connection_error(
    attempts: int = 2,
) -> Callable[[Callable[P, Awaitable[T]]], Callable[P, Awaitable[T]]]
```

### Parameters

- **attempts**: Number of times to attempt the wrapped call before re-raising
  the underlying error (default: 2).

The decorator catches the same `BLEAK_EXCEPTIONS` group used internally by
`establish_connection` and backs off with `calculate_backoff_time()` between
attempts. After the final attempt fails, the original exception propagates.

### Example

```python
from bleak_retry_connector import (
    establish_connection,
    BleakClientWithServiceCache,
    retry_bluetooth_connection_error,
)

@retry_bluetooth_connection_error(attempts=3)
async def read_battery(client: BleakClientWithServiceCache) -> int:
    data = await client.read_gatt_char("00002a19-0000-1000-8000-00805f9b34fb")
    return data[0]

async def main(device):
    client = await establish_connection(
        BleakClientWithServiceCache, device, name=device.name
    )
    try:
        level = await read_battery(client)
        print(f"Battery: {level}%")
    finally:
        await client.disconnect()
```

## close_stale_connections

On Linux/BlueZ, BlueZ may report a device as connected even when another
adapter or a crashed process owns the connection. `close_stale_connections`
disconnects those existing connections so a fresh `establish_connection`
attempt can proceed.

Two variants are exported:

```python
async def close_stale_connections(
    device: BLEDevice, only_other_adapters: bool = False
) -> None

async def close_stale_connections_by_address(
    address: str, only_other_adapters: bool = False
) -> None
```

- **device** / **address**: The target device or its MAC address.
- **only_other_adapters**: If `True`, only disconnect instances on adapters
  different from the one the supplied `device` is on. Useful when you want
  to keep your own active connection alive while clearing duplicates that
  appeared on another adapter.

Both functions are no-ops on non-Linux platforms.

### Example

```python
from bleak_retry_connector import (
    close_stale_connections_by_address,
    establish_connection,
    BleakClientWithServiceCache,
)

# Before reconnecting after a service restart, clear stale BlueZ state:
await close_stale_connections_by_address("AA:BB:CC:DD:EE:FF")

client = await establish_connection(
    BleakClientWithServiceCache, device, name=device.name
)
```

## clear_cache

Removes a device from BlueZ via the `RemoveDevice` D-Bus method. This clears
cached GATT services and any stale `Connected=True` state BlueZ may be
holding for the address.

```python
async def clear_cache(address: str) -> bool
```

- **address**: The MAC address of the device to remove.
- **Returns**: `True` if the device was removed, `False` otherwise (including
  on non-Linux platforms).

`clear_cache()` is safe to call unconditionally — it suppresses all errors
internally and returns `False` rather than raising. There is also an instance
method `BleakClientWithServiceCache.clear_cache()` (documented above) which
clears only the bleak-level service cache for an already-connected client;
the module-level `clear_cache(address)` operates on BlueZ directly and does
not require a client.

### Example

```python
from bleak_retry_connector import clear_cache

# After a firmware update, force BlueZ to forget cached services:
await clear_cache("AA:BB:CC:DD:EE:FF")
```

## restore_discoveries

On Linux/BlueZ, advertisement data tracked by BlueZ can be lost when a
scanner is recreated. `restore_discoveries` re-seeds a freshly created
`BleakScanner` with the devices BlueZ already knows about, so callers don't
have to wait for the next advertisement to see existing devices.

```python
async def restore_discoveries(scanner: BleakScanner, adapter: str) -> None
```

- **scanner**: The newly created `BleakScanner` instance.
- **adapter**: The HCI adapter name (e.g. `"hci0"`).

No-op on non-Linux platforms.

## get_device / get_device_by_adapter

Look up a `BLEDevice` by MAC address against BlueZ's current view of the bus.
Useful when a caller has lost its `BLEDevice` handle (e.g. after a scanner
restart) but still knows the address.

```python
async def get_device(address: str) -> BLEDevice | None
async def get_device_by_adapter(address: str, adapter: str) -> BLEDevice | None
```

- **address**: The MAC address of the device.
- **adapter** (`get_device_by_adapter` only): The HCI adapter name (e.g.
  `"hci0"`) to restrict the lookup to a single controller.

`get_device` searches every adapter and returns the device with the strongest
RSSI; `get_device_by_adapter` only inspects the BlueZ object at
`/org/bluez/<adapter>/dev_<ADDR>` and returns `None` if no device exists on
that adapter.

Both return `None` on non-Linux platforms and when BlueZ has no matching
object.

```python
from bleak_retry_connector import get_device, establish_connection, BleakClientWithServiceCache

device = await get_device("AA:BB:CC:DD:EE:FF")
if device is None:
    raise RuntimeError("device not currently known to BlueZ")

client = await establish_connection(
    BleakClientWithServiceCache, device, name=device.name
)
```

## device_source

Return the `source` tag from a `BLEDevice`'s `details` mapping, or `None` if
the tag is absent. The source is set by the scanner that produced the
advertisement — for example, ESPHome Bluetooth proxies tag their devices with
the proxy name. Native BlueZ devices typically have no source.

```python
def device_source(device: BLEDevice) -> str | None
```

```python
from bleak_retry_connector import device_source

if device_source(device) is None:
    # Local adapter device — slot management applies.
    ...
else:
    # Came from an ESPHome proxy — handle ESP-specific errors.
    ...
```

## ble_device_description

Format a `BLEDevice` into a short, log-friendly string of the form
`<address> - <name> -> <path-or-source>`. Used by `establish_connection`
internally for log lines; exported so callers can produce the same format in
their own diagnostics.

```python
def ble_device_description(device: BLEDevice) -> str
```

The trailing `-> ...` is only appended when the device's `details` carry a
BlueZ `path` (truncated to 15 characters) or a `source` tag. Devices with
neither are described as `<address> - <name>` (or just `<address>` when the
name equals the address).

## BleakSlotManager

`BleakSlotManager` tracks how many BLE connection slots each local BlueZ
adapter has free and which addresses currently hold a slot. It is intended
for callers that orchestrate multiple connections across multiple adapters
(e.g. Home Assistant) and need to make scheduling decisions before calling
`establish_connection`.

```python
from bleak_retry_connector import BleakSlotManager

manager = BleakSlotManager()
await manager.async_setup()

# Tell the manager about each adapter and its slot capacity:
manager.register_adapter("hci0", slots=5)
manager.register_adapter("hci1", slots=5)

allocations = manager.get_allocations("hci0")
print(allocations.free, allocations.allocated)
```

Key methods:

- **`async_setup()`** — Attach to the global BlueZ manager. Must be awaited
  before any other call.
- **`register_adapter(adapter, slots)`** / **`remove_adapter(adapter)`** —
  Declare or forget an adapter and its slot capacity. On registration,
  devices that BlueZ already reports as connected on the adapter are
  pre-allocated.
- **`get_allocations(adapter)`** — Return an `Allocations` dataclass
  describing the adapter (`slots`, `free`, list of allocated addresses).
- **`release_slot(device)`** — Manually release a slot held by `device`.
  Normally unnecessary: the manager watches BlueZ's `Connected` property and
  releases automatically on disconnect.
- **`register_allocation_callback(callback)`** — Subscribe to
  `AllocationChangeEvent`s (allocated / released). Returns an unsubscribe
  callable.
- **`diagnostics()`** — Return a JSON-friendly snapshot for logging.

`BleakSlotManager` only sees BlueZ adapters; ESPHome proxy slots are tracked
by the proxy itself and reported through habluetooth. On non-Linux platforms
the manager can be constructed but `async_setup()` will not find a BlueZ
manager to attach to.

## Constants

- **`BLEAK_RETRY_EXCEPTIONS`**: A tuple of exception classes that
  `establish_connection` and `retry_bluetooth_connection_error` treat as
  transient and retryable: `AttributeError`, `BleakError`, `EOFError`,
  `BrokenPipeError`, and `asyncio.TimeoutError`. Re-exported so callers
  layering their own retry logic on top can match the same set.

- **`NO_RSSI_VALUE`** (`-127`): Sentinel value used internally when an
  advertisement carries no RSSI. Exported so callers ranking devices by
  signal strength can use the same floor.

- **`RSSI_SWITCH_THRESHOLD`** (`5`): Minimum RSSI delta in dBm that
  `establish_connection` requires before switching to a stronger advertised
  path mid-retry. Exposed for callers that want to apply the same hysteresis
  to their own adapter-selection logic.
