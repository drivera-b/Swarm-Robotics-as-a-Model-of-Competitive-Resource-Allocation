from __future__ import annotations


def require_sphero_sdk():
    try:
        from spherov2 import scanner  # type: ignore
        from spherov2.sphero_edu import SpheroEduAPI  # type: ignore
        from spherov2.toy.bolt import BOLT  # type: ignore
    except ImportError as exc:
        raise RuntimeError(
            "Missing spherov2 SDK. Install dependencies with: pip install -r requirements.txt"
        ) from exc
    return scanner, BOLT, SpheroEduAPI
