from __future__ import annotations

from typing import Any

from src.sdk import require_sphero_sdk


def _normalize(value: str | None) -> str:
    return (value or "").strip().lower()


def scan_bolts(timeout: float = 10.0) -> list[dict[str, str]]:
    scanner, BOLT, _ = require_sphero_sdk()
    toys = scanner.find_toys(timeout=timeout, toy_types=[BOLT])

    seen: set[str] = set()
    found: list[dict[str, str]] = []
    for toy in toys:
        name = getattr(toy, "name", "UNKNOWN")
        address = getattr(toy, "address", "")
        key = _normalize(address) or _normalize(name)
        if key in seen:
            continue
        seen.add(key)
        found.append({"name": str(name), "address": str(address)})

    found.sort(key=lambda x: (x["name"].lower(), x["address"].lower()))
    return found


def print_discovered(devices: list[dict[str, str]]) -> None:
    if not devices:
        print("No BOLT robots found.")
        return
    print("\nDiscovered BOLT robots:")
    for idx, device in enumerate(devices, start=1):
        print(f"{idx:>2}. {device['name']:<18}  {device['address']}")


def parse_selection_input(selection_raw: str, devices: list[dict[str, str]]) -> list[dict[str, str]]:
    tokens = [t.strip() for t in selection_raw.split(",") if t.strip()]
    if not tokens:
        return []

    chosen: list[dict[str, str]] = []
    used_keys: set[str] = set()

    def add_device(device: dict[str, str]) -> None:
        key = f"{_normalize(device['name'])}|{_normalize(device['address'])}"
        if key not in used_keys:
            chosen.append(device)
            used_keys.add(key)

    for token in tokens:
        if token.isdigit():
            idx = int(token) - 1
            if idx < 0 or idx >= len(devices):
                raise ValueError(f"Index {token} is out of range.")
            add_device(devices[idx])
            continue

        token_n = _normalize(token)
        match = next(
            (
                d
                for d in devices
                if _normalize(d["address"]) == token_n or _normalize(d["name"]) == token_n
            ),
            None,
        )
        if match is None:
            raise ValueError(f"No discovered robot matches '{token}'.")
        add_device(match)

    return chosen


def resolve_selected_toys(selected: list[dict[str, str]], timeout: float = 10.0) -> list[Any]:
    scanner, BOLT, _ = require_sphero_sdk()
    discovered_toys = list(scanner.find_toys(timeout=timeout, toy_types=[BOLT]))
    unresolved: list[dict[str, str]] = []
    resolved: list[Any] = []
    used_indices: set[int] = set()

    for target in selected:
        target_name = _normalize(target.get("name", ""))
        target_address = _normalize(target.get("address", ""))
        matched_idx = None

        for idx, toy in enumerate(discovered_toys):
            if idx in used_indices:
                continue
            toy_name = _normalize(getattr(toy, "name", ""))
            toy_address = _normalize(getattr(toy, "address", ""))
            address_match = bool(target_address) and toy_address == target_address
            name_match = bool(target_name) and toy_name == target_name
            if address_match or name_match:
                matched_idx = idx
                break

        if matched_idx is None:
            unresolved.append(target)
            continue

        used_indices.add(matched_idx)
        resolved.append(discovered_toys[matched_idx])

    if unresolved:
        missing = ", ".join(
            f"{item.get('name', 'UNKNOWN')} ({item.get('address', 'NO-ADDR')})"
            for item in unresolved
        )
        raise RuntimeError(
            f"Could not resolve configured robot(s): {missing}. "
            "Check power, BLE range, and config.json values."
        )

    return resolved
