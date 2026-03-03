from __future__ import annotations

import asyncio
import time
from datetime import datetime
from pathlib import Path

from src.agent import AgentConfig, RobotAgent
from src.config import load_config, selected_robot_targets
from src.crowding import ChoiceRegistry, InferredCrowdingSource, ManualCrowdingSource
from src.discovery import resolve_selected_toys
from src.robot_client import RobotClient
from src.trial_logger import TrialLogger


def _robot_id_from_target(target: dict[str, str], fallback_idx: int) -> str:
    name = (target.get("name") or "").strip()
    address = (target.get("address") or "").strip()
    if name:
        return name
    if address:
        return address
    return f"robot_{fallback_idx + 1}"


async def connect_clients(
    *,
    config_path: Path,
    num_robots: int,
    scan_timeout: float,
) -> list[RobotClient]:
    config = load_config(config_path)
    targets = selected_robot_targets(config, num_robots)
    # Run SDK scan in a worker thread to avoid nested asyncio.run() conflicts.
    toys = await asyncio.to_thread(resolve_selected_toys, targets, scan_timeout)

    clients: list[RobotClient] = []
    for idx, (target, toy) in enumerate(zip(targets, toys)):
        robot_id = _robot_id_from_target(target, idx)
        client = RobotClient(toy=toy, robot_id=robot_id)
        print(f"Connecting [{idx + 1}/{len(toys)}] {robot_id} ...")
        await client.connect()
        clients.append(client)
    return clients


async def disconnect_clients(clients: list[RobotClient]) -> None:
    for client in clients:
        try:
            await client.disconnect()
        except Exception as exc:
            print(f"Warning: disconnect failed for {client.robot_id}: {exc}")


async def run_mvp_test(
    *,
    config_path: Path,
    num_robots: int,
    scan_timeout: float,
    speed: int,
    roll_seconds: float,
    cycles: int = 3,
) -> None:
    clients = await connect_clients(
        config_path=config_path,
        num_robots=num_robots,
        scan_timeout=scan_timeout,
    )
    headings = [0, 90, 180, 270]

    try:
        for cycle in range(cycles):
            print(f"\nMVP cycle {cycle + 1}/{cycles}")
            tasks = []
            for idx, client in enumerate(clients):
                heading = headings[(cycle + idx) % len(headings)]
                print(f" - {client.robot_id}: heading={heading} speed={speed}")
                tasks.append(client.roll_for(heading=heading, speed=speed, duration=roll_seconds))
            await asyncio.gather(*tasks)
            await asyncio.sleep(0.4)
    finally:
        print("\nStopping and disconnecting MVP robots...")
        await disconnect_clients(clients)


async def run_trial(
    *,
    config_path: Path,
    data_dir: Path,
    num_robots: int,
    lambda_value: int,
    crowding_mode: str,
    trial_seconds: int,
    scan_timeout: float,
    speed: int,
    roll_seconds: float,
    decision_min_seconds: float,
    decision_max_seconds: float,
) -> Path:
    clients = await connect_clients(
        config_path=config_path,
        num_robots=num_robots,
        scan_timeout=scan_timeout,
    )

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_path = data_dir / (
        f"trial_{timestamp}_lambda{lambda_value}_n{num_robots}_{crowding_mode}.csv"
    )
    logger = TrialLogger(csv_path)

    choice_registry = ChoiceRegistry()
    if crowding_mode == "manual":
        crowding_source = ManualCrowdingSource()
    elif crowding_mode == "inferred":
        crowding_source = InferredCrowdingSource(choice_registry)
    else:
        raise ValueError("crowding_mode must be 'manual' or 'inferred'")

    agent_config = AgentConfig(
        lambda_value=lambda_value,
        decision_min_seconds=decision_min_seconds,
        decision_max_seconds=decision_max_seconds,
        roll_seconds=roll_seconds,
        speed=speed,
        trial_seconds=trial_seconds,
    )
    agents = [
        RobotAgent(
            robot_id=client.robot_id,
            client=client,
            config=agent_config,
            crowding_source=crowding_source,
            choice_registry=choice_registry,
            logger=logger,
        )
        for client in clients
    ]

    crowding_source.start()
    trial_start = time.monotonic()
    print(
        f"\nTrial start: robots={num_robots}, lambda={lambda_value}, "
        f"mode={crowding_mode}, duration={trial_seconds}s"
    )

    try:
        tasks = [asyncio.create_task(agent.run(trial_start)) for agent in agents]
        await asyncio.gather(*tasks)
    finally:
        crowding_source.stop()
        logger.close()
        print("\nStopping and disconnecting trial robots...")
        await disconnect_clients(clients)

    return csv_path
