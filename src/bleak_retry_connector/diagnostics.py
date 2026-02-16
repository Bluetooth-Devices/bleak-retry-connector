"""Stuck-state diagnosis and targeted recovery for BLE connections.

Provides :func:`diagnose_stuck_state` to determine why a BLE connection
is stuck, and :func:`clear_stuck_state` to apply the minimal targeted
fix for each diagnosis.

The diagnostic approach is *layered*:

Layer 1 — HCI handle cross-reference (shell tools, most reliable):
    When ``bluetoothctl`` and ``hcitool`` are available (standard on
    Venus OS, Raspberry Pi, most embedded Linux), cross-references
    BlueZ D-Bus ``Connected`` with actual HCI handles.

Layer 2 — D-Bus heuristics (fallback):
    When shell tools are unavailable, falls back to ``clear_cache()``
    via the D-Bus API.
"""

from __future__ import annotations

import asyncio
import logging
import re
import shutil
from enum import Enum

from .const import IS_LINUX

_LOGGER = logging.getLogger(__name__)

# Shell tool paths — probed once at first use
_bluetoothctl: str | None = None
_hcitool: str | None = None
_tools_probed = False


def _probe_tools() -> None:
    """Probe for available shell tools (once)."""
    global _bluetoothctl, _hcitool, _tools_probed  # noqa: PLW0603
    if _tools_probed:
        return
    _bluetoothctl = shutil.which("bluetoothctl")
    _hcitool = shutil.which("hcitool")
    _tools_probed = True


def _has_shell_tools() -> bool:
    """Return True if the core diagnostic shell tools are available."""
    _probe_tools()
    return _bluetoothctl is not None and _hcitool is not None


class StuckState(Enum):
    """Diagnosis of why a BLE connection is stuck.

    Each value maps to a specific, minimal recovery action in
    :func:`clear_stuck_state`.
    """

    NOT_STUCK = "not_stuck"
    PHANTOM_NO_HANDLE = "phantom_no_handle"
    DEAD_HANDLE = "dead_handle"
    PENDING_LE_CREATE = "pending_le_create"
    STALE_CACHE = "stale_cache"


# ---------------------------------------------------------------------------
# Shell-based helpers (Layer 1)
# ---------------------------------------------------------------------------


async def _run_cmd(*args: str, timeout: float = 5.0) -> tuple[int, str]:
    """Run a shell command and return (returncode, stdout)."""
    try:
        proc = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await asyncio.wait_for(
            proc.communicate(), timeout=timeout
        )
        return proc.returncode or 0, stdout.decode(errors="replace")
    except (asyncio.TimeoutError, OSError) as exc:
        _LOGGER.debug("Command %s failed: %s", args, exc)
        return -1, ""


async def _is_bluez_connected(address: str) -> bool:
    """Check if BlueZ D-Bus reports the device as Connected."""
    assert _bluetoothctl is not None  # nosec
    rc, stdout = await _run_cmd(_bluetoothctl, "info", address)
    if rc != 0:
        return False
    return "Connected: yes" in stdout


async def _get_hci_handle(
    address: str, adapter: str
) -> str | None:
    """Return the HCI connection handle for *address* on *adapter*, or None."""
    assert _hcitool is not None  # nosec
    rc, stdout = await _run_cmd(_hcitool, "-i", adapter, "con")
    if rc != 0:
        return None
    addr_upper = address.upper()
    for line in stdout.splitlines():
        if addr_upper in line.upper():
            match = re.search(r"handle\s+(\d+)", line)
            if match:
                return match.group(1)
    return None


async def _is_services_resolved(address: str) -> bool:
    """Check if BlueZ reports ServicesResolved for the device."""
    assert _bluetoothctl is not None  # nosec
    rc, stdout = await _run_cmd(_bluetoothctl, "info", address)
    if rc != 0:
        return False
    return "ServicesResolved: yes" in stdout


