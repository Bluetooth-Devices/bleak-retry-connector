from __future__ import annotations

import platform
from dataclasses import dataclass

IS_LINUX = platform.system() == "Linux"
NO_RSSI_VALUE = -127
RSSI_SWITCH_THRESHOLD = 5
DISCONNECT_TIMEOUT = 5
REAPPEAR_WAIT_INTERVAL = 0.5
DBUS_CONNECT_TIMEOUT = 8.5


@dataclass
class LockConfig:
    """Configuration for cross-process BLE serialization locks.

    On multi-service systems (e.g. Venus OS / Cerbo GX) several processes
    may compete for the same BLE adapter, causing ``InProgress`` errors
    on ~40 %% of connection attempts.  A per-adapter file lock serializes
    these operations so only one process uses a given adapter at a time.

    All services sharing adapters on the same host **must** use the same
    *lock_dir* and *lock_template* to coordinate.

    Parameters
    ----------
    enabled:
        Whether cross-process locking is active.
    lock_dir:
        Directory for lock files.  Must be writable by all participating
        services.
    lock_template:
        Template string with an ``{adapter}`` placeholder, e.g.
        ``"bleak-retry-connector-{adapter}.lock"``.
    lock_timeout:
        Maximum seconds to wait for lock acquisition.  If exceeded, the
        connection attempt proceeds without the lock (graceful
        degradation) to prevent deadlock when a lock holder crashes.
    """

    enabled: bool = False
    lock_dir: str = "/tmp"  # nosec
    lock_template: str = "bleak-retry-connector-{adapter}.lock"
    lock_timeout: float = 15.0

    def path_for_adapter(self, adapter: str | None) -> str:
        """Return the full lock file path for a given adapter."""
        name = adapter or "default"
        filename = self.lock_template.format(adapter=name)
        return f"{self.lock_dir}/{filename}"
