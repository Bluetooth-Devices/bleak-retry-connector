"""Connection watchdog for monitoring BLE notification activity.

Detects "zombie" connections where BlueZ still reports Connected=True
but no notifications are being received — the radio link is effectively
dead without a disconnect callback ever firing.

Usage::

    watchdog = ConnectionWatchdog(
        timeout=180.0,
        on_timeout=my_reconnect_callback,
    )
    watchdog.start()

    # In your notification callback:
    watchdog.notify_activity()

    # When done:
    watchdog.stop()

Important: avoid ``async with BleakClient`` for long-lived connections.
Its ``__aexit__`` calls ``disconnect()`` without a timeout, which hangs
indefinitely in phantom states.  Always use explicit ``connect()`` /
``disconnect()`` with ``asyncio.wait_for(client.disconnect(), timeout=5.0)``.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable

_LOGGER = logging.getLogger(__name__)

DEFAULT_WATCHDOG_TIMEOUT = 180.0  # 3 minutes


class ConnectionWatchdog:
    """Monitor a BLE connection for notification activity.

    Tracks the time since the last :meth:`notify_activity` call.
    When the timeout is exceeded the optional *on_timeout* callback
    is invoked so the caller can trigger reconnection or cleanup.

    The monitoring loop runs as an ``asyncio.Task`` — no threads are
    needed for the normal case.

    Parameters
    ----------
    timeout:
        Seconds of inactivity before the watchdog fires.
    on_timeout:
        Async callback invoked when the timeout expires.  If ``None``,
        the watchdog only logs a warning.
    """

    def __init__(
        self,
        timeout: float = DEFAULT_WATCHDOG_TIMEOUT,
        on_timeout: Callable[[], Awaitable[None]] | None = None,
    ) -> None:
        self._timeout = timeout
        self._on_timeout = on_timeout
        self._last_activity: float = 0.0
        self._task: asyncio.Task[None] | None = None
        self._started = False

    @property
    def is_running(self) -> bool:
        """Return whether the watchdog is actively monitoring."""
        return self._started and self._task is not None and not self._task.done()

    @property
    def last_activity(self) -> float:
        """Return the monotonic timestamp of the last activity."""
        return self._last_activity

    def notify_activity(self) -> None:
        """Record that a notification or other activity was received.

        Call this from your BLE notification callback to reset the
        watchdog timer.
        """
        self._last_activity = time.monotonic()

    def start(self) -> None:
        """Start the watchdog monitoring loop.

        Records the current time as the initial activity timestamp and
        creates an asyncio task for the monitoring loop.  Calling
        ``start()`` on an already-running watchdog is a no-op.
        """
        if self._started:
            return
        self._last_activity = time.monotonic()
        self._started = True
        self._task = asyncio.ensure_future(self._monitor())

    def stop(self) -> None:
        """Stop the watchdog.

        Cancels the monitoring task.  Safe to call multiple times or
        before ``start()``.
        """
        self._started = False
        if self._task is not None:
            self._task.cancel()
            self._task = None

    async def _monitor(self) -> None:
        """Internal monitoring loop.

        Wakes up periodically and checks whether the inactivity timeout
        has been exceeded.  Uses a check interval of half the timeout
        (clamped to 1–30 s) so the actual fire time is at most one
        interval late.
        """
        check_interval = min(self._timeout / 2, 30.0)
        try:
            while self._started:
                await asyncio.sleep(check_interval)
                elapsed = time.monotonic() - self._last_activity
                if elapsed < self._timeout:
                    continue

                _LOGGER.warning(
                    "ConnectionWatchdog: no activity for %.1f s"
                    " (timeout %.1f s), firing callback",
                    elapsed,
                    self._timeout,
                )
                if self._on_timeout is not None:
                    try:
                        await self._on_timeout()
                    except Exception:
                        _LOGGER.exception(
                            "ConnectionWatchdog: on_timeout callback failed"
                        )
                break
        except asyncio.CancelledError:
            pass
        finally:
            self._started = False
