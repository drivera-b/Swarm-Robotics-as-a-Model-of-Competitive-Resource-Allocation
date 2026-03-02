from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_config(config_path: Path) -> dict[str, Any]:
    if not config_path.exists():
        raise FileNotFoundError(
            f"Config not found at {config_path}. Run scripts/run_discovery.py first."
        )
    with config_path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if "robots" not in data or not isinstance(data["robots"], list):
        raise ValueError("config.json must contain a top-level 'robots' list.")
    return data


def save_config(config_path: Path, data: dict[str, Any]) -> None:
    config_path.parent.mkdir(parents=True, exist_ok=True)
    with config_path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def selected_robot_targets(config: dict[str, Any], num_robots: int) -> list[dict[str, str]]:
    robots = config.get("robots", [])
    if len(robots) < num_robots:
        raise ValueError(
            f"Config only has {len(robots)} robots, but {num_robots} were requested."
        )
    return robots[:num_robots]
