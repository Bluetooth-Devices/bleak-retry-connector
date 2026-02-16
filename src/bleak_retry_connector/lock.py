"""Cross-process file locking for BLE adapter serialization.

On multi-service systems several processes may compete for the same BLE
adapter, causing ``InProgress`` errors.  This module provides async-safe
``fcntl.flock`` helpers that serialize BLE operations per adapter without
blocking the asyncio event loop.

The lock is **non-blocking** (``LOCK_NB``).  If the lock is held by
another process, the caller retries with ``asyncio.sleep()`` between
attempts.  If acquisition times out, the caller proceeds without the
lock (graceful degradation).

``fcntl.flock`` is automatically released when the file descriptor is
closed — including process exit — so a crashed process cannot hold the
lock permanently.
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .const import LockConfig

try:
    import fcntl

    _HAS_FCNTL = True
except ImportError:
    _HAS_FCNTL = False

_LOGGER = logging.getLogger(__name__)

_LOCK_RETRY_INTERVAL = 0.25


async def acquire_lock(
    lock_config: LockConfig,
    adapter: str | None,
) -> int | None:
    """Acquire an exclusive file lock for the given adapter.

    Returns the file descriptor on success, or ``None`` if the lock
    could not be acquired within *lock_config.lock_timeout* seconds.
    When ``None`` is returned the caller should proceed without the
    lock (graceful degradation).
    """
    if not _HAS_FCNTL or not lock_config.enabled:
        return None

    lock_path = lock_config.path_for_adapter(adapter)
    elapsed = 0.0

    try:
        fd = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o666)
    except OSError:
        _LOGGER.debug(
            "Failed to open lock file %s, proceeding without lock",
            lock_path,
            exc_info=True,
        )
        return None

    while True:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            _LOGGER.debug("Acquired BLE lock %s (adapter=%s)", lock_path, adapter)
            return fd
        except OSError:
            elapsed += _LOCK_RETRY_INTERVAL
            if elapsed >= lock_config.lock_timeout:
                _LOGGER.warning(
                    "Timed out waiting for BLE lock %s after %.1f s"
                    " — proceeding without lock",
                    lock_path,
                    elapsed,
                )
                os.close(fd)
                return None
            await asyncio.sleep(_LOCK_RETRY_INTERVAL)


def release_lock(fd: int | None) -> None:
    """Release a previously acquired file lock.

    Safe to call with ``None`` (no-op).
    """
    if fd is None:
        return
    try:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)
    except OSError:
        _LOGGER.debug("Failed to release BLE lock", exc_info=True)
