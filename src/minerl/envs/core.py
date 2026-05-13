from __future__ import annotations

import logging
import time
from typing import Any

import gymnasium as gym
import numpy as np

from minerl.runtime.backend import Backend, BackendError
from minerl.runtime.fake import FakeBackend
from minerl.runtime.minecraft import MinecraftBackend
from minerl.tasks.catalog import get_task
from minerl.tasks.schema import TaskSpec

logger = logging.getLogger(__name__)


class MineRLEnv(gym.Env):
    """Gymnasium environment backed by a Minecraft/Malmo runtime."""

    metadata = {"render_modes": ["human", "rgb_array"], "render_fps": 20}

    def __init__(
        self,
        task_id: str,
        *,
        backend: Backend | str | None = None,
        render_mode: str | None = None,
    ) -> None:
        self.task: TaskSpec = get_task(task_id)
        self.render_mode = render_mode
        self.observation_space = self.task.observation_space()
        self.action_space = self.task.action_space()
        self._backend: Backend = self._coerce_backend(backend)
        self._last_obs: dict[str, Any] | None = None
        self._episode_done = False
        self._reset_failed = False
        self._inventory_reward_seen: set[int] = set()

    def _coerce_backend(self, backend: Backend | str | None) -> Backend:
        if backend is None:
            return MinecraftBackend()
        if isinstance(backend, str):
            if backend == "fake":
                return FakeBackend()
            if backend == "minecraft":
                return MinecraftBackend()
            raise ValueError(f"Unknown backend {backend!r}")
        return backend

    def reset(
        self,
        *,
        seed: int | None = None,
        options: dict[str, Any] | None = None,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        super().reset(seed=seed)
        started = time.monotonic()
        logger.info(f"Resetting {self.task.id} with seed {seed}.")
        self._episode_done = False
        self._reset_failed = False
        self._inventory_reward_seen.clear()

        try:
            frame = self._backend.reset(self.task, seed=seed, options=options or {})
            obs, info = self.task.observation_from_frame(frame)
        except BackendError as exc:
            obs = self.task.empty_observation()
            info = {"error": {"type": exc.__class__.__name__, "message": str(exc)}}
            self._reset_failed = True
            logger.error(f"Reset failed for {self.task.id} after {_duration_ms(started)} ms: {exc}")

        self._last_obs = obs
        logger.info(
            f"Reset finished for {self.task.id} in {_duration_ms(started)} ms; "
            f"failed={self._reset_failed}."
        )
        return obs, info

    def step(
        self,
        action: dict[str, Any],
    ) -> tuple[dict[str, Any], float, bool, bool, dict[str, Any]]:
        if self._episode_done:
            raise RuntimeError("step() called after the episode has ended; call reset() first")

        if self._reset_failed:
            self._episode_done = True
            obs = self._last_obs or self.task.empty_observation()
            logger.warning(f"step() was called for {self.task.id} after reset had already failed.")
            return obs, 0.0, False, True, {"error": {"message": "reset failed"}}

        started = time.monotonic()
        logger.debug(f"Stepping {self.task.id}.")
        try:
            commands = self.task.action_to_commands(action)
            frame = self._backend.step(commands)
            obs, info = self.task.observation_from_frame(frame)
            reward = float(frame.reward)
            inventory_reward, inventory_done = self.task.inventory_reward_from_observation(
                obs,
                self._inventory_reward_seen,
            )
            reward += inventory_reward
            terminated = bool(frame.done)
            terminated = terminated or inventory_done
            truncated = False
            if self.task.esc_terminates and _action_truthy(action.get("ESC", 0)):
                info = dict(info)
                info["terminated_by"] = "ESC"
                terminated = True
            if frame.done:
                info = dict(info)
                info["backend_done"] = True
            if inventory_done:
                info = dict(info)
                info["terminated_by"] = "inventory_reward"
        except BackendError as exc:
            obs = self.task.empty_observation()
            info = {"error": {"type": exc.__class__.__name__, "message": str(exc)}}
            reward = 0.0
            terminated = False
            truncated = True
            logger.error(
                f"Step failed for {self.task.id} after {_duration_ms(started)} ms; "
                f"action={_summarize_action(action)}: {exc}"
            )

        self._last_obs = obs
        self._episode_done = terminated or truncated
        if self._episode_done:
            logger.info(
                f"Episode ended for {self.task.id}; terminated={terminated}, truncated={truncated}, "
                f"reward={reward}, info={_summarize_info(info)}."
            )
        logger.debug(
            f"Step finished for {self.task.id} in {_duration_ms(started)} ms; "
            f"reward={reward}, terminated={terminated}, truncated={truncated}."
        )
        return obs, reward, terminated, truncated, info

    def no_op_action(self) -> dict[str, Any]:
        return self.task.no_op_action()

    def render(self) -> np.ndarray | None:
        if self._last_obs is None or "pov" not in self._last_obs:
            return None
        frame = self._last_obs["pov"]
        if self.render_mode == "human":
            from minerl.rendering.human import show_rgb

            show_rgb(frame)
        return frame

    def close(self) -> None:
        started = time.monotonic()
        logger.info(f"Closing {self.task.id}.")
        self._backend.close()
        logger.info(f"Closed {self.task.id} in {_duration_ms(started)} ms.")


def _action_truthy(value: Any) -> bool:
    try:
        return bool(np.asarray(value).item())
    except Exception:
        return bool(value)


def _duration_ms(started: float) -> int:
    return int((time.monotonic() - started) * 1000)


def _summarize_action(action: dict[str, Any]) -> str:
    active: list[str] = []
    for key, value in action.items():
        if key == "camera":
            array = np.asarray(value)
            if np.any(array != 0):
                active.append(f"camera={array.tolist()}")
        elif _action_truthy(value):
            active.append(str(key))
    return ",".join(active) if active else "noop"


def _summarize_info(info: dict[str, Any]) -> str:
    summary: dict[str, Any] = {}
    for key in ("terminated_by", "backend_done", "error"):
        if key in info:
            summary[key] = info[key]
    if not summary:
        summary["keys"] = sorted(info)
    return repr(summary)
