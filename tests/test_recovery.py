"""Tests for the recovery / escalation chain module."""

from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

import pytest

from bleak_retry_connector.recovery import (
    PROFILE_BATTERY,
    PROFILE_ON_DEMAND,
    PROFILE_SENSOR,
    TOOLS,
    EscalationAction,
    EscalationConfig,
    EscalationPolicy,
    ToolCapabilities,
    reset_adapter,
)

# ---------------------------------------------------------------------------
# ToolCapabilities tests
# ---------------------------------------------------------------------------


class TestToolCapabilities:
    """Tests for ToolCapabilities detection and properties."""

    def test_detect_returns_instance(self):
        """detect() should return a ToolCapabilities instance."""
        caps = ToolCapabilities.detect()
        assert isinstance(caps, ToolCapabilities)

    def test_has_shell_tools_requires_both(self):
        """has_shell_tools needs both bluetoothctl and hcitool."""
        caps = ToolCapabilities(bluetoothctl="/usr/bin/bluetoothctl", hcitool=None)
        assert caps.has_shell_tools is False

        caps = ToolCapabilities(
            bluetoothctl="/usr/bin/bluetoothctl", hcitool="/usr/bin/hcitool"
        )
        assert caps.has_shell_tools is True

    def test_can_reset_adapter(self):
        """can_reset_adapter needs hciconfig."""
        caps = ToolCapabilities(hciconfig=None)
        assert caps.can_reset_adapter is False

        caps = ToolCapabilities(hciconfig="/usr/bin/hciconfig")
        assert caps.can_reset_adapter is True

    def test_can_diagnose(self):
        """can_diagnose is the same as has_shell_tools."""
        caps = ToolCapabilities(
            bluetoothctl="/usr/bin/bluetoothctl", hcitool="/usr/bin/hcitool"
        )
        assert caps.can_diagnose is True

    def test_frozen_dataclass(self):
        """ToolCapabilities should be immutable."""
        caps = ToolCapabilities(bluetoothctl="/usr/bin/bluetoothctl")
        with pytest.raises(AttributeError):
            caps.bluetoothctl = "/other/path"  # type: ignore[misc]

    def test_module_level_tools_singleton(self):
        """TOOLS module-level singleton should be a ToolCapabilities instance."""
        assert isinstance(TOOLS, ToolCapabilities)


# ---------------------------------------------------------------------------
# EscalationConfig tests
# ---------------------------------------------------------------------------


class TestEscalationConfig:
    """Tests for EscalationConfig defaults and profiles."""

    def test_defaults(self):
        """Default config has safe defaults."""
        cfg = EscalationConfig()
        assert cfg.diagnose_and_fix is True
        assert cfg.clear_bluez_on_inprogress_dominance is True
        assert cfg.rotate_adapter is True
        assert cfg.reset_adapter is False
        assert cfg.rotate_after == 2
        assert cfg.clear_after == 4
        assert cfg.reset_after == 6
        assert cfg.reset_cooldown == 300.0
        assert cfg.max_escalation == EscalationAction.RESET_ADAPTER

    def test_profile_battery(self):
        """Battery profile enables reset."""
        assert PROFILE_BATTERY.reset_adapter is True
        assert PROFILE_BATTERY.reset_after == 6
        assert PROFILE_BATTERY.reset_cooldown == 300.0

    def test_profile_sensor(self):
        """Sensor profile caps at rotation, no reset."""
        assert PROFILE_SENSOR.reset_adapter is False
        assert PROFILE_SENSOR.max_escalation == EscalationAction.ROTATE_ADAPTER

    def test_profile_on_demand(self):
        """On-demand profile rotates fast, skips InProgress dominance."""
        assert PROFILE_ON_DEMAND.clear_bluez_on_inprogress_dominance is False
        assert PROFILE_ON_DEMAND.reset_adapter is False
        assert PROFILE_ON_DEMAND.rotate_after == 1
        assert PROFILE_ON_DEMAND.max_escalation == EscalationAction.ROTATE_ADAPTER


# ---------------------------------------------------------------------------
# EscalationAction tests
# ---------------------------------------------------------------------------


