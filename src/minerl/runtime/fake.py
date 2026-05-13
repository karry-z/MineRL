from __future__ import annotations

import numpy as np

from minerl.runtime.backend import BackendFrame


class FakeBackend:
    """Deterministic backend for unit tests and API checks."""

    def __init__(self) -> None:
        self.task = None
        self.steps = 0
        self.closed = False
        self.last_commands = ""

    def reset(self, task, *, seed: int | None, options: dict) -> BackendFrame:
        self.task = task
        self.steps = 0
        self.closed = False
        width, height = task.resolution
        return BackendFrame(
            pov=np.zeros((height, width, 3), dtype=np.uint8),
            info={"inventory": [], "life_stats": {}, "location_stats": {}},
        )

    def step(self, commands: str) -> BackendFrame:
        self.steps += 1
        self.last_commands = commands
        width, height = self.task.resolution
        return BackendFrame(
            pov=np.full((height, width, 3), self.steps % 255, dtype=np.uint8),
            info={"inventory": [], "life_stats": {}, "location_stats": {}},
            reward=0.0,
            done=False,
        )

    def close(self) -> None:
        self.closed = True
