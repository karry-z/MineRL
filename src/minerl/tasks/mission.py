from __future__ import annotations

from html import escape

from jinja2 import Environment

from minerl.tasks.constants import MS_PER_STEP
from minerl.tasks.schema import TaskSpec

MISSION_TEMPLATE = Environment(autoescape=False, trim_blocks=True, lstrip_blocks=True).from_string(
    """<?xml version="1.0" encoding="UTF-8" standalone="no" ?>
<Mission xmlns="http://ProjectMalmo.microsoft.com">
  <About>
    <Summary>{{ task.id }}</Summary>
  </About>
  <ModSettings>
    <MsPerTick>{{ ms_per_step }}</MsPerTick>
  </ModSettings>
  <ServerSection>
    <ServerInitialConditions>
      <Time><StartTime>{{ 6000 if task.allow_time else 0 }}</StartTime><AllowPassageOfTime>{{ bool_text(task.allow_time) }}</AllowPassageOfTime></Time>
      <AllowSpawning>{{ bool_text(task.allow_spawning) }}</AllowSpawning>
    </ServerInitialConditions>
    <ServerHandlers>
      {{ world_generator(task) }}
      {% if task.navigation_target %}
      <NavigationDecorator>
        <randomPlacementProperties>
          <maxRandomizedRadius>64</maxRandomizedRadius>
          <minRandomizedRadius>64</minRandomizedRadius>
          <maxRadius>8</maxRadius>
          <minRadius>0</minRadius>
          <block>diamond_block</block>
          <placement>surface</placement>
        </randomPlacementProperties>
        <minRandomizedDistance>0</minRandomizedDistance>
        <maxRandomizedDistance>8</maxRandomizedDistance>
        <randomizeCompassLocation>true</randomizeCompassLocation>
      </NavigationDecorator>
      {% endif %}
      {% if task.max_episode_steps %}
      <ServerQuitFromTimeUp timeLimitMs="{{ task.max_episode_steps * ms_per_step }}"{{ description_attr(task.time_up_description) }}/>
      {% endif %}
      <ServerQuitWhenAnyAgentFinishes/>
    </ServerHandlers>
  </ServerSection>
  <AgentSection mode="Survival">
    <Name>MineRLAgent0</Name>
    <AgentStart>
      {% if task.preferred_spawn_biome %}
      <PreferredSpawnBiome>{{ task.preferred_spawn_biome }}</PreferredSpawnBiome>
      {% endif %}
      {% if task.spawn_in_village %}
      <SpawnInVillage>true</SpawnInVillage>
      {% endif %}
      {% if task.done_on_death %}
      <DoneOnDeath>true</DoneOnDeath>
      {% endif %}
      <LowLevelInputs>true</LowLevelInputs>
      <GuiScale>1</GuiScale>
      <GammaSetting>2</GammaSetting>
      <FOVSetting>70</FOVSetting>
      <FakeCursorSize>16</FakeCursorSize>
      {% if task.inventory %}
      <Inventory>
      {% for name, quantity in task.inventory %}
        <InventoryObject slot="{{ loop.index0 }}" type="{{ name }}" quantity="{{ quantity }}"/>
      {% endfor %}
      </Inventory>
      {% endif %}
    </AgentStart>
    <AgentHandlers>
      <FileBasedPerformanceProducer/>
      <PauseCommand/>
      <VideoProducer want_depth="false">
        <Width>{{ task.resolution[0] }}</Width>
        <Height>{{ task.resolution[1] }}</Height>
      </VideoProducer>
      {{ observation_handlers(task) }}
      {{ action_handlers(task) }}
      {{ reward_handlers(task) }}
      {{ quit_handlers(task) }}
    </AgentHandlers>
  </AgentSection>
</Mission>
"""
)


def render_mission(task: TaskSpec) -> str:
    return MISSION_TEMPLATE.render(
        task=task,
        ms_per_step=MS_PER_STEP,
        bool_text=_bool_text,
        world_generator=_world_generator,
        description_attr=_description_attr,
        observation_handlers=_observation_handlers,
        action_handlers=_action_handlers,
        reward_handlers=_reward_handlers,
        quit_handlers=_quit_handlers,
    )


