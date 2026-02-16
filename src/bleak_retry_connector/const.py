from __future__ import annotations

import platform

IS_LINUX = platform.system() == "Linux"
NO_RSSI_VALUE = -127
RSSI_SWITCH_THRESHOLD = 5
DISCONNECT_TIMEOUT = 5
REAPPEAR_WAIT_INTERVAL = 0.5
DBUS_CONNECT_TIMEOUT = 8.5

# Thread-level safety timer timeout (seconds).  Must be less than
# BLEAK_SAFETY_TIMEOUT (60s) so the asyncio timeout remains the primary
# mechanism and the thread timer is only a fallback for a stuck event loop.
THREAD_SAFETY_TIMEOUT = 45.0
