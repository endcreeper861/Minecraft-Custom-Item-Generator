"""
物品分类规则引擎 v2。

分类基于创造模式物品栏标签页。使用"先精确匹配，再模式匹配"的策略。
纯物品（无block.minecraft条目）优先匹配 item 规则，方块物品（有block条目）匹配 block 规则。

分类标签：
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


# ============================================================
# 精确映射（最高优先级）
# ============================================================
EXACT: dict[str, str] = {
    # === 工具 ===
    "wooden_sword": "combat", "stone_sword": "combat", "copper_sword": "combat",
    "iron_sword": "combat", "golden_sword": "combat", "diamond_sword": "combat",
    "netherite_sword": "combat",
    "wooden_spear": "combat", "stone_spear": "combat", "copper_spear": "combat",
    "iron_spear": "combat", "golden_spear": "combat", "diamond_spear": "combat",
    "netherite_spear": "combat",
    "wooden_axe": "combat", "stone_axe": "combat", "copper_axe": "combat",
    "iron_axe": "combat", "golden_axe": "combat", "diamond_axe": "combat",
    "netherite_axe": "combat",
    "mace": "combat", "trident": "combat", "shield": "combat",
    "bow": "tool", "crossbow": "tool",
    "wooden_pickaxe": "tool", "stone_pickaxe": "tool", "copper_pickaxe": "tool",
    "iron_pickaxe": "tool", "golden_pickaxe": "tool", "diamond_pickaxe": "tool",
    "netherite_pickaxe": "tool",
    "wooden_shovel": "tool", "stone_shovel": "tool", "copper_shovel": "tool",
    "iron_shovel": "tool", "golden_shovel": "tool", "diamond_shovel": "tool",
    "netherite_shovel": "tool",
    "wooden_hoe": "tool", "stone_hoe": "tool", "copper_hoe": "tool",
    "iron_hoe": "tool", "golden_hoe": "tool", "diamond_hoe": "tool",
    "netherite_hoe": "tool",
    "fishing_rod": "tool", "carrot_on_a_stick": "tool",
    "warped_fungus_on_a_stick": "tool", "shears": "tool",
    "flint_and_steel": "tool", "brush": "tool", "spyglass": "tool",
    "clock": "tool", "compass": "tool", "recovery_compass": "tool",
    "map": "tool", "filled_map": "tool",
    "saddle": "tool", "lead": "tool", "name_tag": "tool",
    "writable_book": "tool", "written_book": "tool", "book": "material",
    "bundle": "tool", "snowball": "tool", "egg": "tool",
    "blue_egg": "tool", "brown_egg": "tool",
    "ender_pearl": "tool", "ender_eye": "tool", "firework_rocket": "tool",
    "firework_star": "material", "elytra": "tool", "wind_charge": "tool",
    "goat_horn": "tool", "painting": "tool", "item_frame": "tool",
    "glow_item_frame": "tool", "armor_stand": "tool",
    "minecart": "tool", "chest_minecart": "tool", "furnace_minecart": "tool",
    "hopper_minecart": "tool", "tnt_minecart": "tool",
    "command_block_minecart": "tool",
    "bucket": "tool", "water_bucket": "tool", "lava_bucket": "tool",
    "milk_bucket": "tool", "powder_snow_bucket": "tool",
    "cod_bucket": "tool", "salmon_bucket": "tool",
    "pufferfish_bucket": "tool", "tropical_fish_bucket": "tool",
    "axolotl_bucket": "tool", "tadpole_bucket": "tool",
    "glass_bottle": "tool",

    # 船
    "oak_boat": "tool", "spruce_boat": "tool", "birch_boat": "tool",
    "jungle_boat": "tool", "acacia_boat": "tool", "dark_oak_boat": "tool",
    "mangrove_boat": "tool", "cherry_boat": "tool", "pale_oak_boat": "tool",
    "oak_chest_boat": "tool", "spruce_chest_boat": "tool",
    "birch_chest_boat": "tool", "jungle_chest_boat": "tool",
    "acacia_chest_boat": "tool", "dark_oak_chest_boat": "tool",
    "mangrove_chest_boat": "tool", "cherry_chest_boat": "tool",
    "pale_oak_chest_boat": "tool",
    "bamboo_raft": "tool", "bamboo_chest_raft": "tool",

    # 音乐唱片
    "music_disc_11": "tool", "music_disc_13": "tool", "music_disc_5": "tool",
    "music_disc_blocks": "tool", "music_disc_cat": "tool",
    "music_disc_chirp": "tool", "music_disc_creator": "tool",
    "music_disc_creator_music_box": "tool", "music_disc_far": "tool",
    "music_disc_lava_chicken": "tool", "music_disc_mall": "tool",
    "music_disc_mellohi": "tool", "music_disc_otherside": "tool",
    "music_disc_pigstep": "tool", "music_disc_precipice": "tool",
    "music_disc_relic": "tool", "music_disc_stal": "tool",
    "music_disc_strad": "tool", "music_disc_tears": "tool",
    "music_disc_wait": "tool", "music_disc_ward": "tool",

    # === 盔甲 ===
    "leather_helmet": "combat", "leather_chestplate": "combat",
    "leather_leggings": "combat", "leather_boots": "combat",
    "chainmail_helmet": "combat", "chainmail_chestplate": "combat",
    "chainmail_leggings": "combat", "chainmail_boots": "combat",
    "copper_helmet": "combat", "copper_chestplate": "combat",
    "copper_leggings": "combat", "copper_boots": "combat",
    "iron_helmet": "combat", "iron_chestplate": "combat",
    "iron_leggings": "combat", "iron_boots": "combat",
    "golden_helmet": "combat", "golden_chestplate": "combat",
    "golden_leggings": "combat", "golden_boots": "combat",
    "diamond_helmet": "combat", "diamond_chestplate": "combat",
    "diamond_leggings": "combat", "diamond_boots": "combat",
    "netherite_helmet": "combat", "netherite_chestplate": "combat",
    "netherite_leggings": "combat", "netherite_boots": "combat",
    "turtle_helmet": "combat",
    "leather_horse_armor": "combat", "copper_horse_armor": "combat",
    "iron_horse_armor": "combat", "golden_horse_armor": "combat",
    "diamond_horse_armor": "combat", "netherite_horse_armor": "combat",
    "copper_nautilus_armor": "combat", "iron_nautilus_armor": "combat",
    "golden_nautilus_armor": "combat", "diamond_nautilus_armor": "combat",
    "netherite_nautilus_armor": "combat",
    "wolf_armor": "combat", "totem_of_undying": "combat",

    # === 食物 ===
    "apple": "food", "golden_apple": "food", "enchanted_golden_apple": "food",
    "melon_slice": "food", "sweet_berries": "food", "glow_berries": "food",
    "chorus_fruit": "food", "carrot": "food", "golden_carrot": "food",
    "potato": "food", "baked_potato": "food", "poisonous_potato": "food",
    "beetroot": "food", "dried_kelp": "food",
    "beef": "food", "cooked_beef": "food",
    "porkchop": "food", "cooked_porkchop": "food",
    "mutton": "food", "cooked_mutton": "food",
    "chicken": "food", "cooked_chicken": "food",
    "rabbit": "food", "cooked_rabbit": "food",
    "cod": "food", "cooked_cod": "food",
    "salmon": "food", "cooked_salmon": "food",
    "tropical_fish": "food", "pufferfish": "food",
    "bread": "food", "cookie": "food", "cake": "food",
    "pumpkin_pie": "food", "rotten_flesh": "food", "spider_eye": "food",
    "mushroom_stew": "food", "beetroot_soup": "food",
    "rabbit_stew": "food", "suspicious_stew": "food",
    "honey_bottle": "food", "ominous_bottle": "food",

    # === 材料 ===
    "coal": "material", "charcoal": "material",
    "raw_iron": "material", "raw_copper": "material", "raw_gold": "material",
    "emerald": "material", "lapis_lazuli": "material", "diamond": "material",
    "ancient_debris": "material", "netherite_scrap": "material",
    "netherite_ingot": "material",
    "copper_ingot": "material", "iron_ingot": "material",
    "gold_ingot": "material",
    "copper_nugget": "material", "iron_nugget": "material",
    "gold_nugget": "material",
    "quartz": "material", "amethyst_shard": "material",
    "stick": "material", "flint": "material",
    "wheat": "material", "bone": "material", "bone_meal": "material",
    "string": "material", "feather": "material", "leather": "material",
    "rabbit_hide": "material", "honeycomb": "material",
    "resin_clump": "material", "ink_sac": "material",
    "glow_ink_sac": "material", "slime_ball": "material",
    "clay_ball": "material", "prismarine_shard": "material",
    "prismarine_crystals": "material", "nautilus_shell": "material",
    "heart_of_the_sea": "material", "fire_charge": "material",
    "blaze_rod": "material", "blaze_powder": "material",
    "breeze_rod": "material",
    "nether_star": "material", "shulker_shell": "material",
    "popped_chorus_fruit": "material", "echo_shard": "material",
    "disc_fragment_5": "material",
    "white_dye": "material", "light_gray_dye": "material",
    "gray_dye": "material", "black_dye": "material",
    "brown_dye": "material", "red_dye": "material",
    "orange_dye": "material", "yellow_dye": "material",
    "lime_dye": "material", "green_dye": "material",
    "cyan_dye": "material", "light_blue_dye": "material",
    "blue_dye": "material", "purple_dye": "material",
    "magenta_dye": "material", "pink_dye": "material",
    "bowl": "material", "brick": "material",
    "nether_brick": "material", "resin_brick": "material",
    "paper": "material", "glowstone_dust": "material",
    "redstone": "material", "gunpowder": "material",
    "dragon_breath": "material", "fermented_spider_eye": "material",
    "glistering_melon_slice": "material", "rabbit_foot": "material",
    "ghast_tear": "material", "phantom_membrane": "material",
    "magma_cream": "material", "heavy_core": "material",
    "sugar": "material", "experience_bottle": "material",
    "enchanted_book": "material",
    "beetroot_seeds": "material", "melon_seeds": "material",
    "pumpkin_seeds": "material", "wheat_seeds": "material",
    "torchflower_seeds": "material", "pitcher_pod": "material",
    "cocoa_beans": "material", "nether_wart": "material",
    "torchflower": "material", "mangrove_propagule": "material",
    "chorus_flower": "material",  # actually a block, but treat as natural
    "chorus_fruit": "food",
    "chorus_plant": "natural",
    "sugar_cane": "material",

    # 锻造模板
    "netherite_upgrade_smithing_template": "material",
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
    "angler_pottery_sherd": "material", "archer_pottery_sherd": "material",
    "arms_up_pottery_sherd": "material", "blade_pottery_sherd": "material",
    "brewer_pottery_sherd": "material", "burn_pottery_sherd": "material",
    "danger_pottery_sherd": "material", "explorer_pottery_sherd": "material",
    "flow_pottery_sherd": "material", "friend_pottery_sherd": "material",
    "guster_pottery_sherd": "material", "heart_pottery_sherd": "material",
    "heartbreak_pottery_sherd": "material", "howl_pottery_sherd": "material",
    "miner_pottery_sherd": "material", "mourner_pottery_sherd": "material",
    "plenty_pottery_sherd": "material", "prize_pottery_sherd": "material",
    "scrape_pottery_sherd": "material", "sheaf_pottery_sherd": "material",
    "shelter_pottery_sherd": "material", "skull_pottery_sherd": "material",
    "snort_pottery_sherd": "material",

    # 药水/箭
    "potion": "material", "splash_potion": "material",
    "lingering_potion": "material",
    "arrow": "combat", "spectral_arrow": "combat", "tipped_arrow": "combat",

    # 挽具
    "white_harness": "tool", "light_gray_harness": "tool",
    "gray_harness": "tool", "black_harness": "tool",
    "brown_harness": "tool", "red_harness": "tool",
    "orange_harness": "tool", "yellow_harness": "tool",
    "lime_harness": "tool", "green_harness": "tool",
    "cyan_harness": "tool", "light_blue_harness": "tool",
    "blue_harness": "tool", "purple_harness": "tool",
    "magenta_harness": "tool", "pink_harness": "tool",

    # 收纳袋（item形式）
    "white_bundle": "tool", "light_gray_bundle": "tool",
    "gray_bundle": "tool", "black_bundle": "tool",
    "brown_bundle": "tool", "red_bundle": "tool",
    "orange_bundle": "tool", "yellow_bundle": "tool",
    "lime_bundle": "tool", "green_bundle": "tool",
    "cyan_bundle": "tool", "light_blue_bundle": "tool",
    "blue_bundle": "tool", "purple_bundle": "tool",
    "magenta_bundle": "tool", "pink_bundle": "tool",

    # 管理员
    "debug_stick": "admin", "knowledge_book": "admin",
    "command_block": "admin", "chain_command_block": "admin",
    "repeating_command_block": "admin", "structure_block": "admin",
    "structure_void": "admin", "jigsaw": "admin",
    "barrier": "admin", "light": "admin",
    "test_block": "admin", "test_instance_block": "admin",

    # ===== 方块精确分类 =====
    # 功能性
    "crafting_table": "functional", "furnace": "functional",
    "blast_furnace": "functional", "smoker": "functional",
    "smithing_table": "functional", "enchanting_table": "functional",
    "anvil": "functional", "chipped_anvil": "functional",
    "damaged_anvil": "functional", "brewing_stand": "functional",
    "cauldron": "functional", "beacon": "functional",
    "conduit": "functional", "lodestone": "functional",
    "respawn_anchor": "functional", "note_block": "functional",
    "jukebox": "functional", "chest": "functional",
    "trapped_chest": "functional", "ender_chest": "functional",
    "barrel": "functional", "hopper": "functional",
    "dispenser": "redstone", "dropper": "redstone",
    "crafter": "functional", "loom": "functional",
    "grindstone": "functional", "stonecutter": "functional",
    "cartography_table": "functional", "fletching_table": "functional",
    "lectern": "functional", "composter": "functional",
    "bell": "functional", "scaffolding": "functional",
    "ladder": "functional",
    "beehive": "functional", "bee_nest": "functional",
    "flower_pot": "functional", "decorated_pot": "functional",
    "campfire": "functional", "soul_campfire": "functional",
    "end_crystal": "combat",
    "tnt": "functional",
    "end_portal_frame": "functional",
    "spawner": "functional", "trial_spawner": "functional",
    "vault": "functional",
    "creaking_heart": "functional",
    "dragon_egg": "functional",
    "iron_bars": "building", "copper_bars": "building",
    "chain": "building", "iron_chain": "building",
    "copper_chain": "building",
    "iron_door": "functional", "iron_trapdoor": "functional",
    "torch": "functional", "soul_torch": "functional",
    "redstone_torch": "redstone", "copper_torch": "functional",
    "lantern": "functional", "soul_lantern": "functional",
    "copper_lantern": "functional", "end_rod": "functional",
    "lightning_rod": "functional",
    "glowstone": "functional", "redstone_lamp": "functional",
    "sea_lantern": "functional", "shroomlight": "functional",
    "jack_o_lantern": "functional",
    "ochre_froglight": "functional", "verdant_froglight": "functional",
    "pearlescent_froglight": "functional",

    # 红石
    "redstone_block": "redstone", "observer": "redstone",
    "piston": "redstone", "sticky_piston": "redstone",
    "target": "redstone", "daylight_detector": "redstone",
    "tripwire_hook": "redstone", "lever": "redstone",
    "comparator": "redstone", "repeater": "redstone",
    "calibrated_sculk_sensor": "redstone",
    "sculk_sensor": "redstone", "sculk_shrieker": "redstone",
    "sculk_catalyst": "redstone",
    "heavy_weighted_pressure_plate": "redstone",
    "light_weighted_pressure_plate": "redstone",

    # 自然
    "grass_block": "natural", "podzol": "natural",
    "mycelium": "natural", "dirt_path": "natural",
    "dirt": "natural", "coarse_dirt": "natural",
    "rooted_dirt": "natural", "farmland": "natural",
    "mud": "natural", "packed_mud": "natural",
    "muddy_mangrove_roots": "natural",
    "clay": "natural", "gravel": "natural",
    "sand": "natural", "red_sand": "natural",
    "ice": "natural", "packed_ice": "natural",
    "blue_ice": "natural", "snow": "natural",
    "snow_block": "natural", "moss_block": "natural",
    "moss_carpet": "natural",
    "pale_moss_block": "natural", "pale_moss_carpet": "natural",
    "stone": "natural", "deepslate": "natural",
    "granite": "natural", "diorite": "natural",
    "andesite": "natural", "calcite": "natural",
    "tuff": "natural", "dripstone_block": "natural",
    "pointed_dripstone": "natural",
    "obsidian": "natural", "crying_obsidian": "natural",
    "magma_block": "natural", "bone_block": "natural",
    "netherrack": "natural", "soul_sand": "natural",
    "soul_soil": "natural", "end_stone": "natural",
    "basalt": "natural", "smooth_basalt": "natural",
    "blackstone": "natural", "gilded_blackstone": "natural",
    "sculk": "natural", "sculk_vein": "natural",
    "sea_pickle": "natural", "seagrass": "natural",
    "kelp": "natural", "lily_pad": "natural",
    "vine": "natural", "glow_lichen": "natural",
    "hanging_roots": "natural", "pale_hanging_moss": "natural",
    "spore_blossom": "natural",
    "small_dripleaf": "natural", "big_dripleaf": "natural",
    "bamboo": "natural", "sugar_cane": "natural",
    "cactus": "natural", "cactus_flower": "natural",
    "cobweb": "natural",
    "hay_block": "natural", "dried_kelp_block": "natural",
    "melon": "natural", "pumpkin": "natural",
    "carved_pumpkin": "natural",
    "brown_mushroom": "natural", "red_mushroom": "natural",
    "brown_mushroom_block": "natural", "red_mushroom_block": "natural",
    "mushroom_stem": "natural",
    "crimson_fungus": "natural", "warped_fungus": "natural",
    "nether_sprouts": "natural",
    "crimson_roots": "natural", "warped_roots": "natural",
    "nether_wart_block": "natural", "warped_wart_block": "natural",
    "shroomlight": "functional",
    "crimson_nylium": "natural", "warped_nylium": "natural",
    "sponge": "natural", "wet_sponge": "natural",
    "frogspawn": "natural", "turtle_egg": "natural",
    "sniffer_egg": "natural",
    "bedrock": "natural",
    "dragon_egg": "functional",
    "reinforced_deepslate": "natural",
    "budding_amethyst": "natural",
    "small_amethyst_bud": "natural",
    "medium_amethyst_bud": "natural",
    "large_amethyst_bud": "natural",
    "amethyst_cluster": "natural",
    "amethyst_block": "building",
    "resin_block": "natural", "resin_bricks": "building",
    "resin_clump": "material",

    # 建筑基石
    "stone_bricks": "building", "mossy_stone_bricks": "building",
    "cracked_stone_bricks": "building", "chiseled_stone_bricks": "building",
    "cobblestone": "building", "mossy_cobblestone": "building",
    "deepslate_bricks": "building", "cracked_deepslate_bricks": "building",
    "deepslate_tiles": "building", "cracked_deepslate_tiles": "building",
    "polished_deepslate": "building", "chiseled_deepslate": "building",
    "cobbled_deepslate": "building",
    "polished_granite": "building", "polished_diorite": "building",
    "polished_andesite": "building",
    "polished_tuff": "building", "tuff_bricks": "building",
    "chiseled_tuff": "building", "chiseled_tuff_bricks": "building",
    "bricks": "building",
    "sandstone": "building", "chiseled_sandstone": "building",
    "cut_sandstone": "building", "smooth_sandstone": "building",
    "red_sandstone": "building", "chiseled_red_sandstone": "building",
    "cut_red_sandstone": "building", "smooth_red_sandstone": "building",
    "prismarine": "building", "prismarine_bricks": "building",
    "dark_prismarine": "building",
    "nether_bricks": "building", "cracked_nether_bricks": "building",
    "chiseled_nether_bricks": "building",
    "red_nether_bricks": "building",
    "polished_blackstone": "building",
    "polished_blackstone_bricks": "building",
    "cracked_polished_blackstone_bricks": "building",
    "chiseled_polished_blackstone": "building",
    "end_stone_bricks": "building",
    "purpur_block": "building", "purpur_pillar": "building",
    "quartz_block": "building", "quartz_bricks": "building",
    "quartz_pillar": "building", "chiseled_quartz_block": "building",
    "smooth_quartz": "building",
    "coal_block": "building", "iron_block": "building",
    "gold_block": "building", "diamond_block": "building",
    "emerald_block": "building", "lapis_block": "building",
    "netherite_block": "building",
    "raw_iron_block": "building", "raw_copper_block": "building",
    "raw_gold_block": "building",
    "copper_block": "building", "cut_copper": "building",
    "chiseled_copper": "building",
    "copper_grate": "building",
    "exposed_copper": "building", "exposed_cut_copper": "building",
    "exposed_chiseled_copper": "building", "exposed_copper_grate": "building",
    "weathered_copper": "building", "weathered_cut_copper": "building",
    "weathered_chiseled_copper": "building", "weathered_copper_grate": "building",
    "oxidized_copper": "building", "oxidized_cut_copper": "building",
    "oxidized_chiseled_copper": "building", "oxidized_copper_grate": "building",
    "waxed_copper_block": "building", "waxed_cut_copper": "building",
    "waxed_chiseled_copper": "building", "waxed_copper_grate": "building",
    "waxed_exposed_copper": "building", "waxed_exposed_cut_copper": "building",
    "waxed_exposed_chiseled_copper": "building",
    "waxed_exposed_copper_grate": "building",
    "waxed_weathered_copper": "building", "waxed_weathered_cut_copper": "building",
    "waxed_weathered_chiseled_copper": "building",
    "waxed_weathered_copper_grate": "building",
    "waxed_oxidized_copper": "building", "waxed_oxidized_cut_copper": "building",
    "waxed_oxidized_chiseled_copper": "building",
    "waxed_oxidized_copper_grate": "building",
    "smooth_stone": "building",
    "honey_block": "natural", "honeycomb_block": "natural",
    "slime_block": "natural",
    "copper_door": "building", "exposed_copper_door": "building",
    "weathered_copper_door": "building", "oxidized_copper_door": "building",
    "waxed_copper_door": "building", "waxed_exposed_copper_door": "building",
    "waxed_weathered_copper_door": "building",
    "waxed_oxidized_copper_door": "building",
    "copper_trapdoor": "building", "exposed_copper_trapdoor": "building",
    "weathered_copper_trapdoor": "building",
    "oxidized_copper_trapdoor": "building",
    "waxed_copper_trapdoor": "building",
    "waxed_exposed_copper_trapdoor": "building",
    "waxed_weathered_copper_trapdoor": "building",
    "waxed_oxidized_copper_trapdoor": "building",
    "copper_bulb": "building", "exposed_copper_bulb": "building",
    "weathered_copper_bulb": "building", "oxidized_copper_bulb": "building",
    "waxed_copper_bulb": "building", "waxed_exposed_copper_bulb": "building",
    "waxed_weathered_copper_bulb": "building",
    "waxed_oxidized_copper_bulb": "building",
    "copper_chest": "functional",
    "exposed_copper_chest": "functional",
    "weathered_copper_chest": "functional",
    "oxidized_copper_chest": "functional",
    "waxed_copper_chest": "functional",
    "waxed_exposed_copper_chest": "functional",
    "waxed_weathered_copper_chest": "functional",
    "waxed_oxidized_copper_chest": "functional",
    "copper_golem_statue": "functional",
    "exposed_copper_golem_statue": "functional",
    "weathered_copper_golem_statue": "functional",
    "oxidized_copper_golem_statue": "functional",
    "waxed_copper_golem_statue": "functional",
    "waxed_exposed_copper_golem_statue": "functional",
    "waxed_weathered_copper_golem_statue": "functional",
    "waxed_oxidized_copper_golem_statue": "functional",
    "copper_lantern": "functional",
    "exposed_copper_lantern": "functional",
    "weathered_copper_lantern": "functional",
    "oxidized_copper_lantern": "functional",
    "waxed_copper_lantern": "functional",
    "waxed_exposed_copper_lantern": "functional",
    "waxed_weathered_copper_lantern": "functional",
    "waxed_oxidized_copper_lantern": "functional",

    # 书架/展示架 → functional
    "bookshelf": "functional", "chiseled_bookshelf": "functional",
}

# ============================================================
# 物品模式匹配（纯物品，不含方块条目）
# ============================================================
ITEM_PATTERNS: list[tuple[str, str]] = [
    (r"_spawn_egg$", "spawn_egg"),
    (r"^music_disc_", "tool"),
    (r"_boat$|_chest_boat$|_raft$|_chest_raft$", "tool"),
    (r"_minecart$", "tool"),
    (r"_bucket$", "tool"),
    (r"^goat_horn$", "tool"),
    (r"_armor_trim_smithing_template$|_upgrade_smithing_template$", "material"),
    (r"_banner_pattern$", "material"),
    (r"_pottery_sherd$", "material"),
    (r"(_ingot|_nugget|_scrap)$", "material"),
    (r"^raw_(iron|copper|gold)$", "material"),
    (r"(_shard|_shell|_scute|_membrane)$", "material"),
    (r"(_dye)$", "material"),
    (r"(_brick)$", "material"),
    (r"(_seeds|_pod)$", "material"),
]


# ============================================================
# 方块模式匹配（有 block.minecraft 条目的物品）
# 按顺序匹配，返回第一个命中的分类
# ============================================================
BLOCK_PATTERNS: list[tuple[str, str]] = [
    # 染色类（有颜色前缀的）
    (r"^(white|light_gray|gray|black|brown|red|orange|yellow|lime|green|cyan|light_blue|blue|purple|magenta|pink)_(wool|carpet|terracotta|concrete|concrete_powder|glazed_terracotta|stained_glass|stained_glass_pane|shulker_box|bed|candle|banner)$", "dyed"),
    # 染色玻璃/玻璃板
    (r"^(white|light_gray|gray|black|brown|red|orange|yellow|lime|green|cyan|light_blue|blue|purple|magenta|pink)_stained_glass$", "dyed"),
    (r"^(white|light_gray|gray|black|brown|red|orange|yellow|lime|green|cyan|light_blue|blue|purple|magenta|pink)_stained_glass_pane$", "dyed"),
    # 红石类
    (r"^(redstone_|repeater|comparator|observer|piston|sticky_piston|target|daylight_detector|tripwire_hook|lever|dispenser|dropper|hopper|sculk_sensor|sculk_shrieker|sculk_catalyst|calibrated_sculk_sensor|note_block|heavy_weighted_pressure_plate|light_weighted_pressure_plate)", "redstone"),
    # 功能性
    (r"^(crafting_table|furnace|smoker|blast_furnace|smithing_table|enchanting_table|anvil|chipped_anvil|damaged_anvil|brewing_stand|cauldron|beacon|conduit|lodestone|respawn_anchor|jukebox|chest|trapped_chest|ender_chest|barrel|loom|grindstone|stonecutter|cartography_table|fletching_table|lectern|composter|bell|scaffolding|ladder|beehive|bee_nest|flower_pot|decorated_pot|campfire|soul_campfire|tnt|end_portal_frame|spawner|trial_spawner|vault|creaking_heart|torch|soul_torch|lantern|soul_lantern|end_rod|lightning_rod|glowstone|redstone_lamp|sea_lantern|shroomlight|jack_o_lantern|ochre_froglight|verdant_froglight|pearlescent_froglight|iron_door|iron_trapdoor|bookshelf|chiseled_bookshelf)", "functional"),
    # 铁轨
    (r"^(rail|powered_rail|detector_rail|activator_rail)$", "functional"),
    # 门/活板门（非铁质）
    (r"_(door|trapdoor)$", "building"),
    # 自然类 - 原木/菌柄/木头
    (r"_(log|wood|stem|hyphae)$", "natural"),
    (r"^stripped_", "natural"),
    # 自然类 - 树叶
    (r"_leaves$", "natural"),
    # 自然类 - 树苗
    (r"_sapling$", "natural"),
    # 自然类 - 花草
    (r"^(grass|fern|dead_bush|bush|short_grass|short_dry_grass|tall_grass|tall_dry_grass|large_fern|lilac|peony|rose_bush|sunflower|dandelion|poppy|allium|azure_bluet|blue_orchid|cornflower|lily_of_the_valley|oxeye_daisy|orange_tulip|pink_tulip|red_tulip|white_tulip|wither_rose|torchflower|closed_eyeblossom|open_eyeblossom|pitcher_plant|wildflowers|pink_petals|firefly_bush|leaf_litter|spore_blossom|flowering_azalea|azalea|mangrove_propagule|mangrove_roots|hanging_roots|pale_hanging_moss|brown_mushroom|red_mushroom|crimson_fungus|warped_fungus|crimson_roots|warped_roots|nether_sprouts|nether_wart|chorus_flower|chorus_plant)$", "natural"),
    # 自然类 - 沙/土/冰/雪
    (r"^(dirt|coarse_dirt|rooted_dirt|dirt_path|farmland|mud|packed_mud|muddy_mangrove_roots|clay|gravel|sand|red_sand|ice|packed_ice|blue_ice|snow|snow_block|moss_block|moss_carpet|pale_moss_block|pale_moss_carpet|grass_block|podzol|mycelium)$", "natural"),
    # 自然类 - 石头类
    (r"^(stone|deepslate|granite|diorite|andesite|calcite|tuff|dripstone_block|pointed_dripstone|obsidian|crying_obsidian|magma_block|bone_block|netherrack|soul_sand|soul_soil|end_stone|basalt|smooth_basalt|blackstone|gilded_blackstone|sculk|sculk_vein|sea_pickle|seagrass|kelp|lily_pad|vine|glow_lichen|bamboo|cactus|cactus_flower|cobweb|hay_block|dried_kelp_block|melon|pumpkin|carved_pumpkin|brown_mushroom_block|red_mushroom_block|mushroom_stem|nether_wart_block|warped_wart_block|shroomlight|crimson_nylium|warped_nylium|sponge|wet_sponge|frogspawn|turtle_egg|sniffer_egg|bedrock|reinforced_deepslate|budding_amethyst|small_amethyst_bud|medium_amethyst_bud|large_amethyst_bud|amethyst_cluster)$", "natural"),
    # 自然类 - 珊瑚
    (r"_coral$|_coral_block$|_coral_fan$", "natural"),
    # 自然类 - 矿石
    (r"_ore$", "natural"),
    (r"^ancient_debris$", "natural"),
    # 建筑类 - 楼梯/台阶/墙/栅栏/栅栏门
    (r"_(stairs|slab|wall|fence|fence_gate)$", "building"),
    # 建筑类 - 按钮/压力板
    (r"_(button|pressure_plate)$", "building"),
    # 建筑类 - 告示牌
    (r"_(sign|hanging_sign)$", "building"),
    # 建筑类 - 木板
    (r"_planks$", "building"),
    # 建筑类 - 马赛克
    (r"_mosaic$", "building"),
    # 建筑类 - 展示架
    (r"_shelf$", "building"),
    # 建筑类 - 砖类
    (r"(_bricks|_brick_slab|_brick_stairs|_brick_wall)$", "building"),
    # 建筑类 - 石砖类
    (r"(polished_|chiseled_|cut_|smooth_|mossy_|cracked_)", "building"),
    # 建筑类 - 方块（矿石块、矿物块等）
    (r"(_block$|^raw_.*_block$)", "building"),
    # 建筑类 - 柱
    (r"_pillar$", "building"),
    # 建筑类 - 瓦
    (r"_tiles$", "building"),
    # 建筑类 - 栅栏/栏杆
    (r"(_bars|_chain)$", "building"),
    # 建筑类 - 玻璃
    (r"^(glass|glass_pane|tinted_glass)$", "building"),
    # 铜相关建筑
    (r"^(exposed_|weathered_|oxidized_|waxed_)", "building"),
    # 铜相关功能性
    (r"copper_(chest|golem_statue|lantern)", "functional"),
]


def classify_item(item_id: str) -> str:
    """
    根据物品ID返回创造模式分类标签。

    优先级：精确映射 > 物品模式匹配 > 方块模式匹配 > 默认 material
    """
    # 1. 精确映射
    if item_id in EXACT:
        return EXACT[item_id]

    # 2. 物品模式匹配
    for pattern, category in ITEM_PATTERNS:
        if re.search(pattern, item_id):
            return category

    # 3. 方块模式匹配
    for pattern, category in BLOCK_PATTERNS:
        if re.search(pattern, item_id):
            return category

    # 4. 默认 → 原材料（需人工审核）
    return "material"
