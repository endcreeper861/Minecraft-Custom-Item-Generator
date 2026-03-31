"""
定义附魔和附魔组数据结构，读取保存的附魔数据。

附魔数据存储在 `data/enchantments` 目录下的 JSON 文件中，每个文件对应一个附魔或附魔组。

附魔文件是一个对象，包含以下字段：

- `name`: 附魔名称
- `id`: 附魔 ID（如 `minecraft:sharpness`）
- `max_level`: 可选的最大等级（如 Sharpness 的 max_level 是 5）
- `description`: 可选的附魔描述

附魔组文件是一个数组，是多个附魔及其等级的组合。

附魔示例：
```
{
    "name": "时运",
    "id": "minecraft:fortune",
    "max_level": 3,
    "description": "使破坏方块后掉落物数量的期望值增加。"
}
```

附魔组示例：
```
[
    {
        "name": "时运",
        "id": "minecraft:fortune",
        "max_level": 3,
        "description": "使破坏方块后掉落物数量的期望值增加。"
        "level": 3
    },
    {
        "name": "效率",
        "id": "minecraft:efficiency",
        "max_level": 5,
        "description": "加快破坏方块的速度。"
        "level": 5
    }
]
```
"""


from dataclasses import dataclass
from pathlib import Path
from json import load
import logging

logger = logging.getLogger(__name__)


@dataclass
class Enchantment:
    name: str
    id: str
    max_level: int | None = None
    description: str = ""
    level: int = 1
    
    def to_json(self) -> dict:
        """将 Enchantment 对象转换为 JSON 可序列化的字典"""
        return {
            "name": self.name,
            "id": self.id,
            "max_level": self.max_level,
            "description": self.description,
            "level": self.level,
        }


@dataclass
class EnchantmentGroup:
    enchantments: list[Enchantment]
    
    def to_json(self) -> list[dict]:
        """将 EnchantmentGroup 对象转换为 JSON 可序列化的字典"""
        return [enchantment.to_json() for enchantment in self.enchantments]


def get_all_enchantments() -> list[Enchantment]:
    """从 data/enchantments 目录加载所有附魔数据，并返回 Enchantment 对象列表。"""
    enchantments = []
    for f in Path("data/enchantments").glob("*.json"):
        try:
            with f.open(encoding="utf-8") as file:
                data = load(file)
                enchantments.append(
                    Enchantment(
                        name=data["name"],
                        id=data["id"],
                        max_level=data.get("max_level"),
                        description=data.get("description", ""),
                    )
                )
        except Exception as e:
            logger.error(f"加载附魔数据失败: {f.name} - {e}")
    return enchantments
