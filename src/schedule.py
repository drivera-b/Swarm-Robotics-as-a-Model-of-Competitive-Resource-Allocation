from __future__ import annotations

from src.constants import ZONE_SCHEDULE


def zone_values_for_elapsed(elapsed_seconds: float) -> tuple[str, dict[str, int]]:
    for start, end, values in ZONE_SCHEDULE:
        if start <= elapsed_seconds < end:
            return f"{start}-{end}", dict(values)
    _, end, values = ZONE_SCHEDULE[-1]
    return f"{end-30}-{end}", dict(values)
