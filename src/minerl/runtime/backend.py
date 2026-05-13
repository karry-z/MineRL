from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Protocol

import numpy as np


class BackendError(RuntimeError):
    """Base error for runtime/backend failures."""


@dataclass(slots=True)
class BackendFrame:
    pov: bytes | np.ndarray | None
    info: Mapping[str, Any] | str | None
    reward: float = 0.0
    done: bool = False


class Backend(Protocol):
    def reset(self, task: Any, *, seed: int | None, options: dict[str, Any]) -> BackendFrame:
        ...

    def step(self, commands: str) -> BackendFrame:
        ...

    def close(self) -> None:
        ...
