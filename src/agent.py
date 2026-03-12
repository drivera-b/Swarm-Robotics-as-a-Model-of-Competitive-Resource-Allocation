from __future__ import annotations

import asyncio
import math
import random
import time
from dataclasses import dataclass
from datetime import datetime

from src.constants import ARENA_SIZE_IN, ZONE_CENTERS_IN, ZONE_HEADINGS, ZONES
from src.crowding import ChoiceRegistry, CrowdingSource
from src.robot_client import RobotClient
from src.schedule import zone_values_for_elapsed
from src.trial_logger import TrialLogger


def choose_zone(zone_values: dict[str, int], crowding: dict[str, int], lambda_value: int) -> str:
    scores = {
        zone: zone_values[zone] - (lambda_value * crowding.get(zone, 0))
        for zone in ZONES
    }
    # Tie-break order is deterministic: A, then B, then C, then D.
    return max(ZONES, key=lambda z: (scores[z], zone_values[z], -ZONES.index(z)))


@dataclass
class AgentConfig:
    lambda_value: int
    decision_min_seconds: float
    decision_max_seconds: float
    roll_seconds: float
    speed: int
    trial_seconds: int
    min_roll_seconds: float = 0.45
    max_roll_seconds: float = 1.2
    zone_stop_radius_in: float = 1.5
    collision_distance_threshold_in: float = 2.0
    avoidance_heading_offset_deg: float = 8.0
    speed_to_inches_per_second: float = 0.22


class PositionRegistry:
    """Shared dead-reckoning map for simple local avoidance in small arenas."""

    def __init__(self, robot_ids: list[str]) -> None:
        self._positions: dict[str, tuple[float, float]] = {rid: (0.0, 0.0) for rid in robot_ids}
        self._lock = asyncio.Lock()

    async def get(self, robot_id: str) -> tuple[float, float]:
        async with self._lock:
            return self._positions.get(robot_id, (0.0, 0.0))

    async def nearest_distance(self, robot_id: str) -> float | None:
        async with self._lock:
            current = self._positions.get(robot_id, (0.0, 0.0))
            nearest: float | None = None
            for other_id, other_pos in self._positions.items():
                if other_id == robot_id:
                    continue
                dist = _distance(current, other_pos)
                if nearest is None or dist < nearest:
                    nearest = dist
            return nearest

    async def update_from_move(
        self,
        robot_id: str,
        heading_deg: float,
        speed: int,
        duration: float,
        speed_to_inches_per_second: float,
    ) -> None:
        async with self._lock:
            x, y = self._positions.get(robot_id, (0.0, 0.0))
            distance = max(0.0, speed * duration * speed_to_inches_per_second)
            rad = math.radians(heading_deg)
            dx = distance * math.sin(rad)
            dy = distance * math.cos(rad)

            arena_half = ARENA_SIZE_IN / 2.0
            nx = max(-arena_half, min(arena_half, x + dx))
            ny = max(-arena_half, min(arena_half, y + dy))
            self._positions[robot_id] = (nx, ny)


def _distance(a: tuple[float, float], b: tuple[float, float]) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def _normalize_heading(deg: float) -> float:
    return deg % 360.0


def _heading_toward(current: tuple[float, float], target: tuple[float, float], fallback: int) -> float:
    dx = target[0] - current[0]
    dy = target[1] - current[1]
    if abs(dx) < 1e-6 and abs(dy) < 1e-6:
        return float(fallback)
    # For this heading convention: x=sin(theta), y=cos(theta)
    return _normalize_heading(math.degrees(math.atan2(dx, dy)))


def _roll_duration_for_distance(distance_to_zone: float, config: AgentConfig) -> float:
    if distance_to_zone <= config.zone_stop_radius_in:
        return 0.0

    approx_duration = distance_to_zone / max(1.0, config.speed * config.speed_to_inches_per_second)
    upper = min(config.roll_seconds, config.max_roll_seconds)
    return max(config.min_roll_seconds, min(approx_duration, upper))


def _avoidance_adjustment(robot_id: str, base_heading: float, offset_deg: float) -> float:
    # Deterministic split so nearby robots don't all turn same direction.
    parity = sum(ord(ch) for ch in robot_id) % 2
    sign = -1.0 if parity == 0 else 1.0
    return _normalize_heading(base_heading + sign * offset_deg)


class RobotAgent:
    def __init__(
        self,
        robot_id: str,
        client: RobotClient,
        config: AgentConfig,
        crowding_source: CrowdingSource,
        choice_registry: ChoiceRegistry,
        position_registry: PositionRegistry,
        logger: TrialLogger,
    ) -> None:
        self.robot_id = robot_id
        self.client = client
        self.config = config
        self.crowding_source = crowding_source
        self.choice_registry = choice_registry
        self.position_registry = position_registry
        self.logger = logger

    async def run(self, trial_start_monotonic: float) -> None:
        while True:
            elapsed = time.monotonic() - trial_start_monotonic
            if elapsed >= self.config.trial_seconds:
                return

            segment, zone_values = zone_values_for_elapsed(elapsed)
            crowding = self.crowding_source.get_counts(self.robot_id)
            chosen_zone = choose_zone(zone_values, crowding, self.config.lambda_value)
            self.choice_registry.set_choice(self.robot_id, chosen_zone)

            await self.logger.log_decision(
                timestamp=datetime.now().isoformat(timespec="seconds"),
                lambda_value=self.config.lambda_value,
                segment=segment,
                robot_id=self.robot_id,
                chosen_zone=chosen_zone,
                crowding=crowding,
            )

            current_pos = await self.position_registry.get(self.robot_id)
            target_pos = ZONE_CENTERS_IN[chosen_zone]
            distance_to_zone = _distance(current_pos, target_pos)

            heading = _heading_toward(current_pos, target_pos, fallback=ZONE_HEADINGS[chosen_zone])
            nearest = await self.position_registry.nearest_distance(self.robot_id)
            if nearest is not None and nearest <= self.config.collision_distance_threshold_in:
                heading = _avoidance_adjustment(
                    self.robot_id,
                    heading,
                    self.config.avoidance_heading_offset_deg,
                )

            move_duration = _roll_duration_for_distance(distance_to_zone, self.config)
            if move_duration > 0:
                await self.client.roll_for(
                    heading=int(round(heading)) % 360,
                    speed=self.config.speed,
                    duration=move_duration,
                )
                await self.position_registry.update_from_move(
                    self.robot_id,
                    heading_deg=heading,
                    speed=self.config.speed,
                    duration=move_duration,
                    speed_to_inches_per_second=self.config.speed_to_inches_per_second,
                )
            await self.client.stop()

            interval = random.uniform(
                self.config.decision_min_seconds,
                self.config.decision_max_seconds,
            )
            sleep_time = max(0.0, interval - move_duration)
            if sleep_time > 0:
                remaining = self.config.trial_seconds - (time.monotonic() - trial_start_monotonic)
                if remaining <= 0:
                    return
                await asyncio.sleep(min(sleep_time, remaining))
