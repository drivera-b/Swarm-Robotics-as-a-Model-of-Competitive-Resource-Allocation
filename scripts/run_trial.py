#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
from pathlib import Path
import random
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.constants import DEFAULT_TRIAL_SECONDS
from src.trial import run_trial


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run 90-second decentralized multi-BOLT trial")
    parser.add_argument("--num-robots", type=int, default=3, help="How many robots to run")
    parser.add_argument("--lambda-value", type=int, choices=[2, 6, 10], required=True)
    parser.add_argument(
        "--crowding-mode",
        type=str,
        choices=["manual", "inferred"],
        default="inferred",
    )
    parser.add_argument("--trial-seconds", type=int, default=DEFAULT_TRIAL_SECONDS)
    parser.add_argument("--speed", type=int, default=60, help="Roll speed")
    parser.add_argument("--roll-seconds", type=float, default=2.0, help="Roll duration")
    parser.add_argument("--decision-min", type=float, default=2.0, help="Decision loop min interval")
    parser.add_argument("--decision-max", type=float, default=3.0, help="Decision loop max interval")
    parser.add_argument("--scan-timeout", type=float, default=10.0)
    parser.add_argument("--seed", type=int, default=0, help="0 = no fixed seed")
    parser.add_argument(
        "--config",
        type=Path,
        default=PROJECT_ROOT / "config.json",
        help="Config JSON path",
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=PROJECT_ROOT / "data",
        help="CSV output directory",
    )
    return parser


def main() -> int:
    args = build_arg_parser().parse_args()
    if args.decision_min > args.decision_max:
        print("Invalid arguments: --decision-min must be <= --decision-max")
        return 1
    if args.seed:
        random.seed(args.seed)

    try:
        output_csv = asyncio.run(
            run_trial(
                config_path=args.config,
                data_dir=args.data_dir,
                num_robots=args.num_robots,
                lambda_value=args.lambda_value,
                crowding_mode=args.crowding_mode,
                trial_seconds=args.trial_seconds,
                scan_timeout=args.scan_timeout,
                speed=args.speed,
                roll_seconds=args.roll_seconds,
                decision_min_seconds=args.decision_min,
                decision_max_seconds=args.decision_max,
            )
        )
    except Exception as exc:
        print(f"Trial failed: {exc}")
        return 1
    print(f"Trial complete. CSV written to: {output_csv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
