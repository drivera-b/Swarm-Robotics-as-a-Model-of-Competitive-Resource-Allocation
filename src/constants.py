from __future__ import annotations

ZONES: tuple[str, ...] = ("A", "B", "C", "D")

# Arena configuration (inches): 2ft x 2ft arena with centered 8in start box.
ARENA_SIZE_IN = 24
START_BOX_SIZE_IN = 8
ZONE_SIZE_IN = 4

# Corner resource zone centers (x, y) in inches with origin at arena center.
ZONE_CENTERS_IN: dict[str, tuple[float, float]] = {
    "A": (-10.0, 10.0),
    "B": (10.0, 10.0),
    "C": (-10.0, -10.0),
    "D": (10.0, -10.0),
}

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

# Smaller arena defaults and conservative motion tuning.
DEFAULT_SMALL_ARENA_SPEED = 35
DEFAULT_SMALL_ARENA_ROLL_SECONDS = 1.1
