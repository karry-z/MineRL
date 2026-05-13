from __future__ import annotations

from collections import defaultdict

import gymnasium as gym
import numpy as np

import minerl  # noqa: F401
import minerl.human_play_interface as human_play_module
from minerl.human_play_interface import HumanPlayInterface
from minerl.runtime.backend import BackendFrame
from minerl.tasks.catalog import get_task


def test_public_task_listing_returns_ids() -> None:
    task_ids = minerl.list_tasks()
    assert "MineRLBasaltFindCave-v0" in task_ids
    assert all(isinstance(task_id, str) for task_id in task_ids)


def test_human_play_validation_accepts_dict_pov_key() -> None:
    task = get_task("MineRLBasaltFindCave-v0")
    dummy = type("Dummy", (), {})()
    dummy.action_space = task.action_space()
    dummy.observation_space = task.observation_space()
    HumanPlayInterface._validate_env(dummy)


def test_human_play_esc_confirmation_expires(monkeypatch) -> None:
    now = 100.0
    messages = []
    dummy = HumanPlayInterface.__new__(HumanPlayInterface)
    dummy._esc_armed_until = 0.0
    dummy._esc_exit_requested = False
    dummy.step_count = 0
    dummy._show_message = lambda text, **kwargs: messages.append(text)

    monkeypatch.setattr(human_play_module.time, "monotonic", lambda: now)

    HumanPlayInterface._handle_esc_press(dummy)
    assert HumanPlayInterface._consume_esc_action(dummy) == 0
    assert messages[-1].startswith("Esc will end the episode.")

    now += human_play_module.ESC_CONFIRM_WINDOW + 0.1
    HumanPlayInterface._handle_esc_press(dummy)
    assert HumanPlayInterface._consume_esc_action(dummy) == 0
    assert len(messages) == 2

    now += 1.0
    HumanPlayInterface._handle_esc_press(dummy)
    assert HumanPlayInterface._consume_esc_action(dummy) == 1
    assert HumanPlayInterface._consume_esc_action(dummy) == 0


def test_human_play_held_esc_is_one_press() -> None:
    calls = []
    esc_symbol = 123
    dummy = HumanPlayInterface.__new__(HumanPlayInterface)
    dummy._keymap = {"ESC": esc_symbol}
    dummy.pressed_keys = defaultdict(lambda: False)
    dummy._handle_esc_press = lambda: calls.append("esc")

    HumanPlayInterface._on_key_press(dummy, esc_symbol, None)
    HumanPlayInterface._on_key_press(dummy, esc_symbol, None)

    assert calls == ["esc"]


def test_registered_env_uses_gymnasium_api() -> None:
    env = gym.make("MineRLBasaltFindCave-v0", backend="fake")
    try:
        obs, info = env.reset(seed=123)
        assert set(obs) == {"pov"}
        assert obs["pov"].shape == (360, 640, 3)
        assert isinstance(info, dict)

        action = env.unwrapped.no_op_action()
        result = env.step(action)
        assert len(result) == 5
        next_obs, reward, terminated, truncated, step_info = result
        assert next_obs["pov"].shape == (360, 640, 3)
        assert isinstance(reward, float)
        assert terminated is False
        assert truncated is False
        assert isinstance(step_info, dict)
    finally:
        env.close()


def test_env_boundaries_are_logged(caplog) -> None:
    caplog.set_level("DEBUG", logger="minerl.envs.core")
    env = gym.make("MineRLBasaltFindCave-v0", backend="fake")
    try:
        env.reset(seed=123)
        env.step(env.unwrapped.no_op_action())
    finally:
        env.close()

    messages = "\n".join(record.getMessage() for record in caplog.records)
    assert "Resetting MineRLBasaltFindCave-v0" in messages
    assert "Reset finished for MineRLBasaltFindCave-v0" in messages
    assert "Stepping MineRLBasaltFindCave-v0" in messages
    assert "Step finished for MineRLBasaltFindCave-v0" in messages
    assert "Closing MineRLBasaltFindCave-v0" in messages
    assert "Closed MineRLBasaltFindCave-v0" in messages


def test_no_old_noop_alias_on_action_space() -> None:
    env = gym.make("MineRLTreechop-v0", backend="fake")
    try:
        assert not hasattr(env.action_space, "noop")
        action = env.unwrapped.no_op_action()
        assert action["forward"] == 0
        assert np.all(action["camera"] == 0)
    finally:
        env.close()


def test_basalt_esc_action_terminates_episode() -> None:
    env = gym.make("MineRLBasaltFindCave-v0", backend="fake")
    try:
        env.reset(seed=123)
        action = env.unwrapped.no_op_action()
        action["ESC"] = 1
        _, _, terminated, truncated, info = env.step(action)
        assert terminated is True
        assert truncated is False
        assert info["terminated_by"] == "ESC"
    finally:
        env.close()


class InventoryRewardBackend:
    def __init__(self) -> None:
        self.task = None
        self.step_index = 0
        self.closed = False

    def reset(self, task, *, seed, options):
        self.task = task
        self.step_index = 0
        return BackendFrame(pov=None, info={"inventory": [], "life_stats": {}, "location_stats": {}})

    def step(self, commands):
        self.step_index += 1
        inventories = [
            [{"type": "minecraft:oak_log", "quantity": 1}],
            [{"type": "minecraft:oak_log", "quantity": 1}],
            [{"type": "minecraft:diamond_shovel", "quantity": 1}],
        ]
        return BackendFrame(
            pov=None,
            info={
                "inventory": inventories[self.step_index - 1],
                "life_stats": {},
                "location_stats": {},
            },
            reward=0.0,
            done=False,
        )

    def close(self):
        self.closed = True


def test_diamond_shovel_python_reward_groups_are_sparse_and_terminal() -> None:
    backend = InventoryRewardBackend()
    env = gym.make("MineRLObtainDiamondShovel-v0", backend=backend)
    try:
        env.reset(seed=123)
        action = env.unwrapped.no_op_action()

        _, reward, terminated, truncated, _ = env.step(action)
        assert reward == 1.0
        assert terminated is False
        assert truncated is False

        _, reward, terminated, truncated, _ = env.step(action)
        assert reward == 0.0
        assert terminated is False
        assert truncated is False

        _, reward, terminated, truncated, _ = env.step(action)
        assert reward == 2048.0
        assert terminated is True
        assert truncated is False
    finally:
        env.close()
