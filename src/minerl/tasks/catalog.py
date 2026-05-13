from __future__ import annotations

from collections import OrderedDict

from minerl.tasks.constants import (
    COMMON_ITEMS,
    HUMAN_ACTIONS,
    OBTAIN_DIAMOND_REWARDS,
    OBTAIN_DIAMOND_SHOVEL_REWARDS,
    OBTAIN_IRON_REWARDS,
    OBTAIN_ITEMS,
    SIMPLE_ACTIONS,
    TREECHOP_WORLD_GENERATOR_OPTIONS,
    WOOD_LOG_ITEMS,
    WOOD_PLANK_ITEMS,
)
from minerl.tasks.schema import ActionField, InventoryRewardGroup, ObservationField, TaskSpec


def list_task_specs() -> tuple[TaskSpec, ...]:
    return tuple(_TASKS.values())


def list_tasks() -> tuple[str, ...]:
    return tuple(_TASKS)


def get_task(task_id: str) -> TaskSpec:
    try:
        return _TASKS[task_id]
    except KeyError as exc:
        known = ", ".join(sorted(_TASKS))
        raise KeyError(f"Unknown MineRL task {task_id!r}. Known tasks: {known}") from exc


def _actions(names: tuple[str, ...]) -> tuple[ActionField, ...]:
    return tuple(ActionField(name=name) for name in names) + (
        ActionField(name="camera", kind="camera"),
    )


def _navigate_actions() -> tuple[ActionField, ...]:
    return tuple(ActionField(name=name) for name in SIMPLE_ACTIONS) + (
        ActionField(name="place", kind="enum", options=("none", "dirt")),
        ActionField(name="camera", kind="camera"),
    )


def _obtain_actions(
    *,
    extra_nearby_craft: tuple[str, ...] = (),
) -> tuple[ActionField, ...]:
    return tuple(ActionField(name=name) for name in SIMPLE_ACTIONS) + (
        ActionField(name="camera", kind="camera"),
        ActionField(
            name="place",
            kind="enum",
            options=("none", "dirt", "stone", "cobblestone", "crafting_table", "furnace", "torch"),
        ),
        ActionField(
            name="equip",
            kind="enum",
            options=(
                "none",
                "air",
                "wooden_axe",
                "wooden_pickaxe",
                "stone_axe",
                "stone_pickaxe",
                "iron_axe",
                "iron_pickaxe",
            ),
        ),
        ActionField(
            name="craft",
            command="craft",
            kind="enum",
            options=("none", "torch", "stick", "planks", "crafting_table"),
        ),
        ActionField(
            name="nearbyCraft",
            command="craftNearby",
            kind="enum",
            options=(
                "none",
                "wooden_axe",
                "wooden_pickaxe",
                "stone_axe",
                "stone_pickaxe",
                "iron_axe",
                "iron_pickaxe",
                "furnace",
                *extra_nearby_craft,
            ),
        ),
        ActionField(
            name="nearbySmelt",
            command="smeltNearby",
            kind="enum",
            options=("none", "iron_ingot", "coal"),
        ),
    )


def _pov(resolution: tuple[int, int]) -> ObservationField:
    return ObservationField("pov", "pov", resolution=resolution)


def _inventory(items: tuple[str, ...] = COMMON_ITEMS) -> ObservationField:
    return ObservationField("inventory", "inventory", items=items)


def _simple_task(
    task_id: str,
    *,
    max_episode_steps: int,
    world_generator: str = "default",
    world_generator_options: str = "{}",
    biome_id: int | None = None,
    inventory: tuple[tuple[str, int], ...] = (),
    quit_items: tuple[tuple[str, int], ...] = (),
    quit_craft_items: tuple[tuple[str, int], ...] = (),
    quit_blocks: tuple[str, ...] = (),
    reward_items: tuple[tuple[str, int, float], ...] = (),
    reward_items_sparse: bool = False,
    reward_blocks: tuple[tuple[str, float], ...] = (),
    navigation_target: bool = False,
    navigation_dense_reward: float | None = None,
) -> TaskSpec:
    observations = [_pov((64, 64))]
    if navigation_target:
        observations += [ObservationField("compass", "compass"), _inventory(("dirt",))]
    return TaskSpec(
        id=task_id,
        resolution=(64, 64),
        action_fields=_navigate_actions() if navigation_target else _actions(SIMPLE_ACTIONS),
        observation_fields=tuple(observations),
        max_episode_steps=max_episode_steps,
        world_generator=world_generator,
        world_generator_options=world_generator_options,
        biome_id=biome_id,
        inventory=inventory,
        quit_items=quit_items,
        quit_craft_items=quit_craft_items,
        quit_blocks=quit_blocks,
        reward_items=reward_items,
        reward_items_sparse=reward_items_sparse,
        reward_blocks=reward_blocks,
        navigation_target=navigation_target,
        navigation_dense_reward=navigation_dense_reward,
    )


