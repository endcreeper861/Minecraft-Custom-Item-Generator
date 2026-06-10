"""
原始游戏数据 → 程序可用物品JSON转换脚本。

从 raw_game_data/items/*.json 和 raw_game_data/zh_cn.json 中提取物品数据，
生成 data/items/*.json 文件，并复制纹理到 data/textures/。

用法：
    py -3.14 tools/convert_items.py

排除规则：
    若 zh_cn.json 中存在 block.minecraft.{id} 条目，视为方块排除。
    这能正确处理所有方块（包括 brewing_stand 等功能方块物品）。
"""

import json
import shutil
import sys
from pathlib import Path
from collections import Counter

sys.path.insert(0, str(Path(__file__).parent.parent))
from tools.item_categories import classify_item

RAW_ITEMS_DIR = Path("raw_game_data/items")
RAW_TEXTURES_DIR = Path("raw_game_data/textures/item")
ZH_CN_PATH = Path("raw_game_data/zh_cn.json")
OUTPUT_ITEMS_DIR = Path("data/items")
OUTPUT_TEXTURES_DIR = Path("data/textures")

CATEGORY_NAMES = {
    "building": "建筑方块", "dyed": "染色方块", "natural": "自然方块",
    "functional": "功能方块", "redstone": "红石方块", "tool": "工具与实用物品",
    "combat": "战斗用品", "food": "食物与饮品", "material": "原材料",
    "spawn_egg": "刷怪蛋", "admin": "管理员用品", "custom": "自定义物品",
}


def load_translations() -> dict[str, str]:
    with open(ZH_CN_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def get_chinese_name(item_id: str, translations: dict) -> str:
    key = f"item.minecraft.{item_id}"
    return translations.get(key, item_id)


def should_exclude(item_id: str, translations: dict) -> bool:
    """若存在 block.minecraft.{id} 条目 → 视为方块，排除。"""
    return f"block.minecraft.{item_id}" in translations


def main():
    print("=" * 60)
    print("MC命令生成器 - 物品数据转换工具")
    print("=" * 60)

    print("\n[1/4] 加载翻译文件...")
    translations = load_translations()
    item_count = sum(1 for k in translations if k.startswith("item.minecraft."))
    block_count = sum(1 for k in translations if k.startswith("block.minecraft."))
    print(f"  ✓ {item_count} 条物品翻译, {block_count} 条方块翻译")

    print("\n[2/4] 扫描原始物品数据...")
    raw_files = sorted(RAW_ITEMS_DIR.glob("*.json"))
    print(f"  ✓ 找到 {len(raw_files)} 个原始数据文件")

    items_to_keep = []
    items_excluded = []
    items_no_name = []

    for filepath in raw_files:
        item_id = filepath.stem
        if should_exclude(item_id, translations):
            items_excluded.append(item_id)
            continue
        name = get_chinese_name(item_id, translations)
        if name == item_id:
            items_no_name.append(item_id)
        cat = classify_item(item_id)
        items_to_keep.append((item_id, name, cat))

    print(f"  ✓ 保留 {len(items_to_keep)} 件物品, 排除 {len(items_excluded)} 件方块")

    # 生成JSON
    print("\n[3/4] 生成物品JSON文件...")
    OUTPUT_ITEMS_DIR.mkdir(parents=True, exist_ok=True)
    old_count = sum(1 for _ in OUTPUT_ITEMS_DIR.glob("*.json"))
    for f in OUTPUT_ITEMS_DIR.glob("*.json"):
        f.unlink()
    if old_count:
        print(f"  ✓ 清理 {old_count} 个旧JSON文件")

    created = 0
    category_stats = Counter()
    for item_id, name, cat in items_to_keep:
        data = {"name": name, "id": f"minecraft:{item_id}", "categories": [cat]}
        with open(OUTPUT_ITEMS_DIR / f"{item_id}.json", "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
            f.write("\n")
        created += 1
        category_stats[cat] += 1
    print(f"  ✓ 生成 {created} 个物品JSON文件")

    # 复制纹理
    print("\n[4/4] 复制纹理文件...")
    OUTPUT_TEXTURES_DIR.mkdir(parents=True, exist_ok=True)
    copied = 0
    missing = []
    for item_id, _, _ in items_to_keep:
        src = RAW_TEXTURES_DIR / f"{item_id}.png"
        dst = OUTPUT_TEXTURES_DIR / f"{item_id}.png"
        if src.exists():
            shutil.copy2(src, dst); copied += 1; continue
        # 动画纹理首帧
        cand = list(RAW_TEXTURES_DIR.glob(f"{item_id}_00.png"))
        if cand:
            shutil.copy2(cand[0], dst); copied += 1; continue
        # standby变体
        sb = RAW_TEXTURES_DIR / f"{item_id}_standby.png"
        if sb.exists():
            shutil.copy2(sb, dst); copied += 1; continue
        # 任意前缀匹配
        any_cand = list(RAW_TEXTURES_DIR.glob(f"{item_id}*.png"))
        if any_cand:
            shutil.copy2(any_cand[0], dst); copied += 1; continue
        missing.append(item_id)
    print(f"  ✓ 复制 {copied} 个纹理文件")
    if missing:
        print(f"  ⚠ {len(missing)} 个物品缺少纹理")

    # 报告
    print("\n" + "=" * 60)
    print("转换报告")
    print("=" * 60)
    print(f"\n📊 统计:")
    print(f"  总原始文件:    {len(raw_files)}")
    print(f"  保留物品:      {len(items_to_keep)}")
    print(f"  排除方块:      {len(items_excluded)}")
    print(f"  生成JSON:      {created}")
    print(f"  复制纹理:      {copied}")
    if missing:
        print(f"  缺少纹理:      {len(missing)}")

    print(f"\n📂 分类分布:")
    for cat in sorted(category_stats.keys()):
        cn = CATEGORY_NAMES.get(cat, cat)
        n = category_stats[cat]
        bar = "█" * (n // 5)
        print(f"  {cn:　<10s} ({cat:10s}): {n:4d}  {bar}")

    if items_no_name:
        print(f"\n⚠ 未找到中文名: {len(items_no_name)} 件")
        for x in items_no_name[:15]:
            print(f"  - {x}")
        if len(items_no_name) > 15:
            print(f"  ... 还有 {len(items_no_name) - 15} 件")

    if missing:
        print(f"\n⚠ 缺少纹理: {len(missing)} 件")
        for x in missing:
            print(f"  - {x}")

    print(f"\n✅ 转换完成！" + "=" * 55)


if __name__ == "__main__":
    main()
