"""
生成和处理文本组件（Text Component / Raw JSON Text）。

Minecraft Java 版通过文本组件向玩家发送和显示富文本。文本组件以树状结构保存，
支持 7 种组件类型、完整样式系统、点击/悬停事件及组件继承。

三种基础结构：字符串形式、列表形式和复合标签形式。本模块的 ``to_dict()``
方法自动选择最简合法形式输出。

更多参见：<https://zh.minecraft.wiki/w/%E6%96%87%E6%9C%AC%E7%BB%84%E4%BB%B6>
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# ═══════════════════════════════════════════════════════════════
#  常量定义
# ═══════════════════════════════════════════════════════════════

# 组件类型列表（type 字段可选值，按自动推断优先级排列）
# 注意：text 排在最后作为兜底，因为其 text 字段默认值为 ""（非 None），
# 若排在首位会导致其他类型永不被自动检测到。
COMPONENT_TYPES = [
    "translatable",
    "keybind",
    "score",
    "selector",
    "nbt",
    "object",
    "text",
]

# 点击事件 action 类型
CLICK_ACTIONS = [
    "change_page",
    "copy_to_clipboard",
    "custom",
    "open_file",
    "open_url",
    "run_command",
    "show_dialog",
    "suggest_command",
]

# 悬停事件 action 类型
HOVER_ACTIONS = [
    "show_text",
    "show_item",
    "show_entity",
]

# 各点击事件 action 在 JSON 中对应的字段名
_CLICK_ACTION_FIELDS: dict[str, list[str]] = {
    "change_page": ["page"],
    "copy_to_clipboard": ["value"],
    "custom": ["id", "payload"],
    "open_file": ["path"],
    "open_url": ["url"],
    "run_command": ["command"],
    "show_dialog": ["dialog"],
    "suggest_command": ["command"],
}

# 各悬停事件 action 在 JSON 中对应的字段名
_HOVER_ACTION_FIELDS: dict[str, list[str]] = {
    "show_text": ["value"],
    "show_item": ["id", "count", "components"],
    "show_entity": ["id", "name", "uuid"],
}

# 各组件类型对应的"特征字段"——值非 None 即表示该类型有效
_TYPE_MARKERS: dict[str, str] = {
    "text": "text",
    "translatable": "translate",
    "keybind": "keybind",
    "score": "score",
    "selector": "selector",
    "nbt": "nbt",
    "object": "obj_type",
}


# ═══════════════════════════════════════════════════════════════
#  ClickEvent — 点击事件
# ═══════════════════════════════════════════════════════════════


@dataclass
class ClickEvent:
    """文本组件的点击事件。

    支持 8 种 action 类型，每种有专属字段。``to_dict()`` 仅输出当前 action
    对应的字段，``from_dict()`` 按 action 路由解析。

    Attributes:
        action: 点击行为类型，为 ``CLICK_ACTIONS`` 之一。
        value: 用于 ``copy_to_clipboard``，要复制到剪贴板的字符串。
        page: 用于 ``change_page``，要跳转到的书页（>0）。
        url: 用于 ``open_url``，要打开的 URL。
        path: 用于 ``open_file``，要打开的文件路径。
        command: 用于 ``run_command`` / ``suggest_command``，命令字符串。
        id: 用于 ``custom``，自定义网络负载命名空间 ID。
        payload: 用于 ``custom``，自定义网络负载内容。
        dialog: 用于 ``show_dialog``，对话框命名空间 ID 或内联定义。
    """

    action: str
    value: str | None = None
    page: int | None = None
    url: str | None = None
    path: str | None = None
    command: str | None = None
    id: str | None = None
    payload: Any = None
    dialog: str | dict | None = None

    def to_dict(self) -> dict:
        """转换为 JSON 可序列化的字典。

        仅包含 ``action`` 及当前 action 对应的非 None 字段。
        """
        result: dict[str, Any] = {"action": self.action}
        for field_name in _CLICK_ACTION_FIELDS.get(self.action, []):
            value = getattr(self, field_name, None)
            if value is not None:
                result[field_name] = value
        return result

    @classmethod
    def from_dict(cls, data: dict) -> ClickEvent:
        """从字典反序列化 ClickEvent。

        按 ``data["action"]`` 确定类型，仅读取对应字段。
        """
        action = data.get("action", "")
        kwargs: dict[str, Any] = {"action": action}
        for field_name in _CLICK_ACTION_FIELDS.get(action, []):
            if field_name in data:
                kwargs[field_name] = data[field_name]
        return cls(**kwargs)


# ═══════════════════════════════════════════════════════════════
#  HoverEvent — 悬停事件
# ═══════════════════════════════════════════════════════════════


@dataclass
class HoverEvent:
    """文本组件的悬停事件。

    支持 3 种 action 类型。``to_dict()`` 仅输出当前 action 对应的字段。

    Attributes:
        action: 悬停行为类型，为 ``HOVER_ACTIONS`` 之一。
        value: 用于 ``show_text``，要显示的文本组件或纯文本字符串。
        id: 用于 ``show_item`` / ``show_entity``，物品/实体类型命名空间 ID。
        count: 用于 ``show_item``，物品堆叠数。
        components: 用于 ``show_item``，物品数据组件修订字典。
        name: 用于 ``show_entity``，实体的显示名称（文本组件或字符串，不可预解析）。
        uuid: 用于 ``show_entity``，实体的 UUID（字符串或 4 整数列表）。
    """

    action: str
    value: TextComponent | str | None = None
    id: str | None = None
    count: int | None = None
    components: dict | None = None
    name: TextComponent | str | None = None
    uuid: str | list[int] | None = None

    def to_dict(self) -> dict:
        """转换为 JSON 可序列化的字典。

        仅包含 ``action`` 及当前 action 对应的非 None 字段。
        TextComponent 类型的字段自动调用其 ``to_dict()``。
        """
        result: dict[str, Any] = {"action": self.action}
        for field_name in _HOVER_ACTION_FIELDS.get(self.action, []):
            value = getattr(self, field_name, None)
            if value is None:
                continue
            if isinstance(value, TextComponent):
                result[field_name] = value.to_dict()
            else:
                result[field_name] = value
        return result

    @classmethod
    def from_dict(cls, data: dict) -> HoverEvent:
        """从字典反序列化 HoverEvent。

        按 ``data["action"]`` 确定类型并读取对应字段。
        ``show_text`` 的 ``value`` 和 ``show_entity`` 的 ``name`` 字段
        若为 dict 则自动解析为 TextComponent。
        """
        action = data.get("action", "")
        kwargs: dict[str, Any] = {"action": action}

        for field_name in _HOVER_ACTION_FIELDS.get(action, []):
            if field_name not in data:
                continue
            raw = data[field_name]
            if field_name in ("value", "name") and isinstance(raw, dict):
                kwargs[field_name] = TextComponent.from_dict(raw)
            else:
                kwargs[field_name] = raw

        return cls(**kwargs)


# ═══════════════════════════════════════════════════════════════
#  TextComponent — 文本组件主数据类
# ═══════════════════════════════════════════════════════════════


@dataclass
class TextComponent:
    """Minecraft Java 版文本组件。

    支持全部 7 种组件类型、完整样式系统、点击/悬停事件及子组件继承。
    采用单 dataclass 含所有字段的设计，通过 ``type`` 字段或自动推断确定组件类型。
    ``to_dict()`` 自动选择三种输出形式中最简便的一种。

    **组件类型及专属字段：**

    - ``text``：``text``
    - ``translatable``：``translate``, ``fallback``, ``with_list``
    - ``keybind``：``keybind``
    - ``score``：``score`` (dict: ``{name, objective}``)
    - ``selector``：``selector``, ``separator``
    - ``nbt``：``nbt``, ``interpret``, ``plain``, ``source``,
      ``entity``, ``block``, ``storage``
    - ``object``：``obj_type``, ``sprite``, ``player``
    """

    # ── 组件类型标识 ──
    type: str | None = None
    """组件类型。None 时自动推断。可选值见 ``COMPONENT_TYPES``。"""

    # ── text 类型 ──
    text: str = ""
    """纯文本内容。text 类型的核心字段。"""

    # ── translatable 类型 ──
    translate: str | None = None
    """本地化键名。translatable 类型的核心字段。"""
    fallback: str | None = None
    """回落文本。本地化查询失败时使用。"""
    with_list: list | None = None
    """替换参数列表。元素可为 TextComponent / str / int / float / bool。"""

    # ── keybind 类型 ──
    keybind: str | None = None
    """键位绑定标识符，如 ``"key.inventory"``。"""

    # ── score 类型 ──
    score: dict | None = None
    """记分板信息。格式：``{"name": "...", "objective": "..."}``。
    name 可为选择器/玩家名/UUID/``"*"``。"""

    # ── selector 类型 ──
    selector: str | None = None
    """目标选择器、玩家名称或 UUID。"""
    separator: TextComponent | None = None
    """多实体名称间的分隔符，None 时游戏默认灰色逗号。"""

    # ── nbt 类型 ──
    nbt: str | None = None
    """NBT 路径。"""
    interpret: bool | None = None
    """是否将 NBT 数据解析为文本组件。"""
    plain: bool | None = None
    """interpret 为 false 时，是否输出简单单一文本（无语法高亮）。"""
    source: str | None = None
    """NBT 数据源类型校验标签：``"entity"`` / ``"block"`` / ``"storage"``。"""
    entity: str | None = None
    """NBT 数据源：实体选择器/玩家名/UUID。"""
    block: str | None = None
    """NBT 数据源：方块位置参数。"""
    storage: str | None = None
    """NBT 数据源：命令存储命名空间 ID。"""

    # ── object（精灵图）类型 ──
    obj_type: str | None = None
    """精灵图子类型：``"atlas"`` 或 ``"player"``。JSON 中对应 ``object`` 字段。"""
    sprite: dict | None = None
    """纹理图集精灵图规格 ``{"atlas": ..., "sprite": ...}``。"""
    player: str | dict | None = None
    """玩家皮肤名称或 ``{"name": ..., "hat": ...}`` 配置。"""

    # ── 样式字段 ──
    color: str | None = None
    """文字渲染颜色。支持具名颜色（``"red"``）和十六进制（``"#FF0000"``）。"""
    shadow_color: int | None = None
    """文本阴影颜色（ARGB 整数）。"""
    font: str | None = None
    """渲染字体命名空间 ID，默认 ``"minecraft:default"``。"""
    bold: bool | None = None
    """粗体。"""
    italic: bool | None = None
    """斜体。"""
    underlined: bool | None = None
    """下划线。"""
    strikethrough: bool | None = None
    """删除线。"""
    obfuscated: bool | None = None
    """随机字符（乱码效果）。"""

    # ── 交互字段 ──
    insertion: str | None = None
    """按住 ⇧ Shift 并点击时插入聊天栏的文本。"""
    click_event: ClickEvent | None = None
    """点击事件。"""
    hover_event: HoverEvent | None = None
    """悬停事件。"""

    # ── 组件继承 ──
    extra: list[TextComponent] = field(default_factory=list)
    """子组件列表。子组件继承父组件的样式信息。"""

    # ═══════════════════════════════════════════════════════════
    #  内部辅助
    # ═══════════════════════════════════════════════════════════

    def _resolve_type(self) -> str:
        """确定当前组件的有效类型。

        若 ``type`` 已显式指定则直接返回；否则按优先级遍历各类型的特征字段，
        返回第一个特征值非 None 的类型。若所有特征均为 None 则返回 ``"text"``。
        """
        if self.type is not None:
            return self.type
        for comp_type in COMPONENT_TYPES:
            marker = _TYPE_MARKERS.get(comp_type)
            if marker is not None and getattr(self, marker, None) is not None:
                return comp_type
        return "text"

    def _has_any_style(self) -> bool:
        """检查是否有任何样式字段非 None。"""
        style_attrs = (
            "color",
            "shadow_color",
            "font",
            "bold",
            "italic",
            "underlined",
            "strikethrough",
            "obfuscated",
            "insertion",
        )
        return any(getattr(self, a) is not None for a in style_attrs)

    # ═══════════════════════════════════════════════════════════
    #  to_dict() — 序列化
    # ═══════════════════════════════════════════════════════════

    def to_dict(self) -> str | dict:
        """将文本组件转换为 JSON 可序列化的字符串或字典。

        自动选择三种输出形式中最简便的一种：

        - **形式① 纯字符串**：纯 ``text`` 类型、无样式/事件、无 extra → ``str``
        - **形式② 单组件复合标签**：任意类型，无 extra → ``dict``
        - **形式③ 多样式复合标签**：任意类型，有 extra → ``dict``（含 ``extra`` 列表）
        """
        comp_type = self._resolve_type()
        result: dict[str, Any] = {}

        # ── 写入内容字段 ──
        self._write_content_fields(result, comp_type)

        # ── 写入样式字段 ──
        self._write_style_fields(result)

        # ── 写入交互字段 ──
        if self.click_event is not None:
            result["click_event"] = self.click_event.to_dict()
        if self.hover_event is not None:
            result["hover_event"] = self.hover_event.to_dict()

        # ── 写入子组件 ──
        if self.extra:
            result["extra"] = [child.to_dict() for child in self.extra]

        # ── 判定输出形式 ──
        # 形式①：纯 text 类型 + text 非空 + 无样式/事件 + 无 extra
        if (
            comp_type == "text"
            and self.text
            and not self._has_any_style()
            and self.click_event is None
            and self.hover_event is None
            and not self.extra
        ):
            return self.text

        return result

    def _write_content_fields(self, result: dict, comp_type: str) -> None:
        """按组件类型将非 None 的内容字段写入 result。"""
        if comp_type == "text":
            result["text"] = self.text

        elif comp_type == "translatable":
            result["translate"] = self.translate
            if self.fallback is not None:
                result["fallback"] = self.fallback
            if self.with_list is not None:
                result["with"] = [
                    item.to_dict() if isinstance(item, TextComponent) else item
                    for item in self.with_list
                ]

        elif comp_type == "keybind":
            result["keybind"] = self.keybind

        elif comp_type == "score":
            result["score"] = self.score

        elif comp_type == "selector":
            result["selector"] = self.selector
            if self.separator is not None:
                result["separator"] = self.separator.to_dict()

        elif comp_type == "nbt":
            result["nbt"] = self.nbt
            if self.interpret is not None:
                result["interpret"] = self.interpret
            if self.plain is not None:
                result["plain"] = self.plain
            if self.separator is not None:
                result["separator"] = self.separator.to_dict()
            if self.source is not None:
                result["source"] = self.source
            if self.entity is not None:
                result["entity"] = self.entity
            if self.block is not None:
                result["block"] = self.block
            if self.storage is not None:
                result["storage"] = self.storage

        elif comp_type == "object":
            result["object"] = self.obj_type
            if self.fallback is not None:
                result["fallback"] = self.fallback
            if self.obj_type == "atlas" and self.sprite is not None:
                result["sprite"] = self.sprite
            elif self.obj_type == "player" and self.player is not None:
                result["player"] = self.player

    def _write_style_fields(self, result: dict) -> None:
        """将非 None 的样式字段写入 result。"""
        _write_if_set(result, "color", self.color)
        _write_if_set(result, "shadow_color", self.shadow_color)
        _write_if_set(result, "font", self.font)
        _write_if_set(result, "bold", self.bold)
        _write_if_set(result, "italic", self.italic)
        _write_if_set(result, "underlined", self.underlined)
        _write_if_set(result, "strikethrough", self.strikethrough)
        _write_if_set(result, "obfuscated", self.obfuscated)
        _write_if_set(result, "insertion", self.insertion)

    # ═══════════════════════════════════════════════════════════
    #  from_dict() — 反序列化
    # ═══════════════════════════════════════════════════════════

    @classmethod
    def from_dict(cls, data: str | dict) -> TextComponent:
        """从字符串或字典反序列化文本组件。

        Args:
            data: 字符串（纯文本组件）或字典（复合标签）。

        Returns:
            解析后的 TextComponent 实例。

        自动检测组件类型（按优先级遍历特征字段），解析样式、交互事件，
        并递归解析 ``extra`` 子组件。
        """
        if isinstance(data, str):
            return cls(text=data)

        comp = cls()

        # 显式 type 字段
        comp.type = data.get("type")

        # 按优先级检测特征字段并解析内容
        for comp_type in COMPONENT_TYPES:
            marker = _TYPE_MARKERS.get(comp_type)
            if marker is not None and marker in data:
                cls._parse_content_fields(comp, comp_type, data)
                break

        # ── 解析样式字段 ──
        for style_key in (
            "color",
            "shadow_color",
            "font",
            "bold",
            "italic",
            "underlined",
            "strikethrough",
            "obfuscated",
            "insertion",
        ):
            if style_key in data:
                setattr(comp, style_key, data[style_key])

        # ── 解析交互字段 ──
        if "click_event" in data:
            comp.click_event = ClickEvent.from_dict(data["click_event"])
        if "hover_event" in data:
            comp.hover_event = HoverEvent.from_dict(data["hover_event"])

        # ── 递归解析子组件 ──
        if "extra" in data:
            comp.extra = [cls.from_dict(item) for item in data["extra"]]

        return comp

    @classmethod
    def _parse_content_fields(
        cls, comp: TextComponent, comp_type: str, data: dict
    ) -> None:
        """按组件类型从 data 读取内容字段到 comp 实例。"""
        if comp_type == "text":
            comp.text = data.get("text", "")

        elif comp_type == "translatable":
            comp.translate = data.get("translate")
            comp.fallback = data.get("fallback")
            if "with" in data:
                comp.with_list = [
                    cls.from_dict(item) if isinstance(item, dict) else item
                    for item in data["with"]
                ]

        elif comp_type == "keybind":
            comp.keybind = data.get("keybind")

        elif comp_type == "score":
            comp.score = data.get("score")

        elif comp_type == "selector":
            comp.selector = data.get("selector")
            if "separator" in data and isinstance(data["separator"], dict):
                comp.separator = cls.from_dict(data["separator"])

        elif comp_type == "nbt":
            comp.nbt = data.get("nbt")
            comp.interpret = data.get("interpret")
            comp.plain = data.get("plain")
            if "separator" in data and isinstance(data["separator"], dict):
                comp.separator = cls.from_dict(data["separator"])
            comp.source = data.get("source")
            comp.entity = data.get("entity")
            comp.block = data.get("block")
            comp.storage = data.get("storage")

        elif comp_type == "object":
            comp.obj_type = data.get("object")
            comp.fallback = data.get("fallback")
            if "sprite" in data:
                comp.sprite = data["sprite"]
            if "player" in data:
                comp.player = data["player"]

    # ═══════════════════════════════════════════════════════════
    #  工厂类方法 — 按类型快速构建
    # ═══════════════════════════════════════════════════════════

    @classmethod
    def from_string(cls, s: str) -> TextComponent:
        """从纯文本字符串创建纯文本组件。等价于 ``TextComponent(text=s)``。"""
        return cls(text=s)

    @classmethod
    def translatable(
        cls,
        key: str,
        fallback: str | None = None,
        with_list: list | None = None,
    ) -> TextComponent:
        """创建本地化文本组件。

        Args:
            key: 本地化键名，如 ``"commands.op.success"``。
            fallback: 回落文本。
            with_list: 替换参数列表，元素可为 TextComponent/str/int/float/bool。
        """
        return cls(translate=key, fallback=fallback, with_list=with_list)

    @classmethod
    def keybinding(cls, key: str) -> TextComponent:
        """创建键位绑定组件。

        Args:
            key: 键位绑定标识符，如 ``"key.inventory"``。
        """
        return cls(keybind=key)

    @classmethod
    def from_score(cls, name: str, objective: str) -> TextComponent:
        """创建记分板数据组件。

        Args:
            name: 分数持有者（选择器/玩家名/UUID/``"*"``）。
            objective: 记分项名称。
        """
        return cls(score={"name": name, "objective": objective})

    @classmethod
    def from_selector(
        cls,
        selector: str,
        separator: TextComponent | None = None,
    ) -> TextComponent:
        """创建实体名称组件。

        Args:
            selector: 目标选择器、玩家名称或 UUID。
            separator: 多实体名称间的分隔符。
        """
        return cls(selector=selector, separator=separator)

    @classmethod
    def from_nbt(
        cls,
        nbt_path: str,
        source: str = "entity",
        entity: str | None = None,
        block: str | None = None,
        storage: str | None = None,
        interpret: bool | None = None,
        plain: bool | None = None,
        separator: TextComponent | None = None,
    ) -> TextComponent:
        """创建 NBT 数据组件。

        Args:
            nbt_path: NBT 路径，如 ``"CustomName"``。
            source: 数据源类型 ``"entity"`` / ``"block"`` / ``"storage"``。
            entity: 实体选择器/玩家名/UUID。
            block: 方块位置参数。
            storage: 命令存储命名空间 ID。
            interpret: 是否将 NBT 数据解析为文本组件。
            plain: 是否输出简单单一文本（无语法高亮）。
            separator: 多项数据间的分隔符。
        """
        return cls(
            nbt=nbt_path,
            source=source,
            entity=entity,
            block=block,
            storage=storage,
            interpret=interpret,
            plain=plain,
            separator=separator,
        )

    @classmethod
    def from_sprite(
        cls,
        atlas: str,
        sprite_id: str,
        fallback: str | None = None,
    ) -> TextComponent:
        """创建纹理图集精灵图组件。

        Args:
            atlas: 纹理图集命名空间 ID，如 ``"blocks"``。
            sprite_id: 精灵图命名空间 ID。
            fallback: 渲染失败时的回落文本。
        """
        return cls(
            obj_type="atlas",
            sprite={"atlas": atlas, "sprite": sprite_id},
            fallback=fallback,
        )

    @classmethod
    def player_head(
        cls,
        player_name: str,
        hat: bool = True,
        fallback: str | None = None,
    ) -> TextComponent:
        """创建玩家皮肤精灵图组件（玩家头像）。

        Args:
            player_name: 玩家名称。
            hat: 是否渲染皮肤"帽子"层，默认 True。
            fallback: 渲染失败时的回落文本。
        """
        return cls(
            obj_type="player",
            player={"name": player_name, "hat": hat},
            fallback=fallback,
        )

    # ═══════════════════════════════════════════════════════════
    #  实例便捷方法（链式调用）
    # ═══════════════════════════════════════════════════════════

    def add_child(self, child: TextComponent) -> TextComponent:
        """向 extra 末尾添加子组件，返回 self 以支持链式调用。

        等价于 ``self.extra.append(child); return self``。
        """
        self.extra.append(child)
        return self

    def set_style(
        self,
        color: str | None = None,
        shadow_color: int | None = None,
        font: str | None = None,
        bold: bool | None = None,
        italic: bool | None = None,
        underlined: bool | None = None,
        strikethrough: bool | None = None,
        obfuscated: bool | None = None,
        insertion: str | None = None,
    ) -> TextComponent:
        """批量设置样式字段，返回 self 以支持链式调用。

        仅传入非 None 的参数会被更新，未传入的保持原值不变。
        """
        if color is not None:
            self.color = color
        if shadow_color is not None:
            self.shadow_color = shadow_color
        if font is not None:
            self.font = font
        if bold is not None:
            self.bold = bold
        if italic is not None:
            self.italic = italic
        if underlined is not None:
            self.underlined = underlined
        if strikethrough is not None:
            self.strikethrough = strikethrough
        if obfuscated is not None:
            self.obfuscated = obfuscated
        if insertion is not None:
            self.insertion = insertion
        return self

    def with_click_event(self, action: str, **kwargs: Any) -> TextComponent:
        """设置点击事件，返回 self 以支持链式调用。

        等价于 ``self.click_event = ClickEvent(action=action, **kwargs)``。
        """
        self.click_event = ClickEvent(action=action, **kwargs)
        return self

    def with_hover_event(self, action: str, **kwargs: Any) -> TextComponent:
        """设置悬停事件，返回 self 以支持链式调用。

        等价于 ``self.hover_event = HoverEvent(action=action, **kwargs)``。
        """
        self.hover_event = HoverEvent(action=action, **kwargs)
        return self


# ═══════════════════════════════════════════════════════════════
#  模块级辅助函数
# ═══════════════════════════════════════════════════════════════


def _write_if_set(result: dict, key: str, value: Any) -> None:
    """仅当 value 不为 None 时写入 result[key] = value。"""
    if value is not None:
        result[key] = value
