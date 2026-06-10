"""
物品分类规则引擎。

分类基于创造模式物品栏标签页：
- building: 建筑方块
- dyed: 染色方块
- natural: 自然方块
- functional: 功能方块
- redstone: 红石方块
- tool: 工具与实用物品
- combat: 战斗用品
- food: 食物与饮品
- material: 原材料
- spawn_egg: 刷怪蛋
- admin: 管理员用品
"""

import re
from typing import Optional

# ============================================================
# 硬编码精确映射表（最高优先级）
# 用于覆盖ID模式匹配无法正确处理或有歧义的物品
# ============================================================
EXACT_CATEGORY_MAP: dict[str, str] = {
    # --- 工具与实用物品 ---
    "bow": "tool",
    "crossbow": "tool",
    "trident": "combat",
    "mace": "combat",
    "shield": "combat",
    "fishing_rod": "tool",
    "carrot_on_a_stick": "tool",
    "warped_fungus_on_a_stick": "tool",
    "shears": "tool",
    "flint_and_steel": "tool",
    "brush": "tool",
    "spyglass": "tool",
    "clock": "tool",
    "compass": "tool",
    "recovery_compass": "tool",
    "map": "tool",
    "filled_map": "tool",
    "glass_bottle": "tool",
    "bucket": "tool",
    "water_bucket": "tool",
    "lava_bucket": "tool",
    "milk_bucket": "tool",
    "powder_snow_bucket": "tool",
    "cod_bucket": "tool",
    "salmon_bucket": "tool",
    "pufferfish_bucket": "tool",
    "tropical_fish_bucket": "tool",
    "axolotl_bucket": "tool",
    "tadpole_bucket": "tool",
    "saddle": "tool",
    "lead": "tool",
    "name_tag": "tool",
    "writable_book": "tool",
    "written_book": "tool",
    "book": "material",
    "knowledge_book": "admin",
    "bundle": "tool",
    "snowball": "tool",
    "egg": "tool",
    "blue_egg": "tool",
    "brown_egg": "tool",
    "ender_pearl": "tool",
    "ender_eye": "tool",
    "firework_rocket": "tool",
    "firework_star": "material",
    "elytra": "tool",
    "wind_charge": "tool",
    "goat_horn": "tool",
    "painting": "tool",
    "item_frame": "tool",
    "glow_item_frame": "tool",
    "armor_stand": "tool",
    "saddle": "tool",
    "minecart": "tool",
    "chest_minecart": "tool",
    "furnace_minecart": "tool",
    "hopper_minecart": "tool",
    "tnt_minecart": "tool",
    "command_block_minecart": "tool",

    # --- 船/竹筏 ---
    "oak_boat": "tool",
    "oak_chest_boat": "tool",
    "spruce_boat": "tool",
    "spruce_chest_boat": "tool",
    "birch_boat": "tool",
    "birch_chest_boat": "tool",
    "jungle_boat": "tool",
    "jungle_chest_boat": "tool",
    "acacia_boat": "tool",
    "acacia_chest_boat": "tool",
    "dark_oak_boat": "tool",
    "dark_oak_chest_boat": "tool",
    "mangrove_boat": "tool",
    "mangrove_chest_boat": "tool",
    "cherry_boat": "tool",
    "cherry_chest_boat": "tool",
    "pale_oak_boat": "tool",
    "pale_oak_chest_boat": "tool",
    "bamboo_raft": "tool",
    "bamboo_chest_raft": "tool",

    # --- 音乐唱片 ---
    "music_disc_11": "tool",
    "music_disc_13": "tool",
    "music_disc_5": "tool",
    "music_disc_blocks": "tool",
    "music_disc_cat": "tool",
    "music_disc_chirp": "tool",
    "music_disc_creator": "tool",
    "music_disc_creator_music_box": "tool",
    "music_disc_far": "tool",
    "music_disc_lava_chicken": "tool",
    "music_disc_mall": "tool",
    "music_disc_mellohi": "tool",
    "music_disc_otherside": "tool",
    "music_disc_pigstep": "tool",
    "music_disc_precipice": "tool",
    "music_disc_relic": "tool",
    "music_disc_stal": "tool",
    "music_disc_strad": "tool",
    "music_disc_tears": "tool",
    "music_disc_wait": "tool",
    "music_disc_ward": "tool",

    # --- 战斗用品 ---
    "wooden_sword": "combat",
    "stone_sword": "combat",
    "copper_sword": "combat",
    "iron_sword": "combat",
    "golden_sword": "combat",
    "diamond_sword": "combat",
    "netherite_sword": "combat",
    "wooden_spear": "combat",
    "stone_spear": "combat",
    "copper_spear": "combat",
    "iron_spear": "combat",
    "golden_spear": "combat",
    "diamond_spear": "combat",
    "netherite_spear": "combat",
    "wooden_axe": "combat",
    "stone_axe": "combat",
    "copper_axe": "combat",
    "iron_axe": "combat",
    "golden_axe": "combat",
    "diamond_axe": "combat",
    "netherite_axe": "combat",

    # 盔甲
    "leather_helmet": "combat",
    "leather_chestplate": "combat",
    "leather_leggings": "combat",
    "leather_boots": "combat",
    "chainmail_helmet": "combat",
    "chainmail_chestplate": "combat",
    "chainmail_leggings": "combat",
    "chainmail_boots": "combat",
    "copper_helmet": "combat",
    "copper_chestplate": "combat",
    "copper_leggings": "combat",
    "copper_boots": "combat",
    "iron_helmet": "combat",
    "iron_chestplate": "combat",
    "iron_leggings": "combat",
    "iron_boots": "combat",
    "golden_helmet": "combat",
    "golden_chestplate": "combat",
    "golden_leggings": "combat",
    "golden_boots": "combat",
    "diamond_helmet": "combat",
    "diamond_chestplate": "combat",
    "diamond_leggings": "combat",
    "diamond_boots": "combat",
    "netherite_helmet": "combat",
    "netherite_chestplate": "combat",
    "netherite_leggings": "combat",
    "netherite_boots": "combat",
    "turtle_helmet": "combat",

    # 马铠
    "leather_horse_armor": "combat",
    "copper_horse_armor": "combat",
    "iron_horse_armor": "combat",
    "golden_horse_armor": "combat",
    "diamond_horse_armor": "combat",
    "netherite_horse_armor": "combat",

    # 鹦鹉螺铠
    "copper_nautilus_armor": "combat",
    "iron_nautilus_armor": "combat",
    "golden_nautilus_armor": "combat",
    "diamond_nautilus_armor": "combat",
    "netherite_nautilus_armor": "combat",

    # 狼铠
    "wolf_armor": "combat",

    # 不死图腾
    "totem_of_undying": "combat",

    # --- 工具 ---
    "wooden_pickaxe": "tool",
    "stone_pickaxe": "tool",
    "copper_pickaxe": "tool",
    "iron_pickaxe": "tool",
    "golden_pickaxe": "tool",
    "diamond_pickaxe": "tool",
    "netherite_pickaxe": "tool",
    "wooden_shovel": "tool",
    "stone_shovel": "tool",
    "copper_shovel": "tool",
    "iron_shovel": "tool",
    "golden_shovel": "tool",
    "diamond_shovel": "tool",
    "netherite_shovel": "tool",
    "wooden_hoe": "tool",
    "stone_hoe": "tool",
    "copper_hoe": "tool",
    "iron_hoe": "tool",
    "golden_hoe": "tool",
    "diamond_hoe": "tool",
    "netherite_hoe": "tool",

    # --- 食物 ---
    "apple": "food",
    "golden_apple": "food",
    "enchanted_golden_apple": "food",
    "melon_slice": "food",
    "sweet_berries": "food",
    "glow_berries": "food",
    "chorus_fruit": "food",
    "carrot": "food",
    "golden_carrot": "food",
    "potato": "food",
    "baked_potato": "food",
    "poisonous_potato": "food",
    "beetroot": "food",
    "dried_kelp": "food",
    "beef": "food",
    "cooked_beef": "food",
    "porkchop": "food",
    "cooked_porkchop": "food",
    "mutton": "food",
    "cooked_mutton": "food",
    "chicken": "food",
    "cooked_chicken": "food",
    "rabbit": "food",
    "cooked_rabbit": "food",
    "cod": "food",
    "cooked_cod": "food",
    "salmon": "food",
    "cooked_salmon": "food",
    "tropical_fish": "food",
    "pufferfish": "food",
    "bread": "food",
    "cookie": "food",
    "cake": "food",
    "pumpkin_pie": "food",
    "rotten_flesh": "food",
    "spider_eye": "food",
    "mushroom_stew": "food",
    "beetroot_soup": "food",
    "rabbit_stew": "food",
    "suspicious_stew": "food",
    "honey_bottle": "food",
    "ominous_bottle": "food",

    # --- 原材料 ---
    "coal": "material",
    "charcoal": "material",
    "raw_iron": "material",
    "raw_copper": "material",
    "raw_gold": "material",
    "emerald": "material",
    "lapis_lazuli": "material",
    "diamond": "material",
    "ancient_debris": "material",
    "netherite_scrap": "material",
    "netherite_ingot": "material",
    "netherite_upgrade_smithing_template": "material",
    "quartz": "material",
    "amethyst_shard": "material",
    "copper_ingot": "material",
    "iron_ingot": "material",
    "gold_ingot": "material",
    "copper_nugget": "material",
    "iron_nugget": "material",
    "gold_nugget": "material",
    "stick": "material",
    "flint": "material",
    "wheat": "material",
    "bone": "material",
    "bone_meal": "material",
    "string": "material",
    "feather": "material",
    "leather": "material",
    "rabbit_hide": "material",
    "honeycomb": "material",
    "resin_clump": "material",
    "ink_sac": "material",
    "glow_ink_sac": "material",
    "scute": "material",
    "armadillo_scute": "material",
    "turtle_scute": "material",
    "slime_ball": "material",
    "clay_ball": "material",
    "prismarine_shard": "material",
    "prismarine_crystals": "material",
    "nautilus_shell": "material",
    "heart_of_the_sea": "material",
    "fire_charge": "material",
    "blaze_rod": "material",
    "blaze_powder": "material",
    "breeze_rod": "material",
    "nether_star": "material",
    "ender_pearl": "tool",
    "ender_eye": "tool",
    "shulker_shell": "material",
    "popped_chorus_fruit": "material",
    "echo_shard": "material",
    "disc_fragment_5": "material",
    "white_dye": "material",
    "light_gray_dye": "material",
    "gray_dye": "material",
    "black_dye": "material",
    "brown_dye": "material",
    "red_dye": "material",
    "orange_dye": "material",
    "yellow_dye": "material",
    "lime_dye": "material",
    "green_dye": "material",
    "cyan_dye": "material",
    "light_blue_dye": "material",
    "blue_dye": "material",
    "purple_dye": "material",
    "magenta_dye": "material",
    "pink_dye": "material",
    "bowl": "material",
    "brick": "material",
    "nether_brick": "material",
    "resin_brick": "material",
    "paper": "material",
    "book": "material",
    "glowstone_dust": "material",
    "redstone": "material",
    "gunpowder": "material",
    "dragon_breath": "material",
    "fermented_spider_eye": "material",
    "glistering_melon_slice": "material",
    "rabbit_foot": "material",
    "ghast_tear": "material",
    "phantom_membrane": "material",
    "magma_cream": "material",
    "heavy_core": "material",
    "sugar": "material",
    "sugar_cane": "material",
    "experience_bottle": "material",
    "enchanted_book": "material",

    # 锻造模板
    "bolt_armor_trim_smithing_template": "material",
    "coast_armor_trim_smithing_template": "material",
    "dune_armor_trim_smithing_template": "material",
    "eye_armor_trim_smithing_template": "material",
    "flow_armor_trim_smithing_template": "material",
    "host_armor_trim_smithing_template": "material",
    "raiser_armor_trim_smithing_template": "material",
    "rib_armor_trim_smithing_template": "material",
    "sentry_armor_trim_smithing_template": "material",
    "shaper_armor_trim_smithing_template": "material",
    "silence_armor_trim_smithing_template": "material",
    "snout_armor_trim_smithing_template": "material",
    "spire_armor_trim_smithing_template": "material",
    "tide_armor_trim_smithing_template": "material",
    "vex_armor_trim_smithing_template": "material",
    "ward_armor_trim_smithing_template": "material",
    "wayfinder_armor_trim_smithing_template": "material",
    "wild_armor_trim_smithing_template": "material",

    # 旗帜图案
    "bordure_indented_banner_pattern": "material",
    "creeper_banner_pattern": "material",
    "field_masoned_banner_pattern": "material",
    "flower_banner_pattern": "material",
    "flow_banner_pattern": "material",
    "globe_banner_pattern": "material",
    "guster_banner_pattern": "material",
    "mojang_banner_pattern": "material",
    "piglin_banner_pattern": "material",
    "skull_banner_pattern": "material",

    # 陶片
    "angler_pottery_sherd": "material",
    "archer_pottery_sherd": "material",
    "arms_up_pottery_sherd": "material",
    "blade_pottery_sherd": "material",
    "brewer_pottery_sherd": "material",
    "burn_pottery_sherd": "material",
    "danger_pottery_sherd": "material",
    "explorer_pottery_sherd": "material",
    "flow_pottery_sherd": "material",
    "friend_pottery_sherd": "material",
    "guster_pottery_sherd": "material",
    "heart_pottery_sherd": "material",
    "heartbreak_pottery_sherd": "material",
    "howl_pottery_sherd": "material",
    "miner_pottery_sherd": "material",
    "mourner_pottery_sherd": "material",
    "plenty_pottery_sherd": "material",
    "prize_pottery_sherd": "material",
    "scrape_pottery_sherd": "material",
    "sheaf_pottery_sherd": "material",
    "shelter_pottery_sherd": "material",
    "skull_pottery_sherd": "material",
    "snort_pottery_sherd": "material",

    # --- 刷怪蛋 ---
    # (all *_spawn_egg handled by pattern matching)

    # --- 管理员用品 ---
    "debug_stick": "admin",
    "knowledge_book": "admin",

    # --- 药水/箭（特殊处理） ---
    "potion": "material",
    "splash_potion": "material",
    "lingering_potion": "material",
    "arrow": "combat",
    "spectral_arrow": "combat",
    "tipped_arrow": "combat",

    # --- 马具（挽具） ---
    "white_harness": "tool",
    "light_gray_harness": "tool",
    "gray_harness": "tool",
    "black_harness": "tool",
    "brown_harness": "tool",
    "red_harness": "tool",
    "orange_harness": "tool",
    "yellow_harness": "tool",
    "lime_harness": "tool",
    "green_harness": "tool",
    "cyan_harness": "tool",
    "light_blue_harness": "tool",
    "blue_harness": "tool",
    "purple_harness": "tool",
    "magenta_harness": "tool",
    "pink_harness": "tool",

    # --- 收纳袋 ---
    "white_bundle": "tool",
    "light_gray_bundle": "tool",
    "gray_bundle": "tool",
    "black_bundle": "tool",
    "brown_bundle": "tool",
    "red_bundle": "tool",
    "orange_bundle": "tool",
    "yellow_bundle": "tool",
    "lime_bundle": "tool",
    "green_bundle": "tool",
    "cyan_bundle": "tool",
    "light_blue_bundle": "tool",
    "blue_bundle": "tool",
    "purple_bundle": "tool",
    "magenta_bundle": "tool",
    "pink_bundle": "tool",
}


