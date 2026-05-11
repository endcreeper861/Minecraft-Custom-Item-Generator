"""
生成和处理文本组件（Text Component）。过去亦作原始JSON文本（Raw JSON Text），Minecraft通过它
向玩家发送和显示富文本。

更多参见：<https://zh.minecraft.wiki/w/%E6%96%87%E6%9C%AC%E7%BB%84%E4%BB%B6>
"""

from dataclasses import dataclass
from abc import ABC, abstractmethod
from typing import Literal

ContentType = Literal[
    "text", "translatable", "keybind", "score", "selector", "nbt", "object"
]


@dataclass
class Text(ABC):
    """表示单条文本组件的抽象基类。具有文本组件通用的属性。"""
    
    color: str | None = None
    """文本颜色。可以是Minecraft预定义的颜色名称（如"red"）或RGB十六进制字符串（如"#FF0000"）。"""
    bold: bool = False
    """是否加粗。默认为False。"""
    italic: bool = False
    """是否斜体。默认为False。"""
    underlined: bool = False
    """是否下划线。默认为False。"""
    strikethrough: bool = False
    """是否删除线。默认为False。"""
    obfuscated: bool = False
    """是否随机字符。默认为False。"""
    