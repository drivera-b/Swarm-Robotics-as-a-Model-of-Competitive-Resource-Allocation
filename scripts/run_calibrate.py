#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.trial import connect_clients, disconnect_clients


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Calibrate heading reference for configured BOLT robots")
    parser.add_argument("--num-robots", type=int, default=3, help="How many configured robots to calibrate")
    parser.add_argument("--scan-timeout", type=float, default=10.0, help="BLE scan timeout")
    parser.add_argument(
        "--config",
        type=Path,
        default=PROJECT_ROOT / "config.json",
        help="Config JSON path",
    )
    parser.add_argument(
        "--test-roll",
        action="store_true",
        help="After calibration, do a short heading-0 test roll for each robot.",
    )
    parser.add_argument("--test-speed", type=int, default=25, help="Speed used for --test-roll")
    parser.add_argument("--test-seconds", type=float, default=0.5, help="Duration used for --test-roll")
    return parser


async def run_calibration(
    *,
    config_path: Path,
    num_robots: int,
    scan_timeout: float,
    test_roll: bool,
    test_speed: int,
    test_seconds: float,
) -> None:
    print(
        "Calibration preflight: place all robots in center box with the same physical forward orientation."
    )
    clients = await connect_clients(
        config_path=config_path,
        num_robots=num_robots,
        scan_timeout=scan_timeout,
    )
    try:
        print("Recalibrating heading references...")
        for client in clients:
            await client.calibrate_heading_reference()

        if test_roll:
            print(f"Running heading-0 test roll: speed={test_speed}, duration={test_seconds}s")
            for client in clients:
                print(f" - {client.robot_id}")
                await client.roll_for(heading=0, speed=test_speed, duration=test_seconds)
                await client.stop()
                await asyncio.sleep(0.2)
    finally:
        await disconnect_clients(clients)


def main() -> int:
    args = build_arg_parser().parse_args()
    try:
        asyncio.run(
            run_calibration(
                config_path=args.config,
                num_robots=args.num_robots,
                scan_timeout=args.scan_timeout,
                test_roll=args.test_roll,
                test_speed=args.test_speed,
                test_seconds=args.test_seconds,
            )
        )
    except Exception as exc:
        print(f"Calibration failed: {exc}")
        return 1
    print("Calibration finished.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
