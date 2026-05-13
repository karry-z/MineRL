from __future__ import annotations

from gymnasium.envs.registration import register, registry

from minerl.tasks.catalog import list_task_specs


def register_all() -> None:
    """Register all built-in task IDs with Gymnasium."""
    for task in list_task_specs():
        if task.id in registry:
            continue
        register(
            id=task.id,
            entry_point="minerl.envs.core:MineRLEnv",
            kwargs={"task_id": task.id},
            max_episode_steps=task.max_episode_steps,
        )