async def _has_pending_le_connection(adapter: str) -> bool:
    """Heuristic: try LE Create Connection Cancel and see if it succeeds.

    If there is a pending LE Create Connection, the cancel command
    (OGF 0x08, OCF 0x000E) succeeds.  If there is no pending
    connection, it returns an error.

    This is a non-destructive probe when there is no pending connection.
    """
    assert _hcitool is not None  # nosec
    rc, stdout = await _run_cmd(
        _hcitool, "-i", adapter, "cmd", "0x08", "0x000E"
    )
    if rc != 0:
        return False
    # If the cancel returned status 0x00 in the response, there WAS
    # a pending connection.  Status 0x0C means "Command Disallowed"
    # (no pending connection).  We check for success.
    return "status 0x00" in stdout.lower() or rc == 0


async def _has_bluez_cache_entry(address: str) -> bool:
    """Check if BlueZ has a cache entry for the device."""
    assert _bluetoothctl is not None  # nosec
    rc, stdout = await _run_cmd(_bluetoothctl, "info", address)
    if rc != 0:
        return False
    # If bluetoothctl returns info, there's a cache entry
    return "Device" in stdout and address.upper() in stdout.upper()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def diagnose_stuck_state(
    address: str,
    adapter: str,
) -> StuckState:
    """Determine what kind of stuck state a device is in.

    Uses shell tools (``bluetoothctl``, ``hcitool``) when available for
    precise diagnosis.  Returns :attr:`StuckState.NOT_STUCK` if the
    device appears healthy or diagnosis is not possible.

    Parameters
    ----------
    address:
        The BLE device MAC address.
    adapter:
        The adapter name (e.g. ``hci0``).
    """
    if not IS_LINUX or not _has_shell_tools():
        return StuckState.NOT_STUCK

    # 1. Is BlueZ reporting Connected?
    bluez_connected = await _is_bluez_connected(address)

    # 2. Does an HCI handle actually exist?
    handle = await _get_hci_handle(address, adapter)

    if bluez_connected and not handle:
        return StuckState.PHANTOM_NO_HANDLE

    if bluez_connected and handle:
        services_resolved = await _is_services_resolved(address)
        if not services_resolved:
            return StuckState.DEAD_HANDLE

    if not bluez_connected:
        pending = await _has_pending_le_connection(adapter)
        if pending:
            return StuckState.PENDING_LE_CREATE

        has_cache = await _has_bluez_cache_entry(address)
        if has_cache:
            return StuckState.STALE_CACHE

    return StuckState.NOT_STUCK


async def clear_stuck_state(
    address: str,
    adapter: str,
    state: StuckState,
) -> bool:
    """Apply the targeted fix for a diagnosed stuck state.

    Each state has a specific, minimal cleanup action.  This avoids the
    "shotgun" approach of running every possible cleanup command.

    Returns ``True`` if the cleanup action was executed.
    """
    if state == StuckState.NOT_STUCK:
        return True

    if not IS_LINUX or not _has_shell_tools():
        # Fall back to D-Bus-only cleanup
        from .bluez import clear_cache

        await clear_cache(address)
        return True

    assert _bluetoothctl is not None  # nosec
    assert _hcitool is not None  # nosec

    if state == StuckState.PHANTOM_NO_HANDLE:
        _LOGGER.info(
            "%s: Clearing phantom (BlueZ Connected, no HCI handle)",
            address,
        )
        await _run_cmd(_bluetoothctl, "remove", address)
        return True

    if state == StuckState.DEAD_HANDLE:
        handle = await _get_hci_handle(address, adapter)
        if handle:
            _LOGGER.info(
                "%s: Dropping dead HCI handle %s on %s",
                address,
                handle,
                adapter,
            )
            await _run_cmd(_hcitool, "-i", adapter, "ledc", handle)
        return True

    if state == StuckState.PENDING_LE_CREATE:
        _LOGGER.info(
            "%s: Cancelling pending LE Create Connection on %s",
            address,
            adapter,
        )
        await _run_cmd(
            _hcitool, "-i", adapter, "cmd", "0x08", "0x000E"
        )
        return True

    if state == StuckState.STALE_CACHE:
        _LOGGER.info(
            "%s: Removing stale BlueZ cache entry",
            address,
        )
        await _run_cmd(_bluetoothctl, "remove", address)
        return True

    _LOGGER.debug(  # type: ignore[unreachable]
        "%s: Unhandled stuck state %s", address, state
    )
    return False
