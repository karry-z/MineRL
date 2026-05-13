from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
import json
from typing import Any, Mapping

import gymnasium as gym
import numpy as np

from minerl.runtime.backend import BackendFrame
from minerl.spaces import scalar_box, zero_value
from minerl.tasks.constants import WOOD_LOG_ITEMS, WOOD_PLANK_ITEMS


@dataclass(frozen=True, slots=True)
class ActionField:
    name: str
    command: str | None = None
    kind: str = "button"
    low: float = -180.0
    high: float = 180.0
    shape: tuple[int, ...] = (2,)
    options: tuple[str, ...] = ()

    def space(self) -> gym.Space:
        if self.kind == "camera":
            return gym.spaces.Box(self.low, self.high, shape=self.shape, dtype=np.float32)
        if self.kind == "enum":
            return gym.spaces.Discrete(len(self.options))
        if self.kind == "item":
            return gym.spaces.Discrete(2)
        return gym.spaces.Discrete(2)

    def no_op(self) -> Any:
        return zero_value(self.space())

    def to_command(self, value: Any) -> str:
        command = self.command or self.name
        if self.kind == "camera":
            array = np.asarray(value, dtype=np.float32).reshape(-1)
            pitch, yaw = float(array[0]), float(array[1])
            return f"{command} {pitch} {yaw}"
        if self.kind == "enum":
            option = self._option_value(value)
            if option == "none":
                return ""
            return f"{command} {option}"
        return f"{command} {int(value)}"

    def _option_value(self, value: Any) -> str:
        if isinstance(value, str):
            if value not in self.options:
                raise ValueError(f"{self.name} must be one of {self.options}, got {value!r}")
            return value
        index = int(value)
        if index < 0 or index >= len(self.options):
            raise ValueError(f"{self.name} index {index} is outside {self.options}")
        return self.options[index]


@dataclass(frozen=True, slots=True)
class ObservationField:
    name: str
    kind: str
    resolution: tuple[int, int] | None = None
    items: tuple[str, ...] = ()

    def space(self) -> gym.Space:
        if self.kind == "pov":
            width, height = self.resolution or (640, 360)
            return gym.spaces.Box(0, 255, shape=(height, width, 3), dtype=np.uint8)
        if self.kind == "inventory":
            return gym.spaces.Dict(
                OrderedDict((item, scalar_box(0, 2304, np.int32)) for item in sorted(self.items))
            )
        if self.kind == "compass":
            return gym.spaces.Dict(
                OrderedDict([("angle", scalar_box(-180.0, 180.0, np.float32))])
            )
        if self.kind == "life_stats":
            return gym.spaces.Dict(
                OrderedDict(
                    [
                        ("is_alive", scalar_box(0, 1, np.int8)),
                        ("life", scalar_box(0, 20, np.float32)),
                        ("score", scalar_box(0, np.inf, np.float32)),
                        ("food", scalar_box(0, 20, np.float32)),
                        ("saturation", scalar_box(0, 20, np.float32)),
                        ("xp", scalar_box(0, np.inf, np.float32)),
                        ("breath", scalar_box(0, 300, np.float32)),
                    ]
                )
            )
        if self.kind == "location_stats":
            return gym.spaces.Dict(
                OrderedDict(
                    (key, scalar_box(-np.inf, np.inf, np.float32))
                    for key in ("xpos", "ypos", "zpos", "yaw", "pitch")
                )
            )
        if self.kind == "equipped_items":
            item_charset = "abcdefghijklmnopqrstuvwxyz0123456789_"
            hand_space = gym.spaces.Dict(
                OrderedDict(
                    [
                        ("type", gym.spaces.Text(max_length=64, min_length=0, charset=item_charset)),
                        ("damage", scalar_box(-1, 1562, np.int32)),
                        ("max_damage", scalar_box(-1, 1562, np.int32)),
                    ]
                )
            )
            return gym.spaces.Dict(
                OrderedDict(
                    [
                        ("mainhand", hand_space),
                        ("offhand", hand_space),
                    ]
                )
            )
        return gym.spaces.Dict({})

    def empty(self) -> Any:
        return zero_value(self.space())

    def parse(self, pov: bytes | np.ndarray | None, info: Mapping[str, Any]) -> Any:
        if self.kind == "pov":
            return _parse_pov(pov, self.resolution or (640, 360))
        if self.kind == "inventory":
            return _parse_inventory(info, self.items)
        if self.kind == "compass":
            return OrderedDict([("angle", np.asarray(info.get("compassAngle", 0.0), dtype=np.float32))])
        if self.kind == "life_stats":
            src = info.get("life_stats", {})
            return _parse_numeric_dict(self.space(), src)
        if self.kind == "location_stats":
            return _parse_numeric_dict(self.space(), info)
        if self.kind == "equipped_items":
            equipped = info.get("equipped_items", {})
            return OrderedDict(
                [
                    ("mainhand", _equipped_stack(equipped.get("mainhand"))),
                    ("offhand", _equipped_stack(equipped.get("offhand"))),
                ]
            )
        return OrderedDict()


