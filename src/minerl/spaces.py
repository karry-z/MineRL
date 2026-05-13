from __future__ import annotations

from collections import OrderedDict
from typing import Any

import gymnasium as gym
import numpy as np


def zero_value(space: gym.Space) -> Any:
    """Return a deterministic zero/no-op value for a Gymnasium space."""
    if isinstance(space, gym.spaces.Dict):
        return OrderedDict((key, zero_value(child)) for key, child in space.spaces.items())
    if isinstance(space, gym.spaces.Discrete):
        return int(space.start)
    if isinstance(space, gym.spaces.MultiDiscrete):
        return np.zeros(space.nvec.shape, dtype=space.dtype)
    if isinstance(space, gym.spaces.Box):
        value = np.zeros(space.shape, dtype=space.dtype)
        return np.clip(value, space.low, space.high).astype(space.dtype)
    if isinstance(space, gym.spaces.Text):
        return ""
    raise TypeError(f"No zero value rule for space {space!r}")


def scalar_box(low: float, high: float, dtype: type | np.dtype) -> gym.spaces.Box:
    return gym.spaces.Box(low=low, high=high, shape=(), dtype=dtype)
