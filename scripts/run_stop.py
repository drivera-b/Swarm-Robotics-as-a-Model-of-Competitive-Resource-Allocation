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
    parser = argparse.ArgumentParser(description="Emergency stop for configured Sphero BOLT robots")
    parser.add_argument("--num-robots", type=int, default=3, help="How many configured robots to stop")
    parser.add_argument("--scan-timeout", type=float, default=10.0, help="BLE scan timeout")
    parser.add_argument(
        "--config",
        type=Path,
        default=PROJECT_ROOT / "config.json",
        help="Config JSON path",
    )
    return parser


async def run_stop(*, config_path: Path, num_robots: int, scan_timeout: float) -> None:
    clients = await connect_clients(
        config_path=config_path,
        num_robots=num_robots,
        scan_timeout=scan_timeout,
    )
    try:
        print(f"Sending STOP to {len(clients)} robot(s)...")
        await asyncio.gather(*(client.stop() for client in clients))
    finally:
        await disconnect_clients(clients)


def main() -> int:
    args = build_arg_parser().parse_args()
    try:
        asyncio.run(
            run_stop(
                config_path=args.config,
                num_robots=args.num_robots,
                scan_timeout=args.scan_timeout,
            )
        )
    except Exception as exc:
        print(f"Stop failed: {exc}")
        return 1

    print("All selected robots were sent stop and disconnected.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
