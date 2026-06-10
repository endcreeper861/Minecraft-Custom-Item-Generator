"""
组件 Widget 构建器 —— 将 JSON 组件定义渲染为 PyQt6 界面。

通过 DataPath 统一数据绑定，彻底消除闭包式 getter/setter/clearer 回调。
每种组件类型封装为独立的 Widget Builder 类。
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from PyQt6.QtWidgets import (QCheckBox, QComboBox, QDialog, QGroupBox,
                             QHBoxLayout, QLabel, QLineEdit, QPushButton,
                             QVBoxLayout)

import utils
from data_path import DataPath

if TYPE_CHECKING:
    from item import Item

logger = logging.getLogger(__name__)

# ── 标量类型集合（列表项内联处理用） ─────────────────────────

_SCALAR_TYPES = {"int", "float", "string", "text_component", "bool", "simple_enum"}


# ═══════════════════════════════════════════════════════════════
#  Base Class
# ═══════════════════════════════════════════════════════════════


class ComponentWidget:
    """组件 Widget 构建器基类。

    Args:
        data: JSON 组件定义
        path: 数据绑定路径
    """

    def __init__(self, data: dict, path: DataPath) -> None:
        self.data = data
        self.path = path

    def build(self) -> QHBoxLayout:
        """构建 UI 并返回布局。子类必须实现。"""
        raise NotImplementedError

    # ── 便捷方法 ──

    def _desc(self) -> str:
        return self.data.get("description", "")

    def _default(self):
        return self.data.get("default")

    def _placeholder(self) -> str:
        return self.data.get("place_holder_text", "")


# ═══════════════════════════════════════════════════════════════
#  Scalar Widgets
# ═══════════════════════════════════════════════════════════════


class IntFloatWidget(ComponentWidget):
    """int / float 数值输入。"""

    def build(self) -> QHBoxLayout:
        layout = QHBoxLayout()
        layout.addWidget(QLabel(self._desc() + "："))

        input_field = QLineEdit()
        placeholder = self._placeholder()
        if placeholder:
            input_field.setPlaceholderText(placeholder)
        layout.addWidget(input_field)

        field_type = self.data["type"]

        # 从已有数据还原初始值
        existing = self.path.read()
        if existing is not None:
            try:
                if field_type == "int":
                    _ = int(existing)
                else:
                    _ = float(existing)
                input_field.setText(str(existing))
            except (ValueError, TypeError):
                pass

        def on_text_changed(text: str) -> None:
            text_value = text.strip()
            if not text_value:
                self.path.delete()
                return
            try:
                parsed = int(text_value) if field_type == "int" else float(text_value)
            except ValueError:
                return
            self.path.write(parsed)

        input_field.textChanged.connect(on_text_changed)
        layout.addStretch()
        return layout


class BoolWidget(ComponentWidget):
    """bool 复选框。"""

    def build(self) -> QHBoxLayout:
        layout = QHBoxLayout()

        # 优先从已有数据读取，回退到组件定义的默认值
        existing = self.path.read()
        if existing is not None:
            initial = bool(existing)
        else:
            initial = bool(self._default())

        check_box = QCheckBox(self._desc())
        check_box.setChecked(initial)
        layout.addWidget(check_box)

        def on_state_changed() -> None:
            self.path.write(check_box.isChecked())

        check_box.stateChanged.connect(on_state_changed)
        layout.addStretch()
        return layout


class TextComponentWidget(ComponentWidget):
    """text_component 富文本编辑器入口。

    使用 ``TextEditorDialog`` 编辑 Minecraft JSON 文本组件，
    替代原来的纯文本 QLineEdit。
    """

    def build(self) -> QHBoxLayout:
        layout = QHBoxLayout()
        layout.addWidget(QLabel(self._desc() + "："))

        # 预览文本框（只读，显示当前文本组件的纯文本摘要）
        self._preview = QLineEdit()
        self._preview.setReadOnly(True)
        self._preview.setPlaceholderText("(空)")
        layout.addWidget(self._preview, stretch=1)

        # 编辑按钮
        edit_btn = QPushButton("编辑...")
        edit_btn.clicked.connect(self._open_editor)
        layout.addWidget(edit_btn)

        # 清除按钮
        clear_btn = QPushButton("✕")
        clear_btn.setFixedWidth(28)
        clear_btn.setToolTip("清除文本组件")
        clear_btn.clicked.connect(self._clear)
        layout.addWidget(clear_btn)

        # 加载当前值
        self._refresh_preview()

        return layout

    def _refresh_preview(self) -> None:
        """从 DataPath 读取当前值并更新预览。"""
        current = self.path.read()
        if current is None:
            self._preview.setText("")
            self._preview.setPlaceholderText("(空)")
            return

        # 生成纯文本摘要
        from text import TextComponent
        if isinstance(current, str):
            preview = current[:60]
        elif isinstance(current, dict):
            tc = TextComponent.from_dict(current)
            preview = self._plain_text_summary(tc)[:60]
        else:
            preview = str(current)[:60]

        self._preview.setText(preview)

    @staticmethod
    def _plain_text_summary(tc) -> str:
        """递归收集 TextComponent 树中所有纯文本。"""
        from text import TextComponent
        parts: list[str] = []
        if tc.text:
            parts.append(tc.text)
        # 收集子组件文本
        for child in tc.extra:
            if isinstance(child, TextComponent):
                parts.append(TextComponentWidget._plain_text_summary(child))
        # 占位符用类型名显示
        for attr, label in [
            ("translate", "翻译"), ("keybind", "按键"),
            ("selector", "实体"), ("nbt", "NBT"),
        ]:
            val = getattr(tc, attr, None)
            if val:
                parts.append(f"[{label}:{val}]")
        if tc.score:
            s = tc.score
            parts.append(f"[记分板:{s.get('name','?')}.{s.get('objective','?')}]")
        if tc.obj_type:
            parts.append(f"[精灵图:{tc.obj_type}]")
        return "".join(parts)

    def _open_editor(self) -> None:
        """打开 TextEditorDialog 编辑文本组件。"""
        from text_editor import TextEditorDialog

        current = self.path.read()
        # 规范化输入：DataPath 可能返回 str 或 dict
        dlg = TextEditorDialog.from_dict(None, current)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            result = dlg.to_dict()
            # 如果结果为空字符串，删除此组件
            if result == "" or (isinstance(result, dict) and not result):
                self.path.delete()
            else:
                self.path.write(result)
            self._refresh_preview()

    def _clear(self) -> None:
        """清除文本组件。"""
        self.path.delete()
        self._preview.setText("")
        self._preview.setPlaceholderText("(空)")


class StringWidget(ComponentWidget):
    """string / block_filter 文本输入。

    TODO: block_filter 未来需特殊输入组件
    """

    def build(self) -> QHBoxLayout:
        layout = QHBoxLayout()
        layout.addWidget(QLabel(self._desc() + "："))

        input_field = QLineEdit()
        placeholder = self._placeholder()
        if placeholder:
            input_field.setPlaceholderText(placeholder)
        layout.addWidget(input_field)

        def on_text_changed(text: str) -> None:
            if not text:
                self.path.delete()
                return
            self.path.write(text)

        input_field.textChanged.connect(on_text_changed)

        # 优先从已有数据读取初始值，回退到组件定义的默认值
        existing = self.path.read()
        if existing is not None:
            input_field.setText(str(existing))
        else:
            default = self._default()
            if default is not None:
                default_str = str(default)
                input_field.setText(default_str)

        layout.addStretch()
        return layout


class SimpleEnumWidget(ComponentWidget):
    """simple_enum 下拉框。"""

    def build(self) -> QHBoxLayout:
        layout = QHBoxLayout()
        layout.addWidget(QLabel(self._desc() + "："))

        values: dict = self.data.get("values", {})
        combo_box = QComboBox()
        combo_box.addItems(values.keys())
        layout.addWidget(combo_box)

        def on_changed(text: str) -> None:
            value = values.get(text, text)
            self.path.write(value)

        combo_box.currentTextChanged.connect(on_changed)

        # 优先从已有数据读取初始值，回退到组件定义的默认值
        existing = self.path.read()
        if existing is not None:
            # 反向查找：根据值找到显示名
            found = False
            for display_text, val in values.items():
                if val == existing:
                    combo_box.setCurrentText(display_text)
                    found = True
                    break
            if not found:
                # 值不在可选项中，仍写入但不改变选择
                pass
        else:
            default = self._default()
            if default is not None:
                default_str = str(default)
                combo_box.setCurrentText(default_str)

        layout.addStretch()
        return layout


# ═══════════════════════════════════════════════════════════════
#  Container Widgets
# ═══════════════════════════════════════════════════════════════


class DictWidget(ComponentWidget):
    """dict 嵌套字段组。有 description 时包裹 QGroupBox。"""

    def build(self) -> QHBoxLayout:
        layout = QHBoxLayout()
        values: dict[str, dict] = self.data.get("values", {})
        description = self._desc()

        if description:
            # 有描述 → 包裹在 GroupBox 中
            group_box = QGroupBox(description)
            inner = QVBoxLayout(group_box)
            inner.setContentsMargins(10, 0, 10, 10)
            inner.setSpacing(10)
            self._populate_fields(inner, values)
            layout.addWidget(group_box)
        else:
            # 无描述 → 直接放入当前布局
            inner = QVBoxLayout()
            self._populate_fields(inner, values)
            layout.addLayout(inner)

        return layout

    def _populate_fields(
        self, parent_layout: QVBoxLayout, values: dict[str, dict]
    ) -> None:
        """遍历 dict 的各个字段并递归加载。"""
        for key, field_def in values.items():
            field_type = field_def.get("type")

            if field_type in {"dict", "enum"}:
                child_path = self.path.child(key, ensure_type=dict)
                parent_layout.addLayout(
                    load_component(field_def, None, None, path=child_path)
                )
            elif field_type == "list":
                child_path = self.path.child(key, ensure_type=list)
                parent_layout.addLayout(
                    load_component(field_def, None, None, path=child_path)
                )
            else:
                child_path = self.path.child(key)
                parent_layout.addLayout(
                    load_component(field_def, None, None, path=child_path)
                )


class ConditionalEnumWidget(ComponentWidget):
    """条件枚举 —— 选择改变时动态替换子组件区域。"""

    def build(self) -> QHBoxLayout:
        layout = QHBoxLayout()
        group = QVBoxLayout()

        # 下拉框行
        combo_row = QHBoxLayout()
        group.addLayout(combo_row)
        combo_row.addWidget(QLabel(self._desc() + "："))

        values: dict = self.data.get("values", {})
        combo_box = QComboBox()
        combo_box.addItems(values.keys())
        combo_row.addWidget(combo_box)
        combo_row.addStretch()

        # 子组件区域
        sub_layout = QVBoxLayout()
        group.addLayout(sub_layout)

        def on_selection_changed(text: str) -> None:
            selected = values[text]
            selected_id = selected.get("id", text)

            # 写入/更新 type 标识
            target = self.path.read_dict()
            if target is not None:
                # 仅当类型真正改变时才清空旧字段（保留加载还原时的已有数据）
                if target.get("type") != selected_id:
                    target.clear()
                    target["type"] = selected_id
            else:
                self.path.write({"type": selected_id})

            # 重建子组件
            utils.clear_layout(sub_layout)
            if "components" in selected:
                child_layout = load_component(
                    selected["components"], None, None, path=self.path
                )
                sub_layout.addLayout(child_layout)

        # 初始化：优先从已有数据恢复选中项
        existing = self.path.read_dict()
        if existing and "type" in existing:
            for display_text, option in values.items():
                if option.get("id") == existing["type"]:
                    combo_box.setCurrentText(display_text)
                    break

        # 初始化子组件（此时 combo 已指向正确类型，on_selection_changed 不会清空已有数据）
        on_selection_changed(combo_box.currentText())
        combo_box.currentTextChanged.connect(on_selection_changed)

        layout.addLayout(group)
        return layout


class ListWidget(ComponentWidget):
    """动态列表 —— 支持标量列表和字典列表。"""

    def build(self) -> QHBoxLayout:
        layout = QHBoxLayout()
        group_box = QGroupBox(self._desc())
        outer = QVBoxLayout(group_box)
        outer.setContentsMargins(10, 0, 10, 10)
        outer.setSpacing(10)

        self._list_layout = QVBoxLayout()
        self._list_layout.setContentsMargins(0, 0, 0, 0)
        self._list_layout.setSpacing(10)
        outer.addLayout(self._list_layout)

        self._value_def: dict = self.data.get("values", {})
        self._is_scalar = self._value_def.get("type") in _SCALAR_TYPES

        # 控制按钮行
        btn_row = QHBoxLayout()
        add_btn = QPushButton("添加")
        add_btn.setFixedWidth(50)
        add_btn.clicked.connect(self._add_item)
        btn_row.addWidget(add_btn)

        clear_btn = QPushButton("清空")
        clear_btn.setFixedWidth(50)
        clear_btn.clicked.connect(self._clear_items)
        btn_row.addWidget(clear_btn)
        btn_row.addStretch()
        outer.addLayout(btn_row)

        # 回填已有数据
        self._populate_existing()

        layout.addWidget(group_box)
        return layout

    def _populate_existing(self) -> None:
        """从 DataPath 读取已有列表数据并创建对应 UI 控件。"""
        data_list = self.path.read_list()
        if not data_list:
            return

        if self._is_scalar:
            for item_value in data_list:
                self._build_scalar_item_ui(item_value, data_list)
        else:
            for entry in data_list:
                if isinstance(entry, dict):
                    self._build_dict_item_ui(entry, data_list)

    def _build_scalar_item_ui(self, item_value: Any, data_list: list) -> None:
        """为已有的标量值创建 UI（不向 data_list 追加，数据已存在）。"""
        value_def = self._value_def

        item_box = QGroupBox()
        item_layout = QVBoxLayout(item_box)
        item_layout.setContentsMargins(10, 0, 10, 10)

        input_widget = self._create_scalar_input(value_def, item_value)
        item_layout.addWidget(input_widget)  # type: ignore

        self._bind_scalar_value(input_widget, value_def, item_box, data_list)
        self._add_remove_button(item_layout, item_box, data_list)
        self._list_layout.addWidget(item_box)

    def _build_dict_item_ui(self, entry: dict, data_list: list) -> None:
        """为已有的字典项创建 UI（不向 data_list 追加，数据已存在）。"""
        item_box = QGroupBox()
        item_layout = QVBoxLayout(item_box)
        item_layout.setContentsMargins(10, 0, 10, 10)

        entry_path = DataPath.on_dict(entry)
        item_layout.addLayout(
            load_component(self._value_def, None, None, path=entry_path)
        )

        self._add_remove_button(item_layout, item_box, data_list)
        self._list_layout.addWidget(item_box)

    # ── 列表操作 ──

    def _add_item(self) -> None:
        """添加一项到列表。"""
        data_list = self.path.read_list()
        if data_list is None:
            data_list = []
            self.path.write(data_list)

        if self._is_scalar:
            self._add_scalar_item(data_list)
        else:
            self._add_dict_item(data_list)

    def _add_scalar_item(self, data_list: list) -> None:
        """添加一个标量列表项（int/float/string/bool/simple_enum）。"""
        value_def = self._value_def
        default = self._scalar_default(value_def)
        data_list.append(default)

        item_box = QGroupBox()
        item_layout = QVBoxLayout(item_box)
        item_layout.setContentsMargins(10, 0, 10, 10)

        # 根据类型创建内联控件
        input_widget = self._create_scalar_input(value_def, default)
        item_layout.addWidget(input_widget)  # type: ignore

        # 连接值变更 → 写入列表对应索引
        self._bind_scalar_value(input_widget, value_def, item_box, data_list)

        # 删除按钮
        self._add_remove_button(item_layout, item_box, data_list)
        self._list_layout.addWidget(item_box)

    def _add_dict_item(self, data_list: list) -> None:
        """添加一个字典列表项。"""
        entry: dict = {}
        data_list.append(entry)

        item_box = QGroupBox()
        item_layout = QVBoxLayout(item_box)
        item_layout.setContentsMargins(10, 0, 10, 10)

        # 使用 DataPath.on_dict 绑定到该 entry
        entry_path = DataPath.on_dict(entry)
        item_layout.addLayout(
            load_component(self._value_def, None, None, path=entry_path)
        )

        self._add_remove_button(item_layout, item_box, data_list)
        self._list_layout.addWidget(item_box)

    def _add_remove_button(
        self, layout: QVBoxLayout, item_box: QGroupBox, data_list: list
    ) -> None:
        """添加删除按钮（标量和字典列表共用，使用索引定位）。"""
        btn_row = QHBoxLayout()
        remove_btn = QPushButton("删除")
        remove_btn.setFixedWidth(50)

        def remove() -> None:
            idx = self._list_layout.indexOf(item_box)
            if 0 <= idx < len(data_list):
                data_list.pop(idx)
            self._list_layout.removeWidget(item_box)
            item_box.setParent(None)
            item_box.deleteLater()

        remove_btn.clicked.connect(remove)
        btn_row.addWidget(remove_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

    def _clear_items(self) -> None:
        """清空列表。"""
        data_list = self.path.read_list()
        if data_list is not None:
            data_list.clear()

        while self._list_layout.count():
            item = self._list_layout.takeAt(0)
            widget = item.widget()  # type: ignore
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()

    # ── 标量控件内联创建 ──

    def _scalar_default(self, value_def: dict) -> Any:
        """计算标量列表项的默认值。"""
        vt = value_def.get("type")
        default = value_def.get("default")

        if vt == "int":
            try:
                return int(default) if default is not None else 0
            except (TypeError, ValueError):
                return 0
        if vt == "float":
            try:
                return float(default) if default is not None else 0.0
            except (TypeError, ValueError):
                return 0.0
        if vt == "bool":
            return bool(default) if default is not None else False
        if vt in {"string", "text_component"}:
            return str(default) if default is not None else ""
        if vt == "simple_enum":
            options: dict = value_def.get("values", {})
            if default is not None:
                return options.get(str(default), default)
            if options:
                first_key = next(iter(options))
                return options[first_key]
            return ""
        return ""

    def _create_scalar_input(self, value_def: dict, default: Any):
        """为标量列表项创建对应的输入控件。"""
        vt = value_def.get("type")
        desc = value_def.get("description", "")

        if vt == "bool":
            widget = QCheckBox(desc)
            widget.setChecked(bool(default))
            return widget

        if vt == "simple_enum":
            options: dict = value_def.get("values", {})
            widget = QComboBox()
            widget.addItems(options.keys())
            # 根据值找到对应的 key
            default_key = None
            for k, v in options.items():
                if v == default:
                    default_key = k
                    break
            if default_key is not None:
                widget.setCurrentText(default_key)
            return widget

        # int / float / string / text_component 使用 QLineEdit
        row = QHBoxLayout()
        row.addWidget(QLabel(desc + "：" if desc else ""))
        line_edit = QLineEdit()
        placeholder = value_def.get("place_holder_text", "")
        if placeholder:
            line_edit.setPlaceholderText(placeholder)
        if default is not None and vt not in ("int", "float"):
            line_edit.setText(str(default))
        elif vt in ("int", "float") and default not in (0, 0.0, None):
            line_edit.setText(str(default))
        row.addWidget(line_edit)
        row.addStretch()

        # 将 line_edit 和类型附加到 row 以便后续引用
        row._input = line_edit  # type: ignore[attr-defined]
        row._value_type = vt  # type: ignore[attr-defined]
        return row

    def _bind_scalar_value(
        self,
        widget,
        value_def: dict,
        item_box: QGroupBox,
        data_list: list,
    ) -> None:
        """绑定标量控件的值变更信号 — 每次操作实时通过 indexOf 定位。"""
        vt = value_def.get("type")

        def get_index() -> int:
            return self._list_layout.indexOf(item_box)

        def write_value(value: Any) -> None:
            idx = get_index()
            if 0 <= idx < len(data_list):
                data_list[idx] = value

        def clear_and_remove() -> None:
            idx = get_index()
            if 0 <= idx < len(data_list):
                data_list.pop(idx)
            self._list_layout.removeWidget(item_box)
            item_box.setParent(None)
            item_box.deleteLater()

        if vt == "bool":

            def on_bool_changed():
                write_value(widget.isChecked())

            widget.stateChanged.connect(on_bool_changed)

        elif vt == "simple_enum":
            options: dict = value_def.get("values", {})

            def on_enum_changed(text: str):
                write_value(options.get(text, text))

            widget.currentTextChanged.connect(on_enum_changed)

        else:
            # int / float / string / text_component
            line_edit = getattr(widget, "_input", None)
            if line_edit is None:
                return
            w_vt = getattr(widget, "_value_type", "string")

            def on_text_changed(text: str):
                text_value = text.strip()
                if not text_value:
                    clear_and_remove()
                    return
                if w_vt == "int":
                    try:
                        parsed = int(text_value)
                    except ValueError:
                        return
                    write_value(parsed)
                elif w_vt == "float":
                    try:
                        parsed = float(text_value)
                    except ValueError:
                        return
                    write_value(parsed)
                else:
                    write_value(text_value)

            line_edit.textChanged.connect(on_text_changed)


# ═══════════════════════════════════════════════════════════════
#  Selector Widgets
# ═══════════════════════════════════════════════════════════════


class SelectorWidget(ComponentWidget):
    """选择器基类 —— item / effect / enchantment 的公共模式。

    子类只需实现 _button_text / _open_dialog / _build_payload / _format_display。
    """

    def build(self) -> QHBoxLayout:
        layout = QHBoxLayout()
        layout.addWidget(QLabel(self._desc() + "："))

        self._status_label = QLabel(self._empty_display())
        self._status_label.setMinimumWidth(200)
        layout.addWidget(self._status_label)

        button = QPushButton(self._button_text())
        button.clicked.connect(self._on_select)
        layout.addWidget(button)
        layout.addStretch()

        self._refresh_display()
        return layout

    # ── 子类覆盖 ──

    def _button_text(self) -> str:
        raise NotImplementedError

    def _empty_display(self) -> str:
        return "未选择"

    def _format_display(self, payload) -> str:
        """根据已存储的 payload 生成显示文字。"""
        raise NotImplementedError

    def _open_dialog(self, parent, existing: Any) -> Any:
        """打开选择对话框，返回选中数据；取消返回 None。"""
        raise NotImplementedError

    def _build_payload(self, selected: Any) -> Any:
        """将对话框返回的数据转为存储格式。"""
        raise NotImplementedError

    # ── 内部实现 ──

    def _refresh_display(self) -> None:
        payload = self.path.read()
        if payload:
            self._status_label.setText(self._format_display(payload))
        else:
            self._status_label.setText(self._empty_display())

    def _on_select(self) -> None:
        existing = self.path.read()
        selected = self._open_dialog(self._status_label.window(), existing)
        if selected is None:
            return
        payload = self._build_payload(selected)
        self.path.write(payload)
        self._refresh_display()


class ItemSelectorWidget(SelectorWidget):
    """物品选择器。"""

    def _button_text(self) -> str:
        return "选择物品"

    def _format_display(self, payload) -> str:
        if isinstance(payload, str):
            return payload
        item_id = payload.get("id", "?")
        name = payload.get("name", item_id)
        count = payload.get("count")
        if count is None:
            return f"{name} ({item_id})"
        return f"{name} ({item_id}) x{count}"

    def _open_dialog(self, parent, existing: Any):
        try:
            import item_selector
        except Exception:
            logger.exception("导入 item_selector 失败")
            return None
        return item_selector.choose_item(only_basic=False, parent=parent)

    def _build_payload(self, selected: Any) -> dict:
        from item import Item

        if isinstance(selected, Item):
            item_id = selected.id
            count = selected.count if selected.count is not None else 1
            count = max(0, min(99, count))
            payload: dict = {"id": item_id, "count": count}
            if selected.components:
                payload["components"] = selected.components
            return payload
        return selected if isinstance(selected, dict) else {"id": str(selected)}


class EffectSelectorWidget(SelectorWidget):
    """状态效果选择器。"""

    def _button_text(self) -> str:
        return "选择状态效果"

    def _format_display(self, payload) -> str:
        count = self._count_effects(payload)
        if count <= 0:
            return "未选择"
        return f"已选择 {count} 个状态效果"

    @staticmethod
    def _count_effects(payload) -> int:
        if isinstance(payload, list):
            return len(payload)
        if isinstance(payload, dict):
            effects = payload.get("effects")
            if isinstance(effects, list):
                return len(effects)
            if "id" in payload:
                return 1
        return 0

    @staticmethod
    def _strip_meta(effect: dict) -> dict:
        """移除 name/description 等仅供 UI 使用的字段。"""
        return {k: v for k, v in effect.items() if k not in {"name", "description"}}

    @classmethod
    def _sanitize(cls, payload) -> Any:
        if payload is None:
            return None
        if isinstance(payload, list):
            return [cls._strip_meta(e) if isinstance(e, dict) else e for e in payload]
        if isinstance(payload, dict):
            effects = payload.get("effects")
            if isinstance(effects, list):
                sanitized = dict(payload)
                sanitized["effects"] = [
                    cls._strip_meta(e) if isinstance(e, dict) else e for e in effects
                ]
                sanitized.pop("name", None)
                sanitized.pop("description", None)
                return sanitized
            return cls._strip_meta(payload)
        return payload

    def _open_dialog(self, parent, existing: Any):
        try:
            import effect_selector
        except Exception:
            logger.exception("导入 effect_selector 失败")
            return None
        return effect_selector.open_effect_selector(parent=parent, existing=existing)

    def _build_payload(self, selected: Any) -> Any:
        if hasattr(selected, "to_dict"):
            return self._sanitize(selected.to_dict())
        return selected


class EnchantmentSelectorWidget(SelectorWidget):
    """附魔选择器。"""

    def _button_text(self) -> str:
        return "选择附魔"

    def _format_display(self, payload) -> str:
        if isinstance(payload, dict):
            count = len(payload)
        elif isinstance(payload, list):
            count = len(payload)
        else:
            count = 0
        if count <= 0:
            return "未选择"
        return f"已选择 {count} 个附魔"

    def _open_dialog(self, parent, existing: Any):
        try:
            import enchantment_selector
        except Exception:
            logger.exception("导入 enchantment_selector 失败")
            return None
        return enchantment_selector.open_enchantment_selector(
            parent=parent, existing=existing
        )

    def _build_payload(self, selected: Any) -> dict:
        """将选中的附魔组转为 {id: level} 映射。"""
        payload: dict[str, int] = {}
        enchantments = getattr(selected, "enchantments", None)
        if not enchantments:
            return payload
        for ench in enchantments:
            ench_id = getattr(ench, "id", None)
            if not ench_id:
                continue
            try:
                level = int(getattr(ench, "level", 1))
            except (TypeError, ValueError):
                level = 1
            payload[ench_id] = level
        return payload


# ═══════════════════════════════════════════════════════════════
#  TextComponentMultilineWidget — 多行文本组件编辑器
# ═══════════════════════════════════════════════════════════════


class TextComponentMultilineWidget(ComponentWidget):
    """多行文本组件编辑器入口（用于 lore 等多行场景）。

    使用 ``TextEditorDialog(multiline=True)`` 编辑多行文本，
    每行作为一个独立的文本组件。存储/读取 ``list[dict]``。
    """

    def build(self) -> QHBoxLayout:
        layout = QHBoxLayout()
        layout.addWidget(QLabel(self._desc() + "："))

        # 预览文本框（只读，显示行数或首行摘要）
        self._preview = QLineEdit()
        self._preview.setReadOnly(True)
        self._preview.setPlaceholderText("(空)")
        layout.addWidget(self._preview, stretch=1)

        edit_btn = QPushButton("编辑...")
        edit_btn.clicked.connect(self._open_editor)
        layout.addWidget(edit_btn)

        clear_btn = QPushButton("✕")
        clear_btn.setFixedWidth(28)
        clear_btn.setToolTip("清除文本组件")
        clear_btn.clicked.connect(self._clear)
        layout.addWidget(clear_btn)

        self._refresh_preview()
        return layout

    def _refresh_preview(self) -> None:
        """从 DataPath 读取当前值并更新预览。"""
        current = self.path.read()
        # 空值情况：None / 空列表 / 空字典（toggle 工厂默认写入 {}）均视为空
        if current is None or (isinstance(current, (list, dict)) and not current):
            self._preview.setText("")
            self._preview.setPlaceholderText("(空)")
            return

        if isinstance(current, list):
            if len(current) == 1:
                summary = self._plain_text_summary(current[0])[:60]
            else:
                summary = f"{len(current)} 行"
            self._preview.setText(summary)
        elif isinstance(current, dict):
            # 非空 dict 情况（例如加载的旧数据）：尝试提取纯文本摘要
            from text import TextComponent
            try:
                tc = TextComponent.from_dict(current)
                summary = TextComponentWidget._plain_text_summary(tc)[:60]
            except Exception:
                summary = str(current)[:60]
            self._preview.setText(summary if summary else "")
            if not summary:
                self._preview.setPlaceholderText("(空)")
        else:
            self._preview.setText(str(current)[:60])

    @staticmethod
    def _plain_text_summary(comp) -> str:
        """提取单个组件的纯文本摘要。"""
        if isinstance(comp, str):
            return comp
        if isinstance(comp, dict):
            # 复用 TextComponentWidget 的逻辑
            from text import TextComponent
            try:
                tc = TextComponent.from_dict(comp)
                return TextComponentWidget._plain_text_summary(tc)
            except Exception:
                return comp.get("text", "")[:60]
        return str(comp)[:60]

    def _open_editor(self) -> None:
        """打开 TextEditorDialog（多行模式）编辑文本组件列表。"""
        from text_editor import TextEditorDialog

        current = self.path.read()
        dlg = TextEditorDialog.from_dict(None, current, multiline=True)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            result = dlg.to_dict()
            if not result or (isinstance(result, list) and len(result) == 0):
                self.path.delete()
            else:
                self.path.write(result)
            self._refresh_preview()

    def _clear(self) -> None:
        """清除文本组件。"""
        self.path.delete()
        self._preview.setText("")
        self._preview.setPlaceholderText("(空)")


# ═══════════════════════════════════════════════════════════════
#  Dispatcher
# ═══════════════════════════════════════════════════════════════

_TYPE_MAP: dict[str, type[ComponentWidget]] = {
    "int": IntFloatWidget,
    "float": IntFloatWidget,
    "bool": BoolWidget,
    "string": StringWidget,
    "text_component": TextComponentWidget,
    "text_component_multiline": TextComponentMultilineWidget,
    "block_filter": StringWidget,
    "simple_enum": SimpleEnumWidget,
    "enum": ConditionalEnumWidget,
    "dict": DictWidget,
    "list": ListWidget,
    "item": ItemSelectorWidget,
    "effect": EffectSelectorWidget,
    "enchantment": EnchantmentSelectorWidget,
}


def load_component(
    data: dict,
    item_obj: Item | None,
    component_id: str | None,
    path: DataPath | None = None,
) -> QHBoxLayout:
    """根据 JSON 组件定义构建 UI 布局。

    Args:
        data: JSON 组件定义
        item_obj: 目标 Item（path 为 None 时需要）
        component_id: 数据组件 ID（path 为 None 时需要）
        path: 数据绑定路径；为 None 时自动从 item_obj + component_id 创建

    Returns:
        构建好的水平布局
    """
    if path is None:
        if item_obj is None or component_id is None:
            logger.warning("load_component: item_obj 和 component_id 不能为 None")
            return QHBoxLayout()
        path = DataPath(item_obj, component_id)

    comp_type = data.get("type")
    widget_cls = _TYPE_MAP.get(comp_type)  # type: ignore

    if widget_cls is None:
        logger.warning("未知组件类型: %s", comp_type)
        return QHBoxLayout()

    builder = widget_cls(data, path)
    layout = builder.build()
    # 关键：将 builder 挂载到 layout 上，防止 Python GC 回收 builder 实例
    # PyQt6 中 bound method 信号连接不会阻止 Python 对象被 GC
    layout._cw_builder = builder  # type: ignore[attr-defined]
    return layout