@dataclass(frozen=True, slots=True)
class InventoryRewardGroup:
    items: tuple[str, ...]
    reward: float
    amount: int = 1
    terminal: bool = False


@dataclass(frozen=True, slots=True)
class TaskSpec:
    id: str
    resolution: tuple[int, int]
    action_fields: tuple[ActionField, ...]
    observation_fields: tuple[ObservationField, ...]
    max_episode_steps: int | None = None
    reward_threshold: float | None = None
    world_generator: str = "default"
    world_generator_options: str = "{}"
    biome_id: int | None = None
    inventory: tuple[tuple[str, int], ...] = ()
    allow_time: bool = False
    allow_spawning: bool = True
    quit_items: tuple[tuple[str, int], ...] = ()
    quit_craft_items: tuple[tuple[str, int], ...] = ()
    quit_blocks: tuple[str, ...] = ()
    reward_items: tuple[tuple[str, int, float], ...] = ()
    reward_items_sparse: bool = False
    inventory_reward_groups: tuple[InventoryRewardGroup, ...] = ()
    time_up_description: str | None = None
    mission_end_rewards: tuple[tuple[str, float], ...] = ()
    reward_blocks: tuple[tuple[str, float], ...] = ()
    navigation_target: bool = False
    navigation_dense_reward: float | None = None
    preferred_spawn_biome: str | None = None
    spawn_in_village: bool = False
    done_on_death: bool = False
    esc_terminates: bool = False

    def action_space(self) -> gym.spaces.Dict:
        return gym.spaces.Dict(OrderedDict((field.name, field.space()) for field in self.action_fields))

    def observation_space(self) -> gym.spaces.Dict:
        return gym.spaces.Dict(
            OrderedDict((field.name, field.space()) for field in self.observation_fields)
        )

    def no_op_action(self) -> dict[str, Any]:
        return OrderedDict((field.name, field.no_op()) for field in self.action_fields)

    def empty_observation(self) -> dict[str, Any]:
        return OrderedDict((field.name, field.empty()) for field in self.observation_fields)

    def action_to_commands(self, action: Mapping[str, Any]) -> str:
        commands = []
        for field in self.action_fields:
            value = action.get(field.name, field.no_op())
            command = field.to_command(value)
            if command:
                commands.append(command)
        return "\n".join(commands)

    def observation_from_frame(self, frame: BackendFrame) -> tuple[dict[str, Any], dict[str, Any]]:
        info = _coerce_info(frame.info)
        obs = OrderedDict(
            (field.name, field.parse(frame.pov, info)) for field in self.observation_fields
        )
        monitor = {
            "raw_info": info,
            "backend_done": frame.done,
        }
        return obs, monitor

    def inventory_reward_from_observation(
        self,
        observation: Mapping[str, Any],
        seen_groups: set[int],
    ) -> tuple[float, bool]:
        inventory = observation.get("inventory", {})
        if not isinstance(inventory, Mapping):
            return 0.0, False

        reward = 0.0
        terminated = False
        for index, group in enumerate(self.inventory_reward_groups):
            if index in seen_groups:
                continue
            if any(_inventory_count(inventory, item) >= group.amount for item in group.items):
                seen_groups.add(index)
                reward += group.reward
                terminated = terminated or group.terminal
        return reward, terminated

    def to_mission_xml(self) -> str:
        from minerl.tasks.mission import render_mission

        return render_mission(self)


