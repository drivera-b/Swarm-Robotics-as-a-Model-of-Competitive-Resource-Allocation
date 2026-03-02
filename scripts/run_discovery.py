#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.config import save_config
from src.discovery import parse_selection_input, print_discovered, scan_bolts


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Scan/select Sphero BOLT robots and save config.json")
    parser.add_argument("--timeout", type=float, default=10.0, help="BLE scan timeout in seconds")
    parser.add_argument(
        "--config",
        type=Path,
        default=PROJECT_ROOT / "config.json",
        help="Output config path",
    )
    parser.add_argument(
        "--list-only",
        action="store_true",
        help="Only list discovered robots; do not save config",
    )
    parser.add_argument(
        "--select",
        type=str,
        default="",
        help="Comma-separated selection (e.g., '1,2,3' or names/addresses)",
    )
    return parser


def main() -> int:
    args = build_arg_parser().parse_args()
    try:
        devices = scan_bolts(timeout=args.timeout)
    except Exception as exc:
        print(f"Discovery failed: {exc}")
        return 1
    print_discovered(devices)

    if not devices:
        return 1

    if args.list_only and not args.select:
        return 0

    selection_raw = args.select
    if not selection_raw:
        selection_raw = input(
            "\nSelect robots by comma-separated index/name/address (example: 1,2,3): "
        ).strip()

    try:
        selected = parse_selection_input(selection_raw, devices)
    except Exception as exc:
        print(f"Selection failed: {exc}")
        return 1
    if not selected:
        print("No robots selected; config was not written.")
        return 1

    save_config(args.config, {"robots": selected})
    print(f"\nSaved {len(selected)} robot(s) to: {args.config}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
