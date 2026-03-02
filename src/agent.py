from __future__ import annotations

import asyncio
import random
import time
from dataclasses import dataclass
from datetime import datetime

from src.constants import ZONE_HEADINGS, ZONES
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


class RobotAgent:
    def __init__(
        self,
        robot_id: str,
        client: RobotClient,
        config: AgentConfig,
        crowding_source: CrowdingSource,
        choice_registry: ChoiceRegistry,
        logger: TrialLogger,
    ) -> None:
        self.robot_id = robot_id
        self.client = client
        self.config = config
        self.crowding_source = crowding_source
        self.choice_registry = choice_registry
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

            heading = ZONE_HEADINGS[chosen_zone]
            await self.client.roll_for(
                heading=heading,
                speed=self.config.speed,
                duration=self.config.roll_seconds,
            )
            await self.client.stop()

            interval = random.uniform(
                self.config.decision_min_seconds,
                self.config.decision_max_seconds,
            )
            sleep_time = max(0.0, interval - self.config.roll_seconds)
            if sleep_time > 0:
                remaining = self.config.trial_seconds - (time.monotonic() - trial_start_monotonic)
                if remaining <= 0:
                    return
                await asyncio.sleep(min(sleep_time, remaining))
