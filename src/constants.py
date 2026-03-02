from __future__ import annotations

ZONES: tuple[str, ...] = ("A", "B", "C", "D")

# From center start box (0,0) toward arena corner zones.
ZONE_HEADINGS: dict[str, int] = {
    "A": 315,  # top-left
    "B": 45,   # top-right
    "C": 225,  # bottom-left
    "D": 135,  # bottom-right
}

# (start_second, end_second, zone_values)
ZONE_SCHEDULE: tuple[tuple[int, int, dict[str, int]], ...] = (
    (0, 30, {"A": 40, "B": 30, "C": 20, "D": 10}),
    (30, 60, {"A": 10, "B": 40, "C": 30, "D": 20}),
    (60, 90, {"A": 20, "B": 10, "C": 40, "D": 30}),
)

DEFAULT_TRIAL_SECONDS = 90
