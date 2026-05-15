from __future__ import annotations

from pathlib import Path

from lxml import etree
import numpy as np

from minerl.runtime.backend import BackendFrame
from minerl.tasks.catalog import get_task


def test_mission_xml_is_structured_and_parseable() -> None:
    task = get_task("MineRLNavigate-v0")
    xml = task.to_mission_xml()
    root = etree.fromstring(xml.encode("utf-8"))
    rendered = etree.tostring(root)
    assert root.tag.endswith("Mission")
    assert b"NavigationDecorator" in rendered
    assert b"randomPlacementProperties" in rendered
    assert b"targetBlock" not in rendered
    assert b"LowLevelInputsAgentStart" not in rendered
    assert b"<LowLevelInputs>true</LowLevelInputs>" in rendered
    assert b"InventoryObject" in rendered
    assert b"PlaceCommands" in rendered
    assert b"HumanLevelCommands" in rendered
    assert b"CameraCommands" in rendered


def test_task_specific_mission_handlers_are_rendered() -> None:
    dense_nav_xml = get_task("MineRLNavigateDense-v0").to_mission_xml()
    assert "RewardForDistanceTraveledToCompassTarget" in dense_nav_xml

    equip_xml = get_task("MineRLEquipWeapon-v0").to_mission_xml()
    assert 'InventoryObject slot="0" type="iron_axe" quantity="1"' in equip_xml
    assert "ObservationFromEquippedItem" in equip_xml

    basalt_xml = get_task("MineRLBasaltCreateVillageAnimalPen-v0").to_mission_xml()
    assert "<PreferredSpawnBiome>plains</PreferredSpawnBiome>" in basalt_xml
    assert "<SpawnInVillage>true</SpawnInVillage>" in basalt_xml
    assert "<DoneOnDeath>true</DoneOnDeath>" in basalt_xml
    assert 'type="fence"' in basalt_xml

    diamond_shovel_xml = get_task("MineRLObtainDiamondShovel-v0").to_mission_xml()
    assert '<ServerQuitFromTimeUp timeLimitMs="900000" description="out_of_time"/>' in (
        diamond_shovel_xml
    )
    assert "<RewardForMissionEnd>" in diamond_shovel_xml
    assert "<SimpleCraftCommands/>" not in diamond_shovel_xml


def test_representative_missions_validate_against_malmo_xsd() -> None:
    schema = etree.XMLSchema(
        etree.parse(str(Path("src/minerl/assets/Malmo/Schemas/Mission.xsd")))
    )
    for task_id in (
        "MineRLTreechop-v0",
        "MineRLNavigate-v0",
        "MineRLNavigateDense-v0",
        "MineRLEquipWeapon-v0",
        "MineRLObtainIronPickaxe-v0",
        "MineRLObtainIronPickaxeDense-v0",
        "MineRLObtainDiamond-v0",
        "MineRLObtainDiamondDense-v0",
        "MineRLObtainDiamondShovel-v0",
        "MineRLBasaltCreateVillageAnimalPen-v0",
        "MineRLBasaltBuildVillageHouse-v0",
    ):
        doc = etree.fromstring(get_task(task_id).to_mission_xml().encode("utf-8"))
        assert schema.validate(doc), schema.error_log.last_error


def test_action_translation_is_line_based_malmo_commands() -> None:
    task = get_task("MineRLBasaltFindCave-v0")
    action = task.no_op_action()
    action["forward"] = 1
    action["camera"] = np.asarray([1.5, -2.0], dtype=np.float32)
    commands = task.action_to_commands(action)
    assert "forward 1" in commands.splitlines()
    assert "camera 1.5 -2.0" in commands.splitlines()


def test_enum_action_translation_accepts_index_and_string() -> None:
    task = get_task("MineRLNavigate-v0")
    action = task.no_op_action()
    assert action["place"] == 0
    assert not any(line.startswith("place ") for line in task.action_to_commands(action).splitlines())

    action["place"] = 1
    assert "place dirt" in task.action_to_commands(action).splitlines()

    action["place"] = "dirt"
    assert "place dirt" in task.action_to_commands(action).splitlines()


