"""
定义状态效果和状态效果组数据结构，读取保存的状态效果数据。

状态效果数据储存在 `data/effects` 目录下的 JSON 文件中，每个文件对应一个状态效果或状态效果组。

状态效果文件是一个对象，包含以下字段：

- `name`: 状态效果名称
- `id`: 状态效果 ID（如 `minecraft:strength`）
- `description`: 可选的状态效果描述

状态效果组文件是一个数组，是多个状态效果及其等级的组合。游戏保存的是“倍率”（amplifier）值而不是等级。倍率比等级小1，例如力量II的倍率为1。

状态效果示例：
```json
{
    "name": "夜视",
    "id": "minecraft:night_vision",
    "description": "调亮视野"
}
```

状态效果组示例：
```json
[
    {
        "name": "夜视",
        "id": "minecraft:night_vision",
        "description": "调亮视野",
        "amplifier": 0
    },
    {
        "name": "力量",
        "id": "minecraft:strength",
        "description": "增加近战攻击伤害",
        "amplifier": 1
    }
]
```
"""

from dataclasses import dataclass
from pathlib import Path
from json import load
import logging

logger = logging.getLogger(__name__)


EFFECT_DATA_DIR = "data/effects/"


@dataclass
class Effect:
    name: str
    id: str
    description: str = ""
    amplifier: int = 0

    def to_dict(self) -> dict:
        """将 Effect 对象转换为 JSON 可序列化的字典"""
        return {
            "name": self.name,
            "id": self.id,
            "description": self.description,
            "amplifier": self.amplifier,
        }


@dataclass
class EffectGroup:
    effects: list[Effect]

    def to_dict(self) -> list[dict]:
        """将 EffectGroup 对象转换为 JSON 可序列化的列表"""
        return [effect.to_dict() for effect in self.effects]


def get_all_effects() -> list[Effect]:
    """从 EFFECT_DATA_DIR 目录下的 JSON 文件中读取所有状态效果数据，并返回 Effect 对象列表"""
    effects = []
    for f in Path(EFFECT_DATA_DIR).glob("*.json"):
        try:
            with f.open("r", encoding="utf-8") as file:
                data = load(file)
                effects.append(Effect(**data))
        except Exception as e:
            logger.error(f"加载状态效果数据失败: {f.name} - {e}")
    return effects
