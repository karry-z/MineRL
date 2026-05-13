from __future__ import annotations

MS_PER_STEP = 50

SIMPLE_ACTIONS = (
    "forward",
    "back",
    "left",
    "right",
    "jump",
    "sneak",
    "sprint",
    "attack",
)

HUMAN_ACTIONS = (
    "ESC",
    "attack",
    "back",
    "drop",
    "forward",
    "hotbar.1",
    "hotbar.2",
    "hotbar.3",
    "hotbar.4",
    "hotbar.5",
    "hotbar.6",
    "hotbar.7",
    "hotbar.8",
    "hotbar.9",
    "inventory",
    "jump",
    "left",
    "pickItem",
    "right",
    "sneak",
    "sprint",
    "swapHands",
    "use",
)

COMMON_ITEMS = (
    "air",
    "coal",
    "cobblestone",
    "crafting_table",
    "diamond",
    "diamond_shovel",
    "dirt",
    "furnace",
    "iron_axe",
    "iron_ingot",
    "iron_ore",
    "iron_pickaxe",
    "log",
    "planks",
    "stick",
    "stone",
    "stone_axe",
    "stone_pickaxe",
    "torch",
    "wooden_axe",
    "wooden_pickaxe",
)

OBTAIN_ITEMS = (
    "coal",
    "cobblestone",
    "crafting_table",
    "diamond",
    "diamond_shovel",
    "dirt",
    "furnace",
    "iron_axe",
    "iron_ingot",
    "iron_ore",
    "iron_pickaxe",
    "log",
    "planks",
    "stick",
    "stone",
    "stone_axe",
    "stone_pickaxe",
    "torch",
    "wooden_axe",
    "wooden_pickaxe",
)

WOOD_LOG_ITEMS = (
    "log",
    "log2",
    "acacia_log",
    "birch_log",
    "dark_oak_log",
    "jungle_log",
    "oak_log",
    "spruce_log",
)

WOOD_PLANK_ITEMS = (
    "planks",
    "acacia_planks",
    "birch_planks",
    "dark_oak_planks",
    "jungle_planks",
    "oak_planks",
    "spruce_planks",
)

OBTAIN_IRON_REWARDS = (
    ("log", 1, 1.0),
    ("planks", 1, 2.0),
    ("stick", 1, 4.0),
    ("crafting_table", 1, 4.0),
    ("wooden_pickaxe", 1, 8.0),
    ("cobblestone", 1, 16.0),
    ("furnace", 1, 32.0),
    ("stone_pickaxe", 1, 32.0),
    ("iron_ore", 1, 64.0),
    ("iron_ingot", 1, 128.0),
    ("iron_pickaxe", 1, 256.0),
)

OBTAIN_DIAMOND_REWARDS = OBTAIN_IRON_REWARDS + (
    ("diamond", 1, 1024.0),
)

OBTAIN_DIAMOND_SHOVEL_REWARDS = OBTAIN_DIAMOND_REWARDS + (
    ("diamond_shovel", 1, 2048.0),
)

TREECHOP_WORLD_GENERATOR_OPTIONS = (
    '{"coordinateScale":684.412,"heightScale":684.412,"lowerLimitScale":512.0,'
    '"upperLimitScale":512.0,"depthNoiseScaleX":200.0,"depthNoiseScaleZ":200.0,'
    '"depthNoiseScaleExponent":0.5,"mainNoiseScaleX":80.0,"mainNoiseScaleY":160.0,'
    '"mainNoiseScaleZ":80.0,"baseSize":8.5,"stretchY":12.0,"biomeDepthWeight":1.0,'
    '"biomeDepthOffset":0.0,"biomeScaleWeight":1.0,"biomeScaleOffset":0.0,'
    '"seaLevel":1,"useCaves":false,"useDungeons":false,"dungeonChance":8,'
    '"useStrongholds":false,"useVillages":false,"useMineShafts":false,'
    '"useTemples":false,"useMonuments":false,"useMansions":false,"useRavines":false,'
    '"useWaterLakes":false,"waterLakeChance":4,"useLavaLakes":false,'
    '"lavaLakeChance":80,"useLavaOceans":false,"fixedBiome":4,"biomeSize":4,'
    '"riverSize":1,"dirtSize":33,"dirtCount":10,"dirtMinHeight":0,'
    '"dirtMaxHeight":256,"gravelSize":33,"gravelCount":8,"gravelMinHeight":0,'
    '"gravelMaxHeight":256,"graniteSize":33,"graniteCount":10,"graniteMinHeight":0,'
    '"graniteMaxHeight":80,"dioriteSize":33,"dioriteCount":10,"dioriteMinHeight":0,'
    '"dioriteMaxHeight":80,"andesiteSize":33,"andesiteCount":10,'
    '"andesiteMinHeight":0,"andesiteMaxHeight":80,"coalSize":17,"coalCount":20,'
    '"coalMinHeight":0,"coalMaxHeight":128,"ironSize":9,"ironCount":20,'
    '"ironMinHeight":0,"ironMaxHeight":64,"goldSize":9,"goldCount":2,'
    '"goldMinHeight":0,"goldMaxHeight":32,"redstoneSize":8,"redstoneCount":8,'
    '"redstoneMinHeight":0,"redstoneMaxHeight":16,"diamondSize":8,"diamondCount":1,'
    '"diamondMinHeight":0,"diamondMaxHeight":16,"lapisSize":7,"lapisCount":1,'
    '"lapisCenterHeight":16,"lapisSpread":16}'
)
