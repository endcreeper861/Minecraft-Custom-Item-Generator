"""
原始游戏数据 → 程序可用物品JSON转换脚本 v2。

以 data/textures/*.png 为物品清单（有纹理即有物品形式），
自动排除火、水、空气等无纹理的方块。

用法：
    py -3.14 tools/convert_items.py
"""

import json
import sys
from pathlib import Path
from collections import Counter

sys.path.insert(0, str(Path(__file__).parent.parent))
from tools.item_categories import classify_item

TEXTURES_DIR = Path("data/textures")
ZH_CN_PATH = Path("raw_game_data/zh_cn.json")
OUTPUT_ITEMS_DIR = Path("data/items")

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
    """获取中文名：优先 item.minecraft.{id}，其次 block.minecraft.{id}。"""
    for prefix in ("item", "block"):
        key = f"{prefix}.minecraft.{item_id}"
        if key in translations:
            return translations[key]
    return item_id


def main():
    print("=" * 60)
    print("MC命令生成器 - 物品数据转换工具 v2")
    print("=" * 60)

    # 加载翻译
    print("\n[1/3] 加载翻译文件...")
    translations = load_translations()
    print(f"  ✓ 已加载 {len(translations)} 条翻译")

    # 以纹理文件为物品清单
    print("\n[2/3] 扫描纹理文件（作为物品清单）...")
    texture_files = sorted(TEXTURES_DIR.glob("*.png"))
    print(f"  ✓ 找到 {len(texture_files)} 个纹理文件")

    items_to_keep = []
    items_no_name = []
    excluded = []

    for tex_path in texture_files:
        item_id = tex_path.stem  # 文件名去掉 .png

        # 获取中文名
        name = get_chinese_name(item_id, translations)
        if name == item_id and f"item.minecraft.{item_id}" not in translations \
                and f"block.minecraft.{item_id}" not in translations:
            # 完全没有翻译条目 → 排除（如 golden_dandelion 等仅在纹理中存在的）
            excluded.append((item_id, "无翻译条目"))
            continue

        if name == item_id:
            items_no_name.append(item_id)

        cat = classify_item(item_id)
        items_to_keep.append((item_id, name, cat))

    print(f"  ✓ 保留 {len(items_to_keep)} 件物品, 排除 {len(excluded)} 件无翻译物品")

    # 生成JSON
    print("\n[3/3] 生成物品JSON文件...")
    OUTPUT_ITEMS_DIR.mkdir(parents=True, exist_ok=True)

    # 清理旧文件
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

    # 报告
    print("\n" + "=" * 60)
    print("转换报告")
    print("=" * 60)
    print(f"\n📊 统计:")
    print(f"  纹理文件:      {len(texture_files)}")
    print(f"  保留物品:      {len(items_to_keep)}")
    print(f"  排除:          {len(excluded)}")
    print(f"  生成JSON:      {created}")

    print(f"\n📂 分类分布:")
    for cat in sorted(category_stats.keys()):
        cn = CATEGORY_NAMES.get(cat, cat)
        n = category_stats[cat]
        bar = "█" * (n // 5)
        print(f"  {cn:　<10s} ({cat:10s}): {n:4d}  {bar}")

    if items_no_name:
        print(f"\n⚠ 未找到中文名（使用ID作为名称）: {len(items_no_name)} 件")
        for x in items_no_name[:20]:
            print(f"  - {x}")
        if len(items_no_name) > 20:
            print(f"  ... 还有 {len(items_no_name) - 20} 件")

    if excluded:
        print(f"\n🚫 排除的物品:")
        for x, reason in excluded:
            print(f"  - {x}  ({reason})")

    print(f"\n✅ 转换完成！" + "=" * 55)


if __name__ == "__main__":
    main()