def test_obtain_tasks_render_gui_free_action_and_reward_handlers() -> None:
    sparse_xml = get_task("MineRLObtainIronPickaxe-v0").to_mission_xml()
    assert "<SimpleCraftCommands/>" in sparse_xml
    assert "<NearbyCraftCommands/>" in sparse_xml
    assert "<NearbySmeltCommands/>" in sparse_xml
    assert "<EquipCommands/>" in sparse_xml
    assert '<RewardForPossessingItem sparse="true" excludeLoops="true">' in sparse_xml
    assert '<Item type="iron_pickaxe" amount="1" reward="256.0"/>' in sparse_xml
    assert "<AgentQuitFromCraftingItem>" in sparse_xml
    assert '<Reward description="out_of_time" reward="0.0"/>' in sparse_xml

    dense_xml = get_task("MineRLObtainDiamondDense-v0").to_mission_xml()
    assert '<RewardForPossessingItem sparse="false" excludeLoops="true">' in dense_xml
    assert '<Item type="diamond" amount="1" reward="1024.0"/>' in dense_xml
    assert "<AgentQuitFromPossessingItem>" in dense_xml


def test_obtain_action_translation_uses_malmo_command_names() -> None:
    task = get_task("MineRLObtainIronPickaxe-v0")
    action = task.no_op_action()
    assert not any(
        line.startswith(("place ", "equip ", "craft ", "craftNearby ", "smeltNearby "))
        for line in task.action_to_commands(action).splitlines()
    )

    action["craft"] = "planks"
    action["nearbyCraft"] = "stone_pickaxe"
    action["nearbySmelt"] = "iron_ingot"
    action["equip"] = "stone_pickaxe"
    lines = task.action_to_commands(action).splitlines()
    assert "craft planks" in lines
    assert "craftNearby stone_pickaxe" in lines
    assert "smeltNearby iron_ingot" in lines
    assert "equip stone_pickaxe" in lines


def test_observation_parser_handles_bytes_and_inventory() -> None:
    task = get_task("MineRLTreechop-v0")
    pov = np.arange(64 * 64 * 3, dtype=np.uint8).tobytes()
    frame = BackendFrame(
        pov=pov,
        info={"inventory": [{"type": "log", "quantity": 3}]},
        reward=1.0,
        done=False,
    )
    obs, info = task.observation_from_frame(frame)
    assert obs["pov"].shape == (64, 64, 3)
    assert info["backend_done"] is False

    nav = get_task("MineRLNavigate-v0")
    obs, _ = nav.observation_from_frame(frame)
    assert int(obs["inventory"]["dirt"]) == 0

    obtain = get_task("MineRLObtainDiamondShovel-v0")
    obs, _ = obtain.observation_from_frame(
        BackendFrame(
            pov=None,
            info={
                "inventory": [
                    {"type": "minecraft:oak_log", "quantity": 2},
                    {"type": "minecraft:birch_planks", "quantity": 3},
                ]
            },
            reward=0.0,
            done=False,
        )
    )
    assert int(obs["inventory"]["log"]) == 2
    assert int(obs["inventory"]["planks"]) == 3


def test_diamond_shovel_task_uses_human_resolution_and_python_reward_groups() -> None:
    task = get_task("MineRLObtainDiamondShovel-v0")
    assert "craft" not in task.action_space().spaces
    assert task.observation_space().spaces["pov"].shape == (360, 640, 3)
    assert len(task.inventory_reward_groups) == 13
    assert task.inventory_reward_groups[-1].terminal is True


def test_equipped_item_parser_handles_malmo_json_strings() -> None:
    task = get_task("MineRLEquipWeapon-v0")
    frame = BackendFrame(
        pov=None,
        info={
            "equipped_items": {
                "mainhand": '{"type":"minecraft:iron_axe","maxDamage":250,"damage":0}',
                "offhand": '{"type":"minecraft:air","maxDamage":0,"damage":0}',
            }
        },
        reward=0.0,
        done=False,
    )
    obs, _ = task.observation_from_frame(frame)
    assert obs["equipped_items"]["mainhand"]["type"] == "iron_axe"
    assert int(obs["equipped_items"]["mainhand"]["damage"]) == 0
    assert int(obs["equipped_items"]["mainhand"]["max_damage"]) == 250
    assert task.observation_space().contains(obs)