def _human_task(
    task_id: str,
    *,
    max_episode_steps: int | None = None,
    inventory: tuple[tuple[str, int], ...] = (),
) -> TaskSpec:
    return TaskSpec(
        id=task_id,
        resolution=(640, 360),
        action_fields=_actions(HUMAN_ACTIONS),
        observation_fields=(
            _pov((640, 360)),
            _inventory(),
            ObservationField("equipped_items", "equipped_items"),
            ObservationField("life_stats", "life_stats"),
            ObservationField("location_stats", "location_stats"),
        ),
        max_episode_steps=max_episode_steps,
        allow_time=True,
        allow_spawning=True,
        inventory=inventory,
    )


def _obtain_task(
    task_id: str,
    *,
    max_episode_steps: int,
    reward_items: tuple[tuple[str, int, float], ...],
    reward_items_sparse: bool,
    quit_items: tuple[tuple[str, int], ...] = (),
    quit_craft_items: tuple[tuple[str, int], ...] = (),
    extra_nearby_craft: tuple[str, ...] = (),
) -> TaskSpec:
    return TaskSpec(
        id=task_id,
        resolution=(64, 64),
        action_fields=_obtain_actions(extra_nearby_craft=extra_nearby_craft),
        observation_fields=(
            _pov((64, 64)),
            _inventory(OBTAIN_ITEMS),
            ObservationField("equipped_items", "equipped_items"),
        ),
        max_episode_steps=max_episode_steps,
        quit_items=quit_items,
        quit_craft_items=quit_craft_items,
        reward_items=reward_items,
        reward_items_sparse=reward_items_sparse,
        time_up_description="out_of_time",
        mission_end_rewards=(("out_of_time", 0.0),),
        allow_time=True,
        allow_spawning=True,
    )


def _diamond_shovel_task() -> TaskSpec:
    reward_groups = (
        InventoryRewardGroup(WOOD_LOG_ITEMS, 1.0),
        InventoryRewardGroup(WOOD_PLANK_ITEMS, 2.0),
        *(
            InventoryRewardGroup((name,), reward, terminal=(name == "diamond_shovel"))
            for name, _, reward in OBTAIN_DIAMOND_SHOVEL_REWARDS[2:]
        ),
    )
    return TaskSpec(
        id="MineRLObtainDiamondShovel-v0",
        resolution=(640, 360),
        action_fields=_actions(HUMAN_ACTIONS),
        observation_fields=(
            _pov((640, 360)),
            _inventory(OBTAIN_ITEMS),
            ObservationField("equipped_items", "equipped_items"),
            ObservationField("life_stats", "life_stats"),
            ObservationField("location_stats", "location_stats"),
        ),
        max_episode_steps=18000,
        quit_items=(("diamond_shovel", 1),),
        inventory_reward_groups=reward_groups,
        time_up_description="out_of_time",
        mission_end_rewards=(("out_of_time", 0.0),),
        allow_time=True,
        allow_spawning=True,
    )


def _basalt_task(
    task_id: str,
    *,
    max_episode_steps: int,
    inventory: tuple[tuple[str, int], ...] = (),
    preferred_spawn_biome: str = "plains",
    spawn_in_village: bool = False,
) -> TaskSpec:
    return TaskSpec(
        id=task_id,
        resolution=(640, 360),
        action_fields=_actions(HUMAN_ACTIONS),
        observation_fields=(_pov((640, 360)),),
        max_episode_steps=max_episode_steps,
        inventory=inventory,
        allow_time=False,
        allow_spawning=True,
        preferred_spawn_biome=preferred_spawn_biome,
        spawn_in_village=spawn_in_village,
        done_on_death=True,
        esc_terminates=True,
    )


