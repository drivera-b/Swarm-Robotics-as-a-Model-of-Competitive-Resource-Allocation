from __future__ import annotations

import asyncio
import time
from typing import Any

from src.sdk import require_sphero_sdk


class RobotConnectionError(RuntimeError):
    pass


class RobotClient:
    def __init__(self, toy: Any, robot_id: str) -> None:
        _, _, sphero_api = require_sphero_sdk()
        self._api_class = sphero_api
        self.toy = toy
        self.robot_id = robot_id
        self._api = None
        self._command_lock = asyncio.Lock()

    async def connect(self) -> None:
        try:
            self._api = self._api_class(self.toy)
            await asyncio.to_thread(self._api.__enter__)
            await self.calibrate_heading_reference()
            await asyncio.sleep(0.2)
        except Exception as exc:
            raise RobotConnectionError(f"Failed to connect robot '{self.robot_id}': {exc}") from exc

    async def disconnect(self) -> None:
        if self._api is None:
            return
        try:
            await self.stop()
        finally:
            await asyncio.to_thread(self._api.__exit__, None, None, None)
            self._api = None

    async def stop(self) -> None:
        async with self._command_lock:
            await asyncio.to_thread(self._stop_sync)

    async def roll_for(self, heading: int, speed: int, duration: float) -> None:
        async with self._command_lock:
            await asyncio.to_thread(self._roll_sync, heading, speed, duration)

    async def calibrate_heading_reference(self) -> None:
        """Reset aim so current physical forward direction becomes heading 0."""
        async with self._command_lock:
            await asyncio.to_thread(self._calibrate_heading_reference_sync)

    def _calibrate_heading_reference_sync(self) -> None:
        api = self._require_api()

        if hasattr(api, "set_speed"):
            try:
                api.set_speed(0)
            except TypeError:
                try:
                    api.set_speed(speed=0)
                except TypeError:
                    pass

        if hasattr(api, "reset_aim"):
            api.reset_aim()
        if hasattr(api, "set_heading"):
            try:
                api.set_heading(0)
            except TypeError:
                api.set_heading(heading=0)
        time.sleep(0.05)

    def _roll_sync(self, heading: int, speed: int, duration: float) -> None:
        api = self._require_api()

        # Method name compatibility across SDK versions.
        if hasattr(api, "roll"):
            try:
                api.roll(heading=heading, speed=speed, duration=duration)
            except TypeError:
                api.roll(heading, speed, duration)
            return

        # Fallback path if roll(...) signature is not available.
        if hasattr(api, "set_heading"):
            api.set_heading(heading)
        if hasattr(api, "set_speed"):
            api.set_speed(speed)
            time.sleep(duration)
            self._stop_sync()
            return

        raise RuntimeError("SDK method mismatch: no roll/set_heading/set_speed available.")

    def _stop_sync(self) -> None:
        api = self._require_api()

        if hasattr(api, "stop_roll"):
            try:
                api.stop_roll()
                return
            except TypeError:
                pass

        if hasattr(api, "set_speed"):
            try:
                api.set_speed(0)
                return
            except TypeError:
                try:
                    api.set_speed(speed=0)
                    return
                except TypeError:
                    pass

        if hasattr(api, "stop"):
            api.stop()
            return

        raise RuntimeError("SDK method mismatch: no stop method available.")

    def _require_api(self) -> Any:
        if self._api is None:
            raise RuntimeError(f"Robot '{self.robot_id}' is not connected.")
        return self._api