class TestEscalationAction:
    """Tests for the EscalationAction enum."""

    def test_values(self):
        vals = {
            EscalationAction.RETRY: "retry",
            EscalationAction.DIAGNOSE: "diagnose",
            EscalationAction.CLEAR_BLUEZ: "clear_bluez",
            EscalationAction.ROTATE_ADAPTER: "rotate",
            EscalationAction.RESET_ADAPTER: "reset",
        }
        for action, expected in vals.items():
            assert action.value == expected

    def test_is_str_subclass(self):
        """EscalationAction should be usable as a string."""
        assert isinstance(EscalationAction.RETRY, str)


# ---------------------------------------------------------------------------
# EscalationPolicy tests
# ---------------------------------------------------------------------------


class TestEscalationPolicy:
    """Tests for the EscalationPolicy decision-making logic."""

    def test_first_failure_returns_diagnose(self):
        """First failure with default config should suggest DIAGNOSE."""
        policy = EscalationPolicy(["hci0"])
        action = policy.on_failure("hci0")
        assert action == EscalationAction.DIAGNOSE

    def test_rotate_after_threshold(self):
        """After rotate_after failures, should suggest ROTATE_ADAPTER."""
        policy = EscalationPolicy(["hci0", "hci1"])
        policy.on_failure("hci0")  # 1 → DIAGNOSE
        action = policy.on_failure("hci0")  # 2 → ROTATE
        assert action == EscalationAction.ROTATE_ADAPTER

    def test_clear_after_threshold(self):
        """After clear_after failures, should suggest CLEAR_BLUEZ."""
        policy = EscalationPolicy(["hci0"])
        for _ in range(3):
            policy.on_failure("hci0")
        action = policy.on_failure("hci0")  # 4 → CLEAR
        assert action == EscalationAction.CLEAR_BLUEZ

    def test_reset_after_threshold(self):
        """After reset_after failures, should suggest RESET_ADAPTER if enabled."""
        config = EscalationConfig(reset_adapter=True)
        policy = EscalationPolicy(["hci0"], config=config)
        for _ in range(5):
            policy.on_failure("hci0")
        action = policy.on_failure("hci0")  # 6 → RESET
        assert action == EscalationAction.RESET_ADAPTER

    def test_reset_disabled_by_default(self):
        """Default config does not enable reset — should fall back to CLEAR_BLUEZ."""
        policy = EscalationPolicy(["hci0"])
        for _ in range(10):
            action = policy.on_failure("hci0")
        # Even after many failures, should not suggest RESET
        assert action != EscalationAction.RESET_ADAPTER

    def test_on_success_resets_counter(self):
        """on_success should reset the failure counter."""
        policy = EscalationPolicy(["hci0"])
        policy.on_failure("hci0")
        policy.on_failure("hci0")
        policy.on_success("hci0")
        action = policy.on_failure("hci0")  # back to 1 → DIAGNOSE
        assert action == EscalationAction.DIAGNOSE

    def test_max_escalation_caps_actions(self):
        """max_escalation should cap the returned action."""
        config = EscalationConfig(
            reset_adapter=True,
            max_escalation=EscalationAction.ROTATE_ADAPTER,
        )
        policy = EscalationPolicy(["hci0"], config=config)
        for _ in range(20):
            action = policy.on_failure("hci0")
        # Even after many failures, should not exceed ROTATE
        assert action in (
            EscalationAction.ROTATE_ADAPTER,
            EscalationAction.CLEAR_BLUEZ,
        )
        assert action != EscalationAction.RESET_ADAPTER

    def test_diagnose_disabled(self):
        """If diagnose_and_fix is disabled, skip to next enabled level."""
        config = EscalationConfig(diagnose_and_fix=False)
        policy = EscalationPolicy(["hci0"], config=config)
        action = policy.on_failure("hci0")
        # diagnose disabled, failure count=1 (< rotate_after=2), so RETRY
        assert action == EscalationAction.RETRY

    def test_per_adapter_tracking(self):
        """Failures are tracked per adapter."""
        policy = EscalationPolicy(["hci0", "hci1"])
        policy.on_failure("hci0")
        policy.on_failure("hci0")  # hci0 at 2
        action_hci1 = policy.on_failure("hci1")  # hci1 at 1
        assert action_hci1 == EscalationAction.DIAGNOSE

    def test_record_reset_clears_counter(self):
        """record_reset should clear the failure counter and record time."""
        config = EscalationConfig(reset_adapter=True)
        policy = EscalationPolicy(["hci0"], config=config)
        for _ in range(6):
            policy.on_failure("hci0")
        policy.record_reset("hci0")
        action = policy.on_failure("hci0")  # back to 1
        assert action == EscalationAction.DIAGNOSE

    def test_reset_cooldown(self):
        """Reset should be blocked during cooldown period."""
        config = EscalationConfig(reset_adapter=True, reset_cooldown=300.0)
        policy = EscalationPolicy(["hci0"], config=config)

        # Simulate a recent reset
        policy._last_reset["hci0"] = time.monotonic()

        for _ in range(10):
            action = policy.on_failure("hci0")
        # Should not suggest RESET because cooldown hasn't elapsed
        assert action != EscalationAction.RESET_ADAPTER

    def test_reset_cooldown_expired(self):
        """Reset should be allowed after cooldown expires."""
        config = EscalationConfig(reset_adapter=True, reset_cooldown=0.0)
        policy = EscalationPolicy(["hci0"], config=config)
        for _ in range(5):
            policy.on_failure("hci0")
        action = policy.on_failure("hci0")  # 6 → RESET (cooldown=0)
        assert action == EscalationAction.RESET_ADAPTER

    def test_config_property(self):
        """config property should return the current config."""
        config = EscalationConfig(reset_adapter=True)
        policy = EscalationPolicy(["hci0"], config=config)
        assert policy.config is config

    def test_default_config_if_none(self):
        """If no config provided, should use default EscalationConfig."""
        policy = EscalationPolicy(["hci0"])
        assert isinstance(policy.config, EscalationConfig)
        assert policy.config.reset_adapter is False

    def test_unknown_adapter_on_failure(self):
        """on_failure with an unknown adapter should still work."""
        policy = EscalationPolicy(["hci0"])
        # hci1 not in initial list but should be handled gracefully
        action = policy.on_failure("hci1")
        assert action == EscalationAction.DIAGNOSE

    def test_sensor_profile_never_resets(self):
        """Sensor profile should never suggest RESET_ADAPTER."""
        policy = EscalationPolicy(["hci0", "hci1"], config=PROFILE_SENSOR)
        for _ in range(20):
            action = policy.on_failure("hci0")
        assert action != EscalationAction.RESET_ADAPTER

    def test_on_demand_profile_rotates_fast(self):
        """On-demand profile should rotate after 1 failure."""
        policy = EscalationPolicy(["hci0", "hci1"], config=PROFILE_ON_DEMAND)
        action = policy.on_failure("hci0")  # 1 → ROTATE (rotate_after=1)
        assert action == EscalationAction.ROTATE_ADAPTER


