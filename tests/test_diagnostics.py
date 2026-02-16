"""Tests for the diagnostics module (StuckState, diagnose, clear)."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from bleak_retry_connector.diagnostics import (
    StuckState,
    _is_bluez_connected,
    _is_services_resolved,
    _run_cmd,
    clear_stuck_state,
    diagnose_stuck_state,
)

# ---------------------------------------------------------------------------
# StuckState enum
# ---------------------------------------------------------------------------


class TestStuckState:
    def test_values(self):
        vals = {
            StuckState.NOT_STUCK: "not_stuck",
            StuckState.PHANTOM_NO_HANDLE: "phantom_no_handle",
            StuckState.DEAD_HANDLE: "dead_handle",
            StuckState.PENDING_LE_CREATE: "pending_le_create",
            StuckState.STALE_CACHE: "stale_cache",
        }
        for member, expected in vals.items():
            assert member.value == expected


# ---------------------------------------------------------------------------
# _run_cmd
# ---------------------------------------------------------------------------


class TestRunCmd:
    @pytest.mark.asyncio
    async def test_successful_command(self):
        with patch("asyncio.create_subprocess_exec") as mock_exec:
            mock_proc = AsyncMock()
            mock_proc.communicate.return_value = (b"hello\n", b"")
            mock_proc.returncode = 0
            mock_exec.return_value = mock_proc

            rc, stdout = await _run_cmd("echo", "hello")
            assert rc == 0
            assert "hello" in stdout

    @pytest.mark.asyncio
    async def test_command_failure(self):
        with patch("asyncio.create_subprocess_exec", side_effect=OSError("fail")):
            rc, stdout = await _run_cmd("nonexistent")
            assert rc == -1
            assert stdout == ""


# ---------------------------------------------------------------------------
# _is_bluez_connected
# ---------------------------------------------------------------------------


class TestIsBluezConnected:
    @pytest.mark.asyncio
    async def test_connected(self):
        with (
            patch(
                "bleak_retry_connector.diagnostics._bluetoothctl",
                "/usr/bin/bluetoothctl",
            ),
            patch(
                "bleak_retry_connector.diagnostics._run_cmd",
                return_value=(0, "  Connected: yes\n  Paired: yes\n"),
            ),
        ):
            assert await _is_bluez_connected("AA:BB:CC:DD:EE:FF") is True

    @pytest.mark.asyncio
    async def test_not_connected(self):
        with (
            patch(
                "bleak_retry_connector.diagnostics._bluetoothctl",
                "/usr/bin/bluetoothctl",
            ),
            patch(
                "bleak_retry_connector.diagnostics._run_cmd",
                return_value=(0, "  Connected: no\n"),
            ),
        ):
            assert await _is_bluez_connected("AA:BB:CC:DD:EE:FF") is False

    @pytest.mark.asyncio
    async def test_command_fails(self):
        with (
            patch(
                "bleak_retry_connector.diagnostics._bluetoothctl",
                "/usr/bin/bluetoothctl",
            ),
            patch(
                "bleak_retry_connector.diagnostics._run_cmd",
                return_value=(1, ""),
            ),
        ):
            assert await _is_bluez_connected("AA:BB:CC:DD:EE:FF") is False


# ---------------------------------------------------------------------------
# _is_services_resolved
# ---------------------------------------------------------------------------


class TestIsServicesResolved:
    @pytest.mark.asyncio
    async def test_resolved(self):
        with (
            patch(
                "bleak_retry_connector.diagnostics._bluetoothctl",
                "/usr/bin/bluetoothctl",
            ),
            patch(
                "bleak_retry_connector.diagnostics._run_cmd",
                return_value=(0, "  ServicesResolved: yes\n"),
            ),
        ):
            assert await _is_services_resolved("AA:BB:CC:DD:EE:FF") is True

    @pytest.mark.asyncio
    async def test_not_resolved(self):
        with (
            patch(
                "bleak_retry_connector.diagnostics._bluetoothctl",
                "/usr/bin/bluetoothctl",
            ),
            patch(
                "bleak_retry_connector.diagnostics._run_cmd",
                return_value=(0, "  ServicesResolved: no\n"),
            ),
        ):
            assert await _is_services_resolved("AA:BB:CC:DD:EE:FF") is False


# ---------------------------------------------------------------------------
# diagnose_stuck_state
# ---------------------------------------------------------------------------


class TestDiagnoseStuckState:
    @pytest.mark.asyncio
    async def test_not_linux(self):
        with patch("bleak_retry_connector.diagnostics.IS_LINUX", False):
            state = await diagnose_stuck_state("AA:BB:CC:DD:EE:FF", "hci0")
            assert state == StuckState.NOT_STUCK

    @pytest.mark.asyncio
    async def test_no_shell_tools(self):
        with (
            patch("bleak_retry_connector.diagnostics.IS_LINUX", True),
            patch(
                "bleak_retry_connector.diagnostics._has_shell_tools",
                return_value=False,
            ),
        ):
            state = await diagnose_stuck_state("AA:BB:CC:DD:EE:FF", "hci0")
            assert state == StuckState.NOT_STUCK

    @pytest.mark.asyncio
    async def test_phantom_no_handle(self):
        """Connected=True, no HCI handle → PHANTOM_NO_HANDLE."""
        with (
            patch("bleak_retry_connector.diagnostics.IS_LINUX", True),
            patch(
                "bleak_retry_connector.diagnostics._has_shell_tools",
                return_value=True,
            ),
            patch(
                "bleak_retry_connector.diagnostics._is_bluez_connected",
                return_value=True,
            ),
            patch(
                "bleak_retry_connector.diagnostics._get_hci_handle",
                return_value=None,
            ),
        ):
            state = await diagnose_stuck_state("AA:BB:CC:DD:EE:FF", "hci0")
            assert state == StuckState.PHANTOM_NO_HANDLE

    @pytest.mark.asyncio
    async def test_dead_handle(self):
        """Connected=True, HCI handle exists, ServicesResolved=False → DEAD_HANDLE."""
        with (
            patch("bleak_retry_connector.diagnostics.IS_LINUX", True),
            patch(
                "bleak_retry_connector.diagnostics._has_shell_tools",
                return_value=True,
            ),
            patch(
                "bleak_retry_connector.diagnostics._is_bluez_connected",
                return_value=True,
            ),
            patch(
                "bleak_retry_connector.diagnostics._get_hci_handle",
                return_value="16",
            ),
            patch(
                "bleak_retry_connector.diagnostics._is_services_resolved",
                return_value=False,
            ),
        ):
            state = await diagnose_stuck_state("AA:BB:CC:DD:EE:FF", "hci0")
            assert state == StuckState.DEAD_HANDLE

    @pytest.mark.asyncio
    async def test_pending_le_create(self):
        """Not connected, pending LE connection → PENDING_LE_CREATE."""
        with (
            patch("bleak_retry_connector.diagnostics.IS_LINUX", True),
            patch(
                "bleak_retry_connector.diagnostics._has_shell_tools",
                return_value=True,
            ),
            patch(
                "bleak_retry_connector.diagnostics._is_bluez_connected",
                return_value=False,
            ),
            patch(
                "bleak_retry_connector.diagnostics._get_hci_handle",
                return_value=None,
            ),
            patch(
                "bleak_retry_connector.diagnostics._has_pending_le_connection",
                return_value=True,
            ),
        ):
            state = await diagnose_stuck_state("AA:BB:CC:DD:EE:FF", "hci0")
            assert state == StuckState.PENDING_LE_CREATE

    @pytest.mark.asyncio
    async def test_stale_cache(self):
        """Not connected, no pending, but has cache entry → STALE_CACHE."""
        with (
            patch("bleak_retry_connector.diagnostics.IS_LINUX", True),
            patch(
                "bleak_retry_connector.diagnostics._has_shell_tools",
                return_value=True,
            ),
            patch(
                "bleak_retry_connector.diagnostics._is_bluez_connected",
                return_value=False,
            ),
            patch(
                "bleak_retry_connector.diagnostics._get_hci_handle",
                return_value=None,
            ),
            patch(
                "bleak_retry_connector.diagnostics._has_pending_le_connection",
                return_value=False,
            ),
            patch(
                "bleak_retry_connector.diagnostics._has_bluez_cache_entry",
                return_value=True,
            ),
        ):
            state = await diagnose_stuck_state("AA:BB:CC:DD:EE:FF", "hci0")
            assert state == StuckState.STALE_CACHE

    @pytest.mark.asyncio
    async def test_not_stuck(self):
        """Connected=True, handle exists, services resolved → NOT_STUCK."""
        with (
            patch("bleak_retry_connector.diagnostics.IS_LINUX", True),
            patch(
                "bleak_retry_connector.diagnostics._has_shell_tools",
                return_value=True,
            ),
            patch(
                "bleak_retry_connector.diagnostics._is_bluez_connected",
                return_value=True,
            ),
            patch(
                "bleak_retry_connector.diagnostics._get_hci_handle",
                return_value="16",
            ),
            patch(
                "bleak_retry_connector.diagnostics._is_services_resolved",
                return_value=True,
            ),
        ):
            state = await diagnose_stuck_state("AA:BB:CC:DD:EE:FF", "hci0")
            assert state == StuckState.NOT_STUCK


# ---------------------------------------------------------------------------
# clear_stuck_state
# ---------------------------------------------------------------------------


class TestClearStuckState:
    @pytest.mark.asyncio
    async def test_not_stuck_returns_true(self):
        result = await clear_stuck_state(
            "AA:BB:CC:DD:EE:FF", "hci0", StuckState.NOT_STUCK
        )
        assert result is True

    @pytest.mark.asyncio
    async def test_phantom_calls_remove(self):
        with (
            patch("bleak_retry_connector.diagnostics.IS_LINUX", True),
            patch(
                "bleak_retry_connector.diagnostics._has_shell_tools",
                return_value=True,
            ),
            patch(
                "bleak_retry_connector.diagnostics._bluetoothctl",
                "/usr/bin/bluetoothctl",
            ),
            patch(
                "bleak_retry_connector.diagnostics._hcitool",
                "/usr/bin/hcitool",
            ),
            patch(
                "bleak_retry_connector.diagnostics._run_cmd",
                return_value=(0, ""),
            ) as mock_run,
        ):
            result = await clear_stuck_state(
                "AA:BB:CC:DD:EE:FF", "hci0", StuckState.PHANTOM_NO_HANDLE
            )
            assert result is True
            mock_run.assert_called_once_with(
                "/usr/bin/bluetoothctl", "remove", "AA:BB:CC:DD:EE:FF"
            )

    @pytest.mark.asyncio
    async def test_dead_handle_calls_ledc(self):
        with (
            patch("bleak_retry_connector.diagnostics.IS_LINUX", True),
            patch(
                "bleak_retry_connector.diagnostics._has_shell_tools",
                return_value=True,
            ),
            patch(
                "bleak_retry_connector.diagnostics._bluetoothctl",
                "/usr/bin/bluetoothctl",
            ),
            patch(
                "bleak_retry_connector.diagnostics._hcitool",
                "/usr/bin/hcitool",
            ),
            patch(
                "bleak_retry_connector.diagnostics._get_hci_handle",
                return_value="16",
            ),
            patch(
                "bleak_retry_connector.diagnostics._run_cmd",
                return_value=(0, ""),
            ) as mock_run,
        ):
            result = await clear_stuck_state(
                "AA:BB:CC:DD:EE:FF", "hci0", StuckState.DEAD_HANDLE
            )
            assert result is True
            mock_run.assert_called_once_with(
                "/usr/bin/hcitool", "-i", "hci0", "ledc", "16"
            )

    @pytest.mark.asyncio
    async def test_pending_le_create_calls_cancel(self):
        with (
            patch("bleak_retry_connector.diagnostics.IS_LINUX", True),
            patch(
                "bleak_retry_connector.diagnostics._has_shell_tools",
                return_value=True,
            ),
            patch(
                "bleak_retry_connector.diagnostics._bluetoothctl",
                "/usr/bin/bluetoothctl",
            ),
            patch(
                "bleak_retry_connector.diagnostics._hcitool",
                "/usr/bin/hcitool",
            ),
            patch(
                "bleak_retry_connector.diagnostics._run_cmd",
                return_value=(0, ""),
            ) as mock_run,
        ):
            result = await clear_stuck_state(
                "AA:BB:CC:DD:EE:FF", "hci0", StuckState.PENDING_LE_CREATE
            )
            assert result is True
            mock_run.assert_called_once_with(
                "/usr/bin/hcitool", "-i", "hci0", "cmd", "0x08", "0x000E"
            )

    @pytest.mark.asyncio
    async def test_stale_cache_calls_remove(self):
        with (
            patch("bleak_retry_connector.diagnostics.IS_LINUX", True),
            patch(
                "bleak_retry_connector.diagnostics._has_shell_tools",
                return_value=True,
            ),
            patch(
                "bleak_retry_connector.diagnostics._bluetoothctl",
                "/usr/bin/bluetoothctl",
            ),
            patch(
                "bleak_retry_connector.diagnostics._hcitool",
                "/usr/bin/hcitool",
            ),
            patch(
                "bleak_retry_connector.diagnostics._run_cmd",
                return_value=(0, ""),
            ) as mock_run,
        ):
            result = await clear_stuck_state(
                "AA:BB:CC:DD:EE:FF", "hci0", StuckState.STALE_CACHE
            )
            assert result is True
            mock_run.assert_called_once_with(
                "/usr/bin/bluetoothctl", "remove", "AA:BB:CC:DD:EE:FF"
            )

    @pytest.mark.asyncio
    async def test_fallback_to_clear_cache_when_no_tools(self):
        """When shell tools unavailable, falls back to D-Bus clear_cache."""
        with (
            patch("bleak_retry_connector.diagnostics.IS_LINUX", True),
            patch(
                "bleak_retry_connector.diagnostics._has_shell_tools",
                return_value=False,
            ),
            patch(
                "bleak_retry_connector.bluez.clear_cache",
                return_value=True,
            ) as mock_clear,
        ):
            result = await clear_stuck_state(
                "AA:BB:CC:DD:EE:FF", "hci0", StuckState.PHANTOM_NO_HANDLE
            )
            assert result is True
            mock_clear.assert_called_once_with("AA:BB:CC:DD:EE:FF")


# ---------------------------------------------------------------------------
# _get_hci_handle
# ---------------------------------------------------------------------------


class TestGetHciHandle:
    @pytest.mark.asyncio
    async def test_finds_handle(self):
        hcitool_output = (
            "Connections:\n"
            "    < LE AA:BB:CC:DD:EE:FF handle 16 state 1 lm CENTRAL\n"
            "    < LE 11:22:33:44:55:66 handle 17 state 1 lm CENTRAL\n"
        )
        from bleak_retry_connector.diagnostics import _get_hci_handle

        with (
            patch(
                "bleak_retry_connector.diagnostics._hcitool",
                "/usr/bin/hcitool",
            ),
            patch(
                "bleak_retry_connector.diagnostics._run_cmd",
                return_value=(0, hcitool_output),
            ),
        ):
            handle = await _get_hci_handle("AA:BB:CC:DD:EE:FF", "hci0")
            assert handle == "16"

    @pytest.mark.asyncio
    async def test_no_handle(self):
        hcitool_output = (
            "Connections:\n" "    < LE 11:22:33:44:55:66 handle 17 state 1 lm CENTRAL\n"
        )
        from bleak_retry_connector.diagnostics import _get_hci_handle

        with (
            patch(
                "bleak_retry_connector.diagnostics._hcitool",
                "/usr/bin/hcitool",
            ),
            patch(
                "bleak_retry_connector.diagnostics._run_cmd",
                return_value=(0, hcitool_output),
            ),
        ):
            handle = await _get_hci_handle("AA:BB:CC:DD:EE:FF", "hci0")
            assert handle is None


# ---------------------------------------------------------------------------
# Importability from top-level
# ---------------------------------------------------------------------------


def test_importable_from_top_level():
    """Diagnostic symbols should be importable from bleak_retry_connector."""
    from bleak_retry_connector import (  # noqa: F401
        StuckState,
        clear_stuck_state,
        diagnose_stuck_state,
        is_inactive_connection,
    )
