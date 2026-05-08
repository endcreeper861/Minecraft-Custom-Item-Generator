"""
定义物品数据结构，读取保存的物品数据。

物品数据存储在 `data/items` 目录下的 JSON 文件中，每个文件是一个物品的对象，包含以下字段：

- `name`: 物品名称
- `id`: 物品 ID（Minecraft 内部标识）
- `categories`: 物品分类列表（如 "building", "combat" 等）
- `components`: 可选的物品堆叠组件（如附魔、属性等）
- `count`: 物品数量，默认为 1

示例：
```json
{
    "name": "钻石剑",
    "id": "minecraft:diamond_sword",
    "categories": [
        "combat"
    ]
}
```

其中物品堆叠组件使物品有丰富多样的功能。物品堆叠组件介绍详见：
<https://zh.minecraft.wiki/w/数据组件>
"""

from dataclasses import dataclass, field
from typing import Literal, Any
from pathlib import Path
from json import load, dumps
import logging

logger = logging.getLogger(__name__)

ItemCategory = Literal[
    "custom",
    "building",
    "dyed",
    "natural",
    "functional",
    "redstone",
    "tool",
    "combat",
    "food",
    "material",
    "spawn_egg",
    "admin",
]

CONSUME_ANIMATIONS_DESC = [
    "吃（默认）",
    "无动作",
    "饮用",
    "格挡",
    "拉弓",
    "清刷",
    "弩上弦",
    "矛蓄力",
    "三叉戟投掷",
    "看望远镜",
    "吹山羊角",
    "使用收纳袋",
]

CONSUME_ANIMATIONS_MAP = {
    "吃（默认）": "eat",
    "无动作": "none",
    "饮用": "drink",
    "格挡": "block",
    "拉弓": "bow",
    "清刷": "brush",
    "弩上弦": "crossbow",
    "矛蓄力": "spear",
    "三叉戟投掷": "trident",
    "看望远镜": "spyglass",
    "吹山羊角": "toot_horn",
    "使用收纳袋": "bundle",
}


@dataclass
class Item:
    name: str
    id: str
    categories: list[ItemCategory] = field(default_factory=list)  # 分类
    components: dict[str, Any] = field(default_factory=dict)  # 物品堆叠组件
    count: int = 1  # 默认数量为1

    def item_stack(self) -> str:
        """生成物品堆叠字符串"""
        if self.components:
            components_str = ",".join(
                f"{k}={dumps(v, separators=(',', ':'))}"
                for k, v in self.components.items()
            )
            return f"{self.id}[{components_str}]"
        else:
            return f"{self.id}"

    def to_dict(self) -> dict:
        """将 Item 对象转换为 JSON 可序列化的字典"""
        return {
            "name": self.name,
            "id": self.id,
            "categories": self.categories,
            "components": self.components,
            "count": self.count,
        }


def get_all_items() -> list[Item]:
    """读取所有物品数据"""
    item_list = []

    for f in Path("data/items").glob("*.json"):
        with f.open("r", encoding="utf-8") as file:
            data = load(file)
            item_list.append(
                Item(
                    name=data["name"],
                    id=data["id"],
                    categories=data["categories"],
                    components=data.get("components", {}),
                    count=data.get("count", 1),
                )
            )
    
    for f in Path("custom/items").glob("*.json"):
        with f.open("r", encoding="utf-8") as file:
            data = load(file)
            item_list.append(
                Item(
                    name=f.stem,  # 使用文件名作为物品名称
                    id=data["id"],
                    categories=["custom"],
                    components=data.get("components", {}),
                    count=data.get("count", 1),
                )
            )

    logger.info(f"已加载 {len(item_list)} 个物品数据")

    return item_list
