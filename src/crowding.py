from __future__ import annotations

import re
import threading
from abc import ABC, abstractmethod

from src.constants import ZONES

_CROWDING_PATTERN = re.compile(r"([ABCDabcd])\s*[:=]\s*(\d+)")


def empty_crowding() -> dict[str, int]:
    return {zone: 0 for zone in ZONES}


def parse_crowding_line(line: str) -> dict[str, int] | None:
    matches = _CROWDING_PATTERN.findall(line)
    if not matches:
        return None
    values = empty_crowding()
    for zone, value in matches:
        values[zone.upper()] = int(value)
    return values


class CrowdingSource(ABC):
    @abstractmethod
    def get_counts(self, robot_id: str) -> dict[str, int]:
        raise NotImplementedError

    def start(self) -> None:
        return

    def stop(self) -> None:
        return


class ChoiceRegistry:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._choices: dict[str, str] = {}

    def set_choice(self, robot_id: str, zone: str) -> None:
        with self._lock:
            self._choices[robot_id] = zone

    def counts(self, exclude_robot_id: str | None = None) -> dict[str, int]:
        counts = empty_crowding()
        with self._lock:
            for rid, zone in self._choices.items():
                if exclude_robot_id and rid == exclude_robot_id:
                    continue
                if zone in counts:
                    counts[zone] += 1
        return counts


class InferredCrowdingSource(CrowdingSource):
    def __init__(self, registry: ChoiceRegistry) -> None:
        self.registry = registry

    def get_counts(self, robot_id: str) -> dict[str, int]:
        return self.registry.counts(exclude_robot_id=robot_id)


class ManualCrowdingSource(CrowdingSource):
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._counts = empty_crowding()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread is not None:
            return
        self._thread = threading.Thread(
            target=self._input_loop,
            name="manual-crowding-input",
            daemon=True,
        )
        self._thread.start()
        print(
            "Manual crowding input ready. Enter updates like 'A:2 B:3 C:1 D:2'. "
            "Press Enter to keep current values."
        )

    def stop(self) -> None:
        self._stop_event.set()

    def get_counts(self, robot_id: str) -> dict[str, int]:
        with self._lock:
            return dict(self._counts)

    def _input_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                line = input("Crowding update> ").strip()
            except EOFError:
                return
            if self._stop_event.is_set():
                return
            if not line:
                continue
            parsed = parse_crowding_line(line)
            if parsed is None:
                print("Invalid format. Use: A:2 B:3 C:1 D:2")
                continue
            with self._lock:
                self._counts = parsed