# ============================================================
# ID 模式匹配规则（中等优先级）
# 按顺序匹配，返回第一个匹配的分类
# ============================================================
PATTERN_RULES: list[tuple[str, str]] = [
    # 刷怪蛋
    (r"_spawn_egg$", "spawn_egg"),
    # 工具
    (r"_pickaxe$", "tool"),
    (r"_shovel$", "tool"),
    (r"_hoe$", "tool"),
    # 食物（纯食物物品）
    (r"^(cooked_|golden_carrot|baked_potato|melon_slice|sweet_berries|glow_berries|chorus_fruit|dried_kelp|pumpkin_pie|mushroom_stew|beetroot_soup|rabbit_stew|suspicious_stew|cookie|bread|honey_bottle|ominous_bottle)", "food"),
    # materials
    (r"(_ingot|_nugget|_scrap)$", "material"),
    (r"^raw_(iron|copper|gold)$", "material"),
    (r"(_shard|_crystal|_shell|_scute|_membrane)$", "material"),
    (r"(_armor_trim_smithing_template|_upgrade_smithing_template)$", "material"),
    (r"(_banner_pattern)$", "material"),
    (r"(_pottery_sherd)$", "material"),
    # 种子/作物
    (r"(_seeds|_pod|_propagule|torchflower)$", "material"),
    # bricks
    (r"(_brick)$", "material"),
    # dyes
    (r"(_dye)$", "material"),
    # boat/raft/chest_boat
    (r"(_boat|_chest_boat|_raft|_chest_raft)$", "tool"),
    # minecart
    (r"(_minecart)$", "tool"),
    # bucket (non-block variants)
    (r"(_bucket)$", "tool"),
    # music disc
    (r"^music_disc_", "tool"),
    # goat horn
    (r"^goat_horn$", "tool"),
]


def classify_item(item_id: str) -> str:
    """
    根据物品ID返回分类标签。

    Args:
        item_id: 不带minecraft命名空间的物品ID（如 "apple"）

    Returns:
        分类标签（如 "food", "tool", "combat" 等）
    """
    # 1. 先查硬编码精确映射
    if item_id in EXACT_CATEGORY_MAP:
        return EXACT_CATEGORY_MAP[item_id]

    # 2. ID模式匹配
    for pattern, category in PATTERN_RULES:
        if re.search(pattern, item_id):
            return category

    # 3. 默认归入material（原材料），输出时需要人工审核
    return "material"


# ============================================================
# 已知应排除的物品黑名单（虽然model是item但创造模式物品栏不含）
# ============================================================
EXCLUDE_ITEMS: set[str] = {
    # 不可合成的药水（创造模式物品栏只含可合成的）
    # 实际上potion/splash_potion/lingering_potion的base item是在的
    # 但具体效果变种由游戏动态生成，这里我们保留base item
    # 不可合成的药箭同理
}
