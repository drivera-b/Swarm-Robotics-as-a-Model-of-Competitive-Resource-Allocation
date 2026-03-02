#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.trial import run_mvp_test


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run concurrent MVP movement test on selected BOLTs")
    parser.add_argument("--num-robots", type=int, default=3, help="How many configured robots to use")
    parser.add_argument("--speed", type=int, default=60, help="Roll speed")
    parser.add_argument("--roll-seconds", type=float, default=2.0, help="Roll duration in seconds")
    parser.add_argument("--cycles", type=int, default=3, help="Number of MVP cycles")
    parser.add_argument("--scan-timeout", type=float, default=10.0, help="BLE scan timeout")
    parser.add_argument(
        "--config",
        type=Path,
        default=PROJECT_ROOT / "config.json",
        help="Config JSON path",
    )
    return parser


def main() -> int:
    args = build_arg_parser().parse_args()
    try:
        asyncio.run(
            run_mvp_test(
                config_path=args.config,
                num_robots=args.num_robots,
                scan_timeout=args.scan_timeout,
                speed=args.speed,
                roll_seconds=args.roll_seconds,
                cycles=args.cycles,
            )
        )
    except Exception as exc:
        print(f"MVP test failed: {exc}")
        return 1
    print("MVP test finished.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