MAKE_HOUSE_VILLAGE_INVENTORY = (
    ("stone_pickaxe", 1),
    ("stone_axe", 1),
    ("cobblestone", 64),
    ("log", 64),
    ("glass_pane", 64),
    ("torch", 64),
    ("dirt", 64),
    ("grass", 64),
    ("red_flower", 64),
    ("log", 64),
    ("log2", 64),
    ("log2", 64),
    ("sand", 64),
    ("sandstone", 64),
    ("sandstone", 64),
    ("hardened_clay", 64),
    ("packed_ice", 64),
    ("snow", 64),
    ("web", 64),
    ("wool", 64),
    ("dye", 64),
    ("dye", 64),
    ("dye", 64),
    ("dye", 64),
    ("dye", 64),
    ("dye", 64),
    ("dye", 64),
    ("flower_pot", 64),
    ("cactus", 64),
    ("torch", 64),
)


_TASK_LIST = [
    _simple_task(
        "MineRLTreechop-v0",
        max_episode_steps=8000,
        world_generator_options=TREECHOP_WORLD_GENERATOR_OPTIONS,
        inventory=(("iron_axe", 1),),
        quit_items=(("log", 64),),
        reward_items=(("log", 1, 1.0),),
    ),
    _simple_task(
        "MineRLNavigate-v0",
        max_episode_steps=6000,
        inventory=(("compass", 1),),
        quit_blocks=("diamond_block",),
        reward_blocks=(("diamond_block", 100.0),),
        navigation_target=True,
    ),
    _simple_task(
        "MineRLNavigateDense-v0",
        max_episode_steps=6000,
        inventory=(("compass", 1),),
        quit_blocks=("diamond_block",),
        reward_blocks=(("diamond_block", 100.0),),
        navigation_target=True,
        navigation_dense_reward=1.0,
    ),
    _simple_task(
        "MineRLNavigateExtreme-v0",
        max_episode_steps=6000,
        world_generator="biome",
        biome_id=3,
        inventory=(("compass", 1),),
        quit_blocks=("diamond_block",),
        reward_blocks=(("diamond_block", 100.0),),
        navigation_target=True,
    ),
    _simple_task(
        "MineRLNavigateExtremeDense-v0",
        max_episode_steps=6000,
        world_generator="biome",
        biome_id=3,
        inventory=(("compass", 1),),
        quit_blocks=("diamond_block",),
        reward_blocks=(("diamond_block", 100.0),),
        navigation_target=True,
        navigation_dense_reward=1.0,
    ),
    _human_task("MineRLHumanSurvival-v0"),
    _human_task("MineRLEquipWeapon-v0", max_episode_steps=1200, inventory=(("iron_axe", 1),)),
    _diamond_shovel_task(),
    _obtain_task(
        "MineRLObtainIronPickaxe-v0",
        max_episode_steps=6000,
        reward_items=OBTAIN_IRON_REWARDS,
        reward_items_sparse=True,
        quit_craft_items=(("iron_pickaxe", 1),),
    ),
    _obtain_task(
        "MineRLObtainIronPickaxeDense-v0",
        max_episode_steps=6000,
        reward_items=OBTAIN_IRON_REWARDS,
        reward_items_sparse=False,
        quit_craft_items=(("iron_pickaxe", 1),),
    ),
    _obtain_task(
        "MineRLObtainDiamond-v0",
        max_episode_steps=18000,
        reward_items=OBTAIN_DIAMOND_REWARDS,
        reward_items_sparse=True,
        quit_items=(("diamond", 1),),
    ),
    _obtain_task(
        "MineRLObtainDiamondDense-v0",
        max_episode_steps=18000,
        reward_items=OBTAIN_DIAMOND_REWARDS,
        reward_items_sparse=False,
        quit_items=(("diamond", 1),),
    ),
    _basalt_task("MineRLBasaltFindCave-v0", max_episode_steps=3600),
    _basalt_task(
        "MineRLBasaltMakeWaterfall-v0",
        max_episode_steps=6000,
        preferred_spawn_biome="extreme_hills",
        inventory=(
            ("water_bucket", 1),
            ("cobblestone", 20),
            ("stone_shovel", 1),
            ("stone_pickaxe", 1),
        ),
    ),
    _basalt_task(
        "MineRLBasaltCreateVillageAnimalPen-v0",
        max_episode_steps=6000,
        inventory=(
            ("fence", 64),
            ("fence_gate", 64),
            ("carrot", 1),
            ("wheat_seeds", 1),
            ("wheat", 1),
        ),
        spawn_in_village=True,
    ),
    _basalt_task(
        "MineRLBasaltBuildVillageHouse-v0",
        max_episode_steps=14400,
        inventory=MAKE_HOUSE_VILLAGE_INVENTORY,
        spawn_in_village=True,
    ),
]

_TASKS: OrderedDict[str, TaskSpec] = OrderedDict((task.id, task) for task in _TASK_LIST)
