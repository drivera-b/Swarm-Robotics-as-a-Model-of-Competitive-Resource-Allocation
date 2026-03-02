from __future__ import annotations

import asyncio
import csv
from pathlib import Path

from src.constants import ZONES


def format_crowding(crowding: dict[str, int]) -> str:
    return " ".join(f"{zone}:{crowding.get(zone, 0)}" for zone in ZONES)


class TrialLogger:
    FIELDNAMES = ["timestamp", "lambda", "segment", "robot_id", "chosen_zone", "crowding_used"]

    def __init__(self, output_path: Path) -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        self.output_path = output_path
        self._fh = output_path.open("w", encoding="utf-8", newline="")
        self._writer = csv.DictWriter(self._fh, fieldnames=self.FIELDNAMES)
        self._writer.writeheader()
        self._lock = asyncio.Lock()

    async def log_decision(
        self,
        timestamp: str,
        lambda_value: int,
        segment: str,
        robot_id: str,
        chosen_zone: str,
        crowding: dict[str, int],
    ) -> None:
        row = {
            "timestamp": timestamp,
            "lambda": lambda_value,
            "segment": segment,
            "robot_id": robot_id,
            "chosen_zone": chosen_zone,
            "crowding_used": format_crowding(crowding),
        }
        async with self._lock:
            self._writer.writerow(row)
            self._fh.flush()

    def close(self) -> None:
        self._fh.close()