def _coerce_info(info: Mapping[str, Any] | str | None) -> dict[str, Any]:
    if info is None:
        return {}
    if isinstance(info, str):
        import json

        return json.loads(info) if info else {}
    return dict(info)


def _parse_pov(pov: bytes | np.ndarray | None, resolution: tuple[int, int]) -> np.ndarray:
    width, height = resolution
    if isinstance(pov, np.ndarray):
        arr = pov.astype(np.uint8, copy=False)
        if arr.shape == (height, width, 3):
            return arr
    if not pov:
        return np.zeros((height, width, 3), dtype=np.uint8)
    arr = np.frombuffer(pov, dtype=np.uint8)
    expected = height * width * 3
    if arr.size != expected:
        return np.zeros((height, width, 3), dtype=np.uint8)
    return arr.reshape((height, width, 3))[::-1, :, :]


def _parse_inventory(info: Mapping[str, Any], items: tuple[str, ...]) -> OrderedDict[str, np.ndarray]:
    out = OrderedDict((item, np.asarray(0, dtype=np.int32)) for item in sorted(items))
    for stack in info.get("inventory", []) or []:
        name = stack.get("type") or stack.get("name")
        if not name:
            continue
        name = _normalize_inventory_name(str(name).split(":")[-1])
        if name not in out:
            continue
        quantity = stack.get("quantity", stack.get("count", 1))
        out[name] = np.asarray(int(out[name]) + int(quantity), dtype=np.int32)
    return out


def _inventory_count(inventory: Mapping[str, Any], item: str) -> int:
    item = _normalize_inventory_name(item)
    value = inventory.get(item, 0)
    try:
        return int(np.asarray(value).item())
    except Exception:
        return int(value)


def _normalize_inventory_name(name: str) -> str:
    if name in WOOD_LOG_ITEMS:
        return "log"
    if name in WOOD_PLANK_ITEMS:
        return "planks"
    return name


def _parse_numeric_dict(space: gym.Space, info: Mapping[str, Any]) -> OrderedDict[str, np.ndarray]:
    assert isinstance(space, gym.spaces.Dict)
    out = OrderedDict()
    for key, child in space.spaces.items():
        value = info.get(key, zero_value(child))
        out[key] = np.asarray(value, dtype=getattr(child, "dtype", np.float32))
    return out


def _equipped_stack(value: Any) -> OrderedDict[str, Any]:
    decoded = _decode_equipped(value)
    return OrderedDict(
        [
            ("type", _equipped_name(decoded)),
            ("damage", np.asarray(_equipped_int(decoded, "damage", -1), dtype=np.int32)),
            ("max_damage", np.asarray(_equipped_int(decoded, "maxDamage", -1), dtype=np.int32)),
        ]
    )


def _decode_equipped(value: Any) -> Any:
    if isinstance(value, str) and value.startswith("{"):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value
    return value


def _equipped_name(value: Any) -> str:
    if isinstance(value, Mapping):
        return str(value.get("type") or value.get("name") or "air").split(":")[-1]
    if isinstance(value, str):
        return value.split(":")[-1]
    return "air"


def _equipped_int(value: Any, key: str, default: int) -> int:
    if isinstance(value, Mapping):
        snake_key = "max_damage" if key == "maxDamage" else key
        raw = value.get(key, value.get(snake_key, default))
        try:
            return int(raw)
        except (TypeError, ValueError):
            return default
    return default
