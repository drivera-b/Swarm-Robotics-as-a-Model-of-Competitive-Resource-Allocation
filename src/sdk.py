from __future__ import annotations

import struct


def _apply_spherov2_compat_patches() -> None:
    """Apply runtime guards for known noisy spherov2 packet parsing issues."""
    try:
        from spherov2.commands.sensor import Sensor  # type: ignore
    except Exception:
        return

    if getattr(Sensor, "_codex_collision_guard", False):
        return

    notify = getattr(Sensor, "collision_detected_notify", None)
    if not notify or not isinstance(notify, tuple) or len(notify) != 2:
        return

    cmd_info, original_handler = notify

    def safe_collision_handler(listener, packet):
        try:
            original_handler(listener, packet)
        except struct.error:
            # Ignore malformed collision packets that occasionally appear on BOLT BLE streams.
            return

    Sensor.collision_detected_notify = (cmd_info, safe_collision_handler)
    Sensor._codex_collision_guard = True


def require_sphero_sdk():
    try:
        from spherov2 import scanner  # type: ignore
        from spherov2.sphero_edu import SpheroEduAPI  # type: ignore
        from spherov2.toy.bolt import BOLT  # type: ignore
    except ImportError as exc:
        raise RuntimeError(
            "Missing spherov2 SDK. Install dependencies with: pip install -r requirements.txt"
        ) from exc

    _apply_spherov2_compat_patches()
    return scanner, BOLT, SpheroEduAPI