# ---------------------------------------------------------------------------
# reset_adapter tests
# ---------------------------------------------------------------------------


class TestResetAdapter:
    """Tests for the reset_adapter utility function."""

    @pytest.mark.asyncio
    async def test_returns_false_when_not_linux(self):
        """reset_adapter should return False on non-Linux."""
        with patch("bleak_retry_connector.recovery.IS_LINUX", False):
            result = await reset_adapter("hci0")
            assert result is False

    @pytest.mark.asyncio
    async def test_returns_false_when_no_hciconfig(self):
        """reset_adapter should return False when hciconfig is not found."""
        tools_no_hciconfig = ToolCapabilities(hciconfig=None)
        with (
            patch("bleak_retry_connector.recovery.IS_LINUX", True),
            patch("bleak_retry_connector.recovery.TOOLS", tools_no_hciconfig),
        ):
            result = await reset_adapter("hci0")
            assert result is False

    @pytest.mark.asyncio
    async def test_calls_hciconfig_down_up(self):
        """reset_adapter should call hciconfig down then up."""
        mock_tools = ToolCapabilities(
            hciconfig="/usr/bin/hciconfig",
            bluetoothctl="/usr/bin/bluetoothctl",
        )
        mock_run = MagicMock(return_value=MagicMock(returncode=0))

        async def fast_sleep(_):
            pass

        with (
            patch("bleak_retry_connector.recovery.IS_LINUX", True),
            patch("bleak_retry_connector.recovery.TOOLS", mock_tools),
            patch("bleak_retry_connector.recovery.subprocess.run", mock_run),
            patch("bleak_retry_connector.recovery.asyncio.sleep", fast_sleep),
        ):
            result = await reset_adapter("hci0", restart_bluetoothd=False)

        assert result is True
        calls = mock_run.call_args_list
        assert len(calls) == 2
        assert calls[0][0][0] == ["/usr/bin/hciconfig", "hci0", "down"]
        assert calls[1][0][0] == ["/usr/bin/hciconfig", "hci0", "up"]

    @pytest.mark.asyncio
    async def test_restarts_bluetoothd_if_dead(self):
        """reset_adapter should restart bluetoothd if it died."""
        mock_tools = ToolCapabilities(
            hciconfig="/usr/bin/hciconfig",
            bluetoothctl="/usr/bin/bluetoothctl",
        )

        call_log: list[list[str]] = []

        def mock_run(cmd, **kwargs):
            call_log.append(cmd)
            result = MagicMock()
            if cmd[0] == "pidof":
                result.returncode = 1  # bluetoothd not running
            else:
                result.returncode = 0
            return result

        async def fast_sleep(_):
            pass

        with (
            patch("bleak_retry_connector.recovery.IS_LINUX", True),
            patch("bleak_retry_connector.recovery.TOOLS", mock_tools),
            patch("bleak_retry_connector.recovery.subprocess.run", mock_run),
            patch("bleak_retry_connector.recovery.asyncio.sleep", fast_sleep),
        ):
            result = await reset_adapter("hci0", restart_bluetoothd=True)

        assert result is True
        pidof_calls = [c for c in call_log if c[0] == "pidof"]
        assert len(pidof_calls) == 1
        bluetooth_calls = [c for c in call_log if "/etc/init.d/bluetooth" in str(c)]
        assert len(bluetooth_calls) == 1

    @pytest.mark.asyncio
    async def test_returns_false_on_down_failure(self):
        """reset_adapter should return False if hciconfig down raises."""
        mock_tools = ToolCapabilities(hciconfig="/usr/bin/hciconfig")

        with (
            patch("bleak_retry_connector.recovery.IS_LINUX", True),
            patch("bleak_retry_connector.recovery.TOOLS", mock_tools),
            patch(
                "bleak_retry_connector.recovery.subprocess.run",
                side_effect=OSError("command failed"),
            ),
        ):
            result = await reset_adapter("hci0")

        assert result is False

    @pytest.mark.asyncio
    async def test_returns_false_on_up_nonzero(self):
        """reset_adapter should return False if hciconfig up returns non-zero."""
        mock_tools = ToolCapabilities(hciconfig="/usr/bin/hciconfig")

        call_count = 0

        def mock_run(cmd, **kwargs):
            nonlocal call_count
            call_count += 1
            result = MagicMock()
            if call_count == 1:
                result.returncode = 0  # down succeeds
            else:
                result.returncode = 1  # up fails
                result.stderr = b"some error"
            return result

        async def fast_sleep(_):
            pass

        with (
            patch("bleak_retry_connector.recovery.IS_LINUX", True),
            patch("bleak_retry_connector.recovery.TOOLS", mock_tools),
            patch("bleak_retry_connector.recovery.subprocess.run", mock_run),
            patch("bleak_retry_connector.recovery.asyncio.sleep", fast_sleep),
        ):
            result = await reset_adapter("hci0", restart_bluetoothd=False)

        assert result is False


# ---------------------------------------------------------------------------
# Integration: importability from top-level
# ---------------------------------------------------------------------------


def test_importable_from_top_level():
    """All recovery symbols should be importable from bleak_retry_connector."""
    from bleak_retry_connector import (  # noqa: F401
        PROFILE_BATTERY,
        PROFILE_ON_DEMAND,
        PROFILE_SENSOR,
        TOOLS,
        EscalationAction,
        EscalationConfig,
        EscalationPolicy,
        ToolCapabilities,
        reset_adapter,
    )
