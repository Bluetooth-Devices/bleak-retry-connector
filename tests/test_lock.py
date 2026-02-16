"""Tests for cross-process file locking."""

from __future__ import annotations

import tempfile
from unittest.mock import patch

import pytest

from bleak_retry_connector.const import LockConfig
from bleak_retry_connector.lock import acquire_lock, release_lock

pytestmark = pytest.mark.asyncio


async def test_lock_config_path_for_adapter():
    """LockConfig generates correct paths for adapters."""
    config = LockConfig(enabled=True, lock_dir="/tmp")
    assert config.path_for_adapter("hci0") == ("/tmp/bleak-retry-connector-hci0.lock")
    assert config.path_for_adapter("hci1") == ("/tmp/bleak-retry-connector-hci1.lock")
    assert config.path_for_adapter(None) == ("/tmp/bleak-retry-connector-default.lock")


async def test_lock_config_custom_template():
    """LockConfig supports custom templates."""
    config = LockConfig(
        enabled=True,
        lock_dir="/var/lock",
        lock_template="my-service-{adapter}.lock",
    )
    assert config.path_for_adapter("hci0") == "/var/lock/my-service-hci0.lock"


async def test_acquire_release_lock():
    """Lock can be acquired and released."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config = LockConfig(enabled=True, lock_dir=tmpdir)
        fd = await acquire_lock(config, "hci0")
        assert fd is not None
        release_lock(fd)


async def test_acquire_lock_disabled():
    """Lock is not acquired when config is disabled."""
    config = LockConfig(enabled=False)
    fd = await acquire_lock(config, "hci0")
    assert fd is None


async def test_acquire_lock_no_fcntl():
    """Lock is not acquired when fcntl is unavailable."""
    config = LockConfig(enabled=True)
    with patch("bleak_retry_connector.lock._HAS_FCNTL", False):
        fd = await acquire_lock(config, "hci0")
    assert fd is None


async def test_release_lock_none():
    """release_lock(None) is a safe no-op."""
    release_lock(None)


async def test_lock_contention_timeout():
    """Second lock acquisition times out when first holds the lock."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config = LockConfig(
            enabled=True,
            lock_dir=tmpdir,
            lock_timeout=0.5,
        )
        fd1 = await acquire_lock(config, "hci0")
        assert fd1 is not None

        fd2 = await acquire_lock(config, "hci0")
        assert fd2 is None

        release_lock(fd1)


async def test_lock_released_after_holder_closes():
    """Lock can be re-acquired after previous holder releases."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config = LockConfig(
            enabled=True,
            lock_dir=tmpdir,
            lock_timeout=1.0,
        )
        fd1 = await acquire_lock(config, "hci0")
        assert fd1 is not None
        release_lock(fd1)

        fd2 = await acquire_lock(config, "hci0")
        assert fd2 is not None
        release_lock(fd2)


async def test_lock_per_adapter_independent():
    """Locks for different adapters are independent."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config = LockConfig(enabled=True, lock_dir=tmpdir)
        fd_hci0 = await acquire_lock(config, "hci0")
        fd_hci1 = await acquire_lock(config, "hci1")
        assert fd_hci0 is not None
        assert fd_hci1 is not None
        release_lock(fd_hci0)
        release_lock(fd_hci1)


async def test_lock_bad_directory():
    """Lock gracefully degrades if directory is not writable."""
    config = LockConfig(
        enabled=True,
        lock_dir="/nonexistent/path/that/does/not/exist",
    )
    fd = await acquire_lock(config, "hci0")
    assert fd is None
