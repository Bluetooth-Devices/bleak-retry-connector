"""Adapter recovery and escalation chain for BLE connection failures.

Provides a configurable escalation policy that tracks consecutive
failures per adapter and recommends increasingly aggressive recovery
actions.  The policy respects caller configuration — it never suggests
an action the caller has disabled.

Escalation levels (least to most disruptive)::

    1. RETRY          — simple backoff retry
    2. DIAGNOSE       — diagnose stuck state + targeted fix (future PR 1)
    3. CLEAR_BLUEZ    — clear InProgress-dominant stale BlueZ state
    4. ROTATE_ADAPTER — switch to a different adapter
    5. RESET_ADAPTER  — hciconfig down/up (disrupts ALL connections)

Also provides:
- :class:`ToolCapabilities` for detecting available BLE shell tools
- :func:`reset_adapter` as a standalone last-resort utility
"""

from __future__ import annotations

import asyncio
import logging
import shutil
import subprocess  # nosec
import time
from dataclasses import dataclass
from enum import Enum

from .const import IS_LINUX

_LOGGER = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Tool capabilities — probed once at import
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ToolCapabilities:
    """Detected system tool availability — probed once at import time.

    All diagnostic and recovery code should check this object instead of
    calling ``shutil.which()`` ad-hoc.
    """

    bluetoothctl: str | None = None
    hcitool: str | None = None
    hciconfig: str | None = None
    rfkill: str | None = None

    @property
    def has_shell_tools(self) -> bool:
        """True if the core diagnostic tools are available."""
        return self.bluetoothctl is not None and self.hcitool is not None

    @property
    def can_reset_adapter(self) -> bool:
        """True if adapter reset is possible."""
        return self.hciconfig is not None

    @property
    def can_diagnose(self) -> bool:
        """True if precise stuck-state diagnosis is possible."""
        return self.has_shell_tools

    @classmethod
    def detect(cls) -> ToolCapabilities:
        """Probe the system for available BLE tools.

        Called once at module import.  Results are cached for the
        lifetime of the process.
        """
        return cls(
            bluetoothctl=shutil.which("bluetoothctl"),
            hcitool=shutil.which("hcitool"),
            hciconfig=shutil.which("hciconfig"),
            rfkill=shutil.which("rfkill"),
        )


TOOLS = ToolCapabilities.detect()


# ---------------------------------------------------------------------------
# Escalation configuration
# ---------------------------------------------------------------------------


class EscalationAction(str, Enum):
    """Actions the escalation policy can recommend."""

    RETRY = "retry"
    DIAGNOSE = "diagnose"
    CLEAR_BLUEZ = "clear_bluez"
    ROTATE_ADAPTER = "rotate"
    RESET_ADAPTER = "reset"


# Ordered from least to most disruptive
_LEVELS = list(EscalationAction)


@dataclass
class EscalationConfig:
    """Configuration for the recovery escalation chain.

    Each escalation level can be individually enabled or disabled.
    Thresholds control when each level triggers.

    Parameters
    ----------
    diagnose_and_fix:
        Enable stuck-state diagnosis + targeted fix.  Almost always
        ``True``.
    clear_bluez_on_inprogress_dominance:
        Enable BlueZ state cleanup when ``InProgress`` errors dominate
        all adapters.
    rotate_adapter:
        Enable adapter rotation on failure.  Requires multiple adapters.
    reset_adapter:
        Enable adapter reset as last resort.  **WARNING:** disrupts ALL
        connections on the adapter.  Only enable if this service "owns"
        the adapter or coordinates with others.  Default ``False``.
    rotate_after:
        Consecutive failures before rotating adapter.
    clear_after:
        Consecutive ``InProgress`` failures before BlueZ cleanup.
    reset_after:
        Consecutive failures before adapter reset.
    reset_cooldown:
        Minimum seconds between adapter resets.
    max_escalation:
        Hard ceiling on escalation.  Even if ``reset_adapter`` is
        ``True``, setting ``max_escalation`` to
        :attr:`EscalationAction.ROTATE_ADAPTER` prevents reset.
    """

    diagnose_and_fix: bool = True
    clear_bluez_on_inprogress_dominance: bool = True
    rotate_adapter: bool = True
    reset_adapter: bool = False
    rotate_after: int = 2
    clear_after: int = 4
    reset_after: int = 6
    reset_cooldown: float = 300.0
    max_escalation: EscalationAction = EscalationAction.RESET_ADAPTER


# Pre-built profiles for common service types
PROFILE_BATTERY = EscalationConfig(
    reset_adapter=True,
    reset_after=6,
    reset_cooldown=300.0,
)

PROFILE_SENSOR = EscalationConfig(
    reset_adapter=False,
    max_escalation=EscalationAction.ROTATE_ADAPTER,
)

PROFILE_ON_DEMAND = EscalationConfig(
    clear_bluez_on_inprogress_dominance=False,
    reset_adapter=False,
    rotate_after=1,
    max_escalation=EscalationAction.ROTATE_ADAPTER,
)


# ---------------------------------------------------------------------------
# Escalation policy
# ---------------------------------------------------------------------------


