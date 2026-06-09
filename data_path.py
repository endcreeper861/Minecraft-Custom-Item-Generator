"""
DataPath — 统一的数据路径导航器。

替代 component.py 中原有的四个内部函数和 getter/setter/clearer 回调模式。
每次操作实时从 Item.components 读取，杜绝闭包捕获旧引用的问题。
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from item import Item

logger = logging.getLogger(__name__)


class DataPath:
    """ "封装"在 Item.components 树中导航到某个节点"的全部逻辑。

    两种模式：
    1. **组件模式**：通过 ``(item, component_id, field_keys)`` 定位到
       ``item.components[component_id][key1][key2]...``
    2. **分离模式**：通过 ``DataPath.on_dict(root_dict)`` 创建，直接操作一个
       独立的 dict（用于列表项等不与 Item 直接绑定的嵌套数据）。

    核心保证：
    - 每次 read/write/delete 都实时访问底层数据，绝不缓存引用
    - write 自动创建中间容器，类型不匹配时警告并修正
    """

    __slots__ = (
        "_item",
        "_component_id",
        "_field_keys",
        "_root_dict",  # 仅分离模式使用
    )

    def __init__(
        self,
        item: Item,
        component_id: str,
        field_keys: tuple[str, ...] = (),
    ) -> None:
        """组件模式：绑定到 Item 的某个数据组件路径。

        Args:
            item: 目标 Item 实例
            component_id: 数据组件 ID（如 ``"food"``, ``"max_stack_size"``）
            field_keys: 嵌套字段路径（如 ``("nutrition",)``）
        """
        self._item: Item | None = item
        self._component_id: str | None = component_id
        self._field_keys: tuple[str, ...] = tuple(field_keys)
        self._root_dict: dict | None = None

    @classmethod
    def on_dict(cls, root: dict, field_keys: tuple[str, ...] = ()) -> DataPath:
        """分离模式：直接操作一个独立 dict（用于列表项的嵌套数据）。

        Args:
            root: 要绑定的 dict 对象
            field_keys: 嵌套字段路径
        """
        dp = cls.__new__(cls)
        dp._item = None
        dp._component_id = None
        dp._field_keys = tuple(field_keys)
        dp._root_dict = root
        return dp

    # ── 内部导航 ──────────────────────────────────────────────

    def _resolve_root(self) -> dict | list | None:
        """获取当前路径的根容器（component_id 层级）。"""
        if self._item is None:
            return self._root_dict
        return self._item.components.get(self._component_id)  # type: ignore[arg-type]

    def _navigate(self) -> tuple[dict | list | None, str | None, dict | None]:
        """导航到当前路径的父容器和最后一个键。

        Returns:
            (parent_container, last_key, leaf_value)
            - parent_container: 最后一个键的父容器（dict 或 list）
            - last_key: 最后一个字段键名，field_keys 为空时为 None
            - leaf_value: 当前路径的值（可能为 None）
        """
        current: Any = self._resolve_root()

        if not self._field_keys:
            return None, None, current

        parent: dict | None = None
        last_key: str | None = None

        for i, key in enumerate(self._field_keys):
            if not isinstance(current, dict):
                return None, key, None
            parent = current
            last_key = key
            if i < len(self._field_keys) - 1:
                current = current.get(key)
            else:
                # 最后一个 key
                return parent, key, current.get(key)

        return parent, last_key, None

    def _current_dict(self) -> dict | None:
        """获取当前路径所在的 dict 容器（遍历 field_keys 后的叶子 dict）。"""
        if not self._field_keys:
            root = self._resolve_root()
            return root if isinstance(root, dict) else None
        _, _, leaf = self._navigate()
        return leaf if isinstance(leaf, dict) else None

    def _ensure_container(self, key: str, expected_type: type) -> dict | list:
        """确保指定 key 处的容器存在且类型正确。"""
        container = self._current_dict()
        if container is None:
            return expected_type()

        existing = container.get(key)
        if isinstance(existing, expected_type):
            return existing  # type: ignore

        if existing is not None:
            logger.warning(
                "组件容器类型不匹配: %s.%s 期望 %s, 实际 %s，已自动修正",
                self._component_id,
                ".".join(self._field_keys + (key,)),
                expected_type.__name__,
                type(existing).__name__,
            )
        new_container = expected_type()
        container[key] = new_container
        return new_container

    # ── 公共接口 ──────────────────────────────────────────────

    def read(self) -> Any:
        """读取当前路径的值。不存在时返回 None。"""
        if not self._field_keys:
            return self._resolve_root()
        _, _, value = self._navigate()
        return value

    def write(self, value: Any) -> None:
        """写入值到当前路径。自动创建中间容器。"""
        if not self._field_keys:
            # 根级别写入：item.components[component_id] = value
            if self._item is not None:
                self._item.components[self._component_id] = value  # type: ignore[index]
            else:
                # 分离模式不支持根级别替换（应使用 child 导航）
                logger.warning("DataPath.on_dict 不支持根级别 write，请使用 child()")
            return

        parent, last_key, _ = self._navigate()

        # 如果中间路径不存在，逐级创建
        if parent is None:
            root = self._resolve_root()
            if root is None or not isinstance(root, dict):
                # 根不存在或类型不对：在 item.components 上创建
                if self._item is not None:
                    root = {}
                    self._item.components[self._component_id] = root  # type: ignore[index]
                elif self._root_dict is not None:
                    root = self._root_dict
                else:
                    return

            current: Any = root
            for i, key in enumerate(self._field_keys):
                if i == len(self._field_keys) - 1:
                    # 最后一个 key：设置值
                    if isinstance(current, dict):
                        current[key] = value
                    return
                # 中间 key：确保存在 dict 容器
                if not isinstance(current, dict):
                    return
                child = current.get(key)
                if not isinstance(child, dict):
                    child = {}
                    current[key] = child
                current = child
            return

        if isinstance(parent, dict) and last_key is not None:
            parent[last_key] = value

    def delete(self) -> None:
        """删除当前路径的值。"""
        if not self._field_keys:
            # 根级别删除
            if self._item is not None:
                self._item.components.pop(self._component_id, None)  # type: ignore[arg-type]
            return

        parent, last_key, _ = self._navigate()
        if isinstance(parent, dict) and last_key is not None:
            parent.pop(last_key, None)

    def child(self, key: str, ensure_type: type | None = None) -> DataPath:
        """创建子路径。

        Args:
            key: 子字段键名
            ensure_type: 若指定，确保该 key 处的容器为 dict 或 list 类型
        """
        if ensure_type is not None:
            # 确保当前节点存在（否则无法在它上面创建子容器）
            if self._current_dict() is None:
                self.write({})
            self._ensure_container(key, ensure_type)

        if self._item is not None:
            # 组件模式：追加 field_key
            return DataPath(self._item, self._component_id, self._field_keys + (key,))  # type: ignore[arg-type]
        else:
            # 分离模式：也用 field_keys 路径导航，保持与 write/read/delete 一致
            # 注意：不可用 "or {}"，空 dict 是 falsy 的！
            root = self._root_dict if self._root_dict is not None else {}
            return DataPath.on_dict(root, self._field_keys + (key,))

    def ensure_list(self, key: str) -> list:
        """确保指定 key 处为 list 类型并返回该 list。"""
        return self._ensure_container(key, list)  # type: ignore[return-value]

    def ensure_dict(self, key: str) -> dict:
        """确保指定 key 处为 dict 类型并返回该 dict。"""
        return self._ensure_container(key, dict)  # type: ignore[return-value]

    def read_list(self) -> list | None:
        """读取当前路径的值，确保为 list 类型。"""
        value = self.read()
        if isinstance(value, list):
            return value
        if value is not None:
            logger.warning(
                "组件根类型不匹配: %s 期望 list, 实际 %s",
                self._component_id,
                type(value).__name__,
            )
        return None

    def read_dict(self) -> dict | None:
        """读取当前路径的值，确保为 dict 类型。"""
        value = self.read()
        if isinstance(value, dict):
            return value
        if value is not None:
            logger.warning(
                "组件根类型不匹配: %s 期望 dict, 实际 %s",
                self._component_id,
                type(value).__name__,
            )
        return None

    # ── 属性访问 ──────────────────────────────────────────────

    @property
    def component_id(self) -> str | None:
        return self._component_id

    @property
    def field_keys(self) -> tuple[str, ...]:
        return self._field_keys
