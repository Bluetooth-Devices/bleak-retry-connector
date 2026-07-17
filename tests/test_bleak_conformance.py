"""Conformance canary for the private ``bleak`` internals this package couples to.

The rest of the suite mocks the BlueZ manager, so a green run proves the package's
*logic* but not that it still matches the *real* ``bleak`` — in particular the private
attributes (``BlueZManager._bus`` / ``._properties`` / ``._services_cache`` /
``._wait_condition``) and ``bluezdbus.defs`` constants it reaches into. Those are exactly
what a ``bleak`` major bump silently removes or renames, and mocks always satisfy them.

These tests exercise the *installed* ``bleak`` with no mocking. If a future bump breaks
one of these coupling points, CI fails here with a precise message instead of shipping a
package that only its own mocks can pass. Update ``src/`` and these assertions together.
"""

from __future__ import annotations

import inspect

import pytest

# The bluezdbus backend is Linux-only; degrade gracefully elsewhere.
manager = pytest.importorskip("bleak.backends.bluezdbus.manager")
defs = pytest.importorskip("bleak.backends.bluezdbus.defs")


# Private BlueZManager instance attributes read by dbus.py / bluez.py.
_MANAGER_INSTANCE_ATTRS = ("_bus", "_properties", "_services_cache")

# defs constants referenced in dbus.py / bluez.py.
_DEFS_CONSTANTS = (
    "ADAPTER_INTERFACE",
    "BLUEZ_SERVICE",
    "DEVICE_INTERFACE",
    "GATT_SERVICE_INTERFACE",
)


def test_get_global_bluez_manager_is_importable() -> None:
    """bleak_manager.py imports this factory from the bluezdbus manager module."""
    assert callable(manager.get_global_bluez_manager)


@pytest.mark.parametrize("attr", _MANAGER_INSTANCE_ATTRS)
def test_bluez_manager_exposes_private_attr(attr: str) -> None:
    """dbus.py / bluez.py read these private attributes off the manager instance."""
    instance = manager.BlueZManager()
    assert hasattr(instance, attr)


def test_bluez_manager_wait_condition_signature() -> None:
    """bluez.py calls manager._wait_condition(device_path, "Connected", False)."""
    method = getattr(manager.BlueZManager, "_wait_condition", None)
    assert callable(method)
    params = list(inspect.signature(method).parameters)
    # self + the three positional arguments the call site passes.
    assert params[:4] == ["self", "device_path", "property_name", "property_value"]


@pytest.mark.parametrize("const", _DEFS_CONSTANTS)
def test_defs_constant_present(const: str) -> None:
    """dbus.py / bluez.py reference these interface/service string constants."""
    assert isinstance(getattr(defs, const), str)