def _bool_text(value: bool) -> str:
    return "true" if value else "false"


def _world_generator(task: TaskSpec) -> str:
    if task.world_generator == "biome":
        biome_id = 3 if task.biome_id is None else task.biome_id
        return f'<BiomeGenerator forceReset="true" biome="{biome_id}"/>'
    options = escape(task.world_generator_options, quote=True)
    return f'<DefaultWorldGenerator forceReset="true" generatorOptions="{options}"/>'


def _description_attr(description: str | None) -> str:
    if not description:
        return ""
    return f' description="{escape(description, quote=True)}"'


def _observation_handlers(task: TaskSpec) -> str:
    tags = {"<ObservationFromFullStats/>"}
    if any(field.kind == "inventory" for field in task.observation_fields):
        tags.add('<ObservationFromFullInventory flat="false"/>')
    if any(field.kind == "compass" for field in task.observation_fields):
        tags.add("<ObservationFromCompass/>")
    if any(field.kind == "equipped_items" for field in task.observation_fields):
        tags.add("<ObservationFromEquippedItem/>")
    return "\n      ".join(sorted(tags))


def _action_handlers(task: TaskSpec) -> str:
    has_camera = any(field.kind == "camera" for field in task.action_fields)
    commands = {field.command or field.name for field in task.action_fields}
    tags = ["<HumanLevelCommands/>"]
    if "craft" in commands:
        tags.append("<SimpleCraftCommands/>")
    if "craftNearby" in commands:
        tags.append("<NearbyCraftCommands/>")
    if "smeltNearby" in commands:
        tags.append("<NearbySmeltCommands/>")
    if "place" in commands:
        tags.append("<PlaceCommands/>")
    if "equip" in commands:
        tags.append("<EquipCommands/>")
    if has_camera:
        tags.append("<CameraCommands/>")
    return "\n      ".join(tags)


def _reward_handlers(task: TaskSpec) -> str:
    parts = []
    if task.mission_end_rewards:
        rewards = "".join(
            f'<Reward description="{escape(description, quote=True)}" reward="{reward}"/>'
            for description, reward in task.mission_end_rewards
        )
        parts.append(f"<RewardForMissionEnd>{rewards}</RewardForMissionEnd>")
    if task.reward_items:
        items = "".join(
            f'<Item type="{name}" amount="{amount}" reward="{reward}"/>'
            for name, amount, reward in task.reward_items
        )
        parts.append(
            f'<RewardForPossessingItem sparse="{_bool_text(task.reward_items_sparse)}" '
            'excludeLoops="true">'
            f"{items}</RewardForPossessingItem>"
        )
    if task.reward_blocks:
        blocks = "".join(
            f'<Block type="{name}" behaviour="onceOnly" reward="{reward}"/>'
            for name, reward in task.reward_blocks
        )
        parts.append(f"<RewardForTouchingBlockType>{blocks}</RewardForTouchingBlockType>")
    if task.navigation_dense_reward is not None:
        parts.append(
            "<RewardForDistanceTraveledToCompassTarget "
            f'rewardPerBlock="{task.navigation_dense_reward}" density="PER_TICK"/>'
        )
    return "\n      ".join(parts)


def _quit_handlers(task: TaskSpec) -> str:
    parts = []
    if task.quit_items:
        items = "".join(
            f'<Item type="{name}" amount="{amount}"/>' for name, amount in task.quit_items
        )
        parts.append(f"<AgentQuitFromPossessingItem>{items}</AgentQuitFromPossessingItem>")
    if task.quit_craft_items:
        items = "".join(
            f'<Item type="{name}" amount="{amount}"/>' for name, amount in task.quit_craft_items
        )
        parts.append(f"<AgentQuitFromCraftingItem>{items}</AgentQuitFromCraftingItem>")
    if task.quit_blocks:
        blocks = "".join(f'<Block type="{name}"/>' for name in task.quit_blocks)
        parts.append(f"<AgentQuitFromTouchingBlockType>{blocks}</AgentQuitFromTouchingBlockType>")
    return "\n      ".join(parts)