class EscalationPolicy:
    """Track consecutive failures per adapter and decide escalation level.

    The policy respects the caller's :class:`EscalationConfig` — it will
    never suggest an action the caller has disabled.

    Example::

        config = EscalationConfig(reset_adapter=False)  # sensor service
        policy = EscalationPolicy(["hci0", "hci1"], config=config)

        action = policy.on_failure("hci0")
        # action will never be RESET_ADAPTER because config disabled it

        policy.on_success("hci0")  # resets failure counter
    """

    def __init__(
        self,
        adapters: list[str],
        config: EscalationConfig | None = None,
    ) -> None:
        self._config = config or EscalationConfig()
        self._adapters = adapters
        self._max_level_idx = _LEVELS.index(self._config.max_escalation)
        self._failures: dict[str, int] = {a: 0 for a in adapters}
        self._last_reset: dict[str, float] = {a: 0.0 for a in adapters}

    @property
    def config(self) -> EscalationConfig:
        """Return the current escalation configuration."""
        return self._config

    def on_failure(self, adapter: str) -> EscalationAction:
        """Record a failure and return the next escalation action.

        The returned action will never exceed *max_escalation* or
        suggest a disabled level.
        """
        self._failures[adapter] = self._failures.get(adapter, 0) + 1
        count = self._failures[adapter]

        if (
            count >= self._config.reset_after
            and self._is_level_enabled(EscalationAction.RESET_ADAPTER)
            and self._can_reset(adapter)
        ):
            return EscalationAction.RESET_ADAPTER

        if count >= self._config.clear_after and self._is_level_enabled(
            EscalationAction.CLEAR_BLUEZ
        ):
            return EscalationAction.CLEAR_BLUEZ

        if count >= self._config.rotate_after and self._is_level_enabled(
            EscalationAction.ROTATE_ADAPTER
        ):
            return EscalationAction.ROTATE_ADAPTER

        if count >= 1 and self._is_level_enabled(EscalationAction.DIAGNOSE):
            return EscalationAction.DIAGNOSE

        return EscalationAction.RETRY

    def on_success(self, adapter: str) -> None:
        """Record a success — resets the failure counter for *adapter*."""
        self._failures[adapter] = 0

    def record_reset(self, adapter: str) -> None:
        """Record that an adapter reset was performed."""
        self._last_reset[adapter] = time.monotonic()
        self._failures[adapter] = 0

    def _is_level_enabled(self, level: EscalationAction) -> bool:
        """Check if a given escalation level is enabled in config."""
        if _LEVELS.index(level) > self._max_level_idx:
            return False
        level_config_map = {
            EscalationAction.DIAGNOSE: self._config.diagnose_and_fix,
            EscalationAction.CLEAR_BLUEZ: (
                self._config.clear_bluez_on_inprogress_dominance
            ),
            EscalationAction.ROTATE_ADAPTER: self._config.rotate_adapter,
            EscalationAction.RESET_ADAPTER: self._config.reset_adapter,
        }
        return level_config_map.get(level, True)

    def _can_reset(self, adapter: str) -> bool:
        """Check if enough time has passed since the last reset."""
        last = self._last_reset.get(adapter, 0.0)
        return (time.monotonic() - last) >= self._config.reset_cooldown


# ---------------------------------------------------------------------------
# Adapter reset utility
# ---------------------------------------------------------------------------


async def reset_adapter(
    adapter: str,
    restart_bluetoothd: bool = True,
) -> bool:
    """Reset a BLE adapter as a last resort.

    This should only be called after all other recovery mechanisms have
    failed.  It temporarily disrupts **ALL** BLE connections on the
    adapter.

    Sequence:

    1. ``hciconfig <adapter> down``
    2. sleep 1.0 s
    3. ``hciconfig <adapter> up``
    4. If *restart_bluetoothd* is ``True``, check whether ``bluetoothd``
       survived the reset and restart it if not.

    On Venus OS, ``bluetoothd`` can crash during adapter reset.  The
    code checks ``pidof bluetoothd`` and restarts the daemon if it is
    not running.

    Returns ``True`` if the reset appeared successful (adapter is UP
    and ``bluetoothd`` is running).
    """
    if not IS_LINUX:
        return False
    if not TOOLS.can_reset_adapter:
        _LOGGER.warning(
            "Cannot reset %s: hciconfig not found",
            adapter,
        )
        return False

    hciconfig = TOOLS.hciconfig
    assert hciconfig is not None  # nosec — checked above

    _LOGGER.warning("Resetting adapter %s (hciconfig down/up)", adapter)

    try:
        subprocess.run(  # nosec
            [hciconfig, adapter, "down"],
            capture_output=True,
            timeout=5,
        )
    except Exception:
        _LOGGER.exception("Failed to bring %s down", adapter)
        return False

    await asyncio.sleep(1.0)

    try:
        result = subprocess.run(  # nosec
            [hciconfig, adapter, "up"],
            capture_output=True,
            timeout=5,
        )
        if result.returncode != 0:
            _LOGGER.error(
                "hciconfig %s up failed: %s",
                adapter,
                result.stderr.decode(errors="replace"),
            )
            return False
    except Exception:
        _LOGGER.exception("Failed to bring %s up", adapter)
        return False

    if restart_bluetoothd:
        await asyncio.sleep(0.5)
        try:
            pidof = subprocess.run(  # nosec
                ["pidof", "bluetoothd"],
                capture_output=True,
                timeout=3,
            )
            if pidof.returncode != 0:
                _LOGGER.warning(
                    "bluetoothd not running after %s reset, restarting",
                    adapter,
                )
                subprocess.run(  # nosec
                    ["/etc/init.d/bluetooth", "start"],
                    capture_output=True,
                    timeout=10,
                )
                await asyncio.sleep(3.0)
        except Exception:
            _LOGGER.debug(
                "Failed to check/restart bluetoothd",
                exc_info=True,
            )

    _LOGGER.info("Adapter %s reset complete", adapter)
    return True
