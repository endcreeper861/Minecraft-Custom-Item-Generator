"""
定义、解析数据组件类。
"""

import logging
from typing import TYPE_CHECKING, Callable

from PyQt6.QtWidgets import (QCheckBox, QComboBox, QGroupBox, QHBoxLayout,
                             QLabel, QLineEdit, QPushButton, QVBoxLayout)

import item
import utils

logger = logging.getLogger(__name__)

DataGetter = Callable[[], dict | list | None]


def _get_component_root(current_item: item.Item, component_id: str) -> dict | None:
    data = current_item.components.get(component_id)
    if isinstance(data, dict):
        return data
    return None


def _make_component_root_getter(
    current_item: item.Item, component_id: str
) -> DataGetter:
    def getter() -> dict | list | None:
        return _get_component_root(current_item, component_id)

    return getter


def _make_dict_child_getter(parent_getter: DataGetter, key: str) -> DataGetter:
    def getter() -> dict | list | None:
        parent = parent_getter()
        if parent is None or not isinstance(parent, dict):
            return None
        child = parent.get(key)
        if not isinstance(child, dict):
            child = {}
            parent[key] = child
        return child

    return getter


def _make_list_child_getter(parent_getter: DataGetter, key: str) -> DataGetter:
    def getter() -> dict | list | None:
        parent = parent_getter()
        if parent is None or not isinstance(parent, dict):
            return None
        child = parent.get(key)
        if not isinstance(child, list):
            child = []
            parent[key] = child
        return child

    return getter


def load_component(
    data: dict,
    item: item.Item,
    id: str,
    data_root_getter: DataGetter | None = None,
    field_key: str | None = None,
) -> QHBoxLayout:
    """
    加载数据组件。
    """
    layout = QHBoxLayout()
    logger.debug("加载组件: %s", data.get("type"))

    if data_root_getter is None:
        data_root_getter = _make_component_root_getter(item, id)

    match data:
        case {"type": "int" | "float", "description": description}:
            layout.addWidget(QLabel(description + "："))
            logger.debug("创建数值输入组件: %s", description)
            input_field = QLineEdit()
            if "place_holder_text" in data:
                input_field.setPlaceholderText(data["place_holder_text"])
            layout.addWidget(input_field)
            field_type = data["type"]

            def on_text_changed(text: str):
                container = data_root_getter()
                if container is None or not isinstance(container, dict):
                    return
                if field_key is None:
                    return
                text_value = text.strip()
                if not text_value:
                    container.pop(field_key, None)
                    return
                try:
                    parsed = int(text_value) if field_type == "int" else float(text_value)
                except ValueError:
                    return
                container[field_key] = parsed

            input_field.textChanged.connect(on_text_changed)
            layout.addStretch()

        case {"type": "bool", "description": description, "default": default}:
            check_box = QCheckBox(description)
            check_box.setChecked(default)
            logger.debug("创建布尔组件: %s (default=%s)", description, default)
            layout.addWidget(check_box)

            def on_state_changed():
                container = data_root_getter()
                if container is None or not isinstance(container, dict):
                    return
                if field_key is None:
                    return
                container[field_key] = check_box.isChecked()

            check_box.stateChanged.connect(on_state_changed)

        case {"type": "list", "description": description, "values": values}:
            group_box = QGroupBox(description)
            components_layout = QVBoxLayout(group_box)
            components_layout.setContentsMargins(10, 0, 10, 10)
            components_layout.setSpacing(10)
            logger.debug("创建列表组件: %s", description)

            list_layout = QVBoxLayout()
            list_layout.setContentsMargins(0, 0, 0, 0)
            list_layout.setSpacing(10)
            components_layout.addLayout(list_layout)

            def add_item():
                logger.debug("添加列表项到 '%s'", description)
                data_list = data_root_getter()
                if data_list is None or not isinstance(data_list, list):
                    return
                entry: dict = {}
                data_list.append(entry)
                item_box = QGroupBox()
                item_layout = QVBoxLayout(item_box)
                item_layout.setContentsMargins(10, 0, 10, 10)
                item_layout.addLayout(
                    load_component(values, item, id, data_root_getter=lambda: entry)
                )
                remove_button_layout = QHBoxLayout()
                remove_button = QPushButton("删除")
                remove_button.setFixedWidth(50)
                remove_button_layout.addWidget(remove_button)
                remove_button_layout.addStretch()
                item_layout.addLayout(remove_button_layout)
                list_layout.addWidget(item_box)

                def remove_item():
                    # 从布局中移除该项并安排删除以释放资源
                    logger.debug("移除列表项 from '%s'", description)
                    if entry in data_list:
                        data_list.remove(entry)
                    list_layout.removeWidget(item_box)
                    item_box.setParent(None)
                    item_box.deleteLater()

                remove_button.clicked.connect(remove_item)

            def clear_items():
                # 使用 takeAt() 并对取出的 widget 调用 deleteLater()
                count = list_layout.count()
                logger.debug("清空列表 '%s'，项数=%d", description, count)
                data_list = data_root_getter()
                if data_list is not None and isinstance(data_list, list):
                    data_list.clear()
                while list_layout.count():
                    item = list_layout.takeAt(0)
                    widget = item.widget()  # type: ignore
                    if widget is not None:
                        widget.setParent(None)
                        widget.deleteLater()

            control_button_layout = QHBoxLayout()
            add_button = QPushButton("添加")
            add_button.setFixedWidth(50)
            add_button.clicked.connect(add_item)
            control_button_layout.addWidget(add_button)
            clear_button = QPushButton("清空")
            clear_button.setFixedWidth(50)
            clear_button.clicked.connect(clear_items)
            control_button_layout.addWidget(clear_button)
            control_button_layout.addStretch()
            components_layout.addLayout(control_button_layout)

            layout.addWidget(group_box)

        case {"type": "dict", "description": description, "values": values}:
            # 如果有description则用group box分组，否则直接放在当前布局
            group_box = QGroupBox(description)
            components_layout = QVBoxLayout(group_box)
            components_layout.setContentsMargins(10, 0, 10, 10)
            components_layout.setSpacing(10)
            logger.debug("创建dict组件(分组): %s", description)
            for key, value in values.items():
                value_type = value.get("type")
                if value_type in {"dict", "enum"}:
                    child_getter = _make_dict_child_getter(data_root_getter, key)
                    components_layout.addLayout(
                        load_component(value, item, id, data_root_getter=child_getter)
                    )
                elif value_type == "list":
                    child_getter = _make_list_child_getter(data_root_getter, key)
                    components_layout.addLayout(
                        load_component(value, item, id, data_root_getter=child_getter)
                    )
                else:
                    components_layout.addLayout(
                        load_component(
                            value,
                            item,
                            id,
                            data_root_getter=data_root_getter,
                            field_key=key,
                        )
                    )
            layout.addWidget(group_box)

        case {"type": "dict", "values": values}:
            components_layout = QVBoxLayout()
            logger.debug("创建dict组件（无描述）: keys=%s", list(values.keys()))
            for key, value in values.items():
                value_type = value.get("type")
                if value_type in {"dict", "enum"}:
                    child_getter = _make_dict_child_getter(data_root_getter, key)
                    components_layout.addLayout(
                        load_component(value, item, id, data_root_getter=child_getter)
                    )
                elif value_type == "list":
                    child_getter = _make_list_child_getter(data_root_getter, key)
                    components_layout.addLayout(
                        load_component(value, item, id, data_root_getter=child_getter)
                    )
                else:
                    components_layout.addLayout(
                        load_component(
                            value,
                            item,
                            id,
                            data_root_getter=data_root_getter,
                            field_key=key,
                        )
                    )
            layout.addLayout(components_layout)

        case {"type": "simple_enum", "description": description, "values": values}:
            layout.addWidget(QLabel(description + "："))
            combo_box = QComboBox()
            combo_box.addItems(values.keys())
            logger.debug(
                "创建simple_enum组件: %s options=%s", description, list(values.keys())
            )
            layout.addWidget(combo_box)

            def on_simple_enum_changed(text: str):
                container = data_root_getter()
                if container is None or not isinstance(container, dict):
                    return
                if field_key is None:
                    return
                container[field_key] = values.get(text, text)

            combo_box.currentTextChanged.connect(on_simple_enum_changed)
            layout.addStretch()

        case {"type": "enum", "description": description, "values": values}:
            group_layout = QVBoxLayout()
            combo_box_layout = QHBoxLayout()
            group_layout.addLayout(combo_box_layout)
            combo_box_layout.addWidget(QLabel(description + "："))
            combo_box = QComboBox()
            combo_box.addItems(values.keys())
            logger.debug(
                "创建enum组件: %s options=%s", description, list(values.keys())
            )
            components_layout = QVBoxLayout()

            def on_selection_changed(text):
                logger.debug("enum组件 '%s' 选择改变: %s", description, text)
                selected = values[text]
                selected_id = selected.get("id", text)
                target = data_root_getter()
                if isinstance(target, dict):
                    target.clear()
                    target["type"] = selected_id
                # 先清空之前的组件
                utils.clear_layout(components_layout)
                # 加载新组件
                if "components" in selected:
                    new_layout = load_component(
                        selected["components"], item, id, data_root_getter=data_root_getter
                    )
                    components_layout.addLayout(new_layout)

            on_selection_changed(combo_box.currentText())  # 初始化显示默认选项的组件
            combo_box.currentTextChanged.connect(on_selection_changed)
            combo_box_layout.addWidget(combo_box)
            combo_box_layout.addStretch()
            group_layout.addLayout(components_layout)
            layout.addLayout(group_layout)

        case {"type": "item", "description": description}:
            # 打开物品选择器
            layout.addWidget(QLabel(description + "："))
            selected_label = QLabel("未选择")
            selected_label.setMinimumWidth(200)
            layout.addWidget(selected_label)
            button = QPushButton("选择物品")
            logger.debug("创建物品选择按钮: %s", description)
            layout.addWidget(button)
            layout.addStretch()

            def set_selected_display(item_id: str, name: str | None, count: int | None):
                if count is None:
                    count_text = ""
                else:
                    count_text = f" x{count}"
                if name:
                    selected_label.setText(f"{name} ({item_id}){count_text}")
                else:
                    selected_label.setText(f"{item_id}{count_text}")

            def set_selected_from_payload(payload: dict | str | None):
                if not payload:
                    selected_label.setText("未选择")
                    return
                if isinstance(payload, str):
                    set_selected_display(payload, None, None)
                    return
                item_id = payload.get("id")
                if not item_id:
                    selected_label.setText("未选择")
                    return
                count = payload.get("count")
                set_selected_display(item_id, None, count)

            def get_existing_payload() -> dict | str | None:
                if field_key is None:
                    return data_root_getter() # type: ignore
                container = data_root_getter()
                if isinstance(container, dict):
                    return container.get(field_key)
                return None

            set_selected_from_payload(get_existing_payload())

            def on_select_item():
                try:
                    import item_selector
                except Exception:
                    logger.exception("导入 item_selector 失败")
                    return

                selected = item_selector.choose_item(only_basic=False, parent=button.window())
                if not selected:
                    return

                item_id = selected.id
                count = selected.count if selected.count is not None else 1
                if count < 0:
                    count = 0
                if count > 99:
                    count = 99

                payload: dict = {"id": item_id, "count": count}
                if selected.components:
                    payload["components"] = selected.components

                if field_key is None:
                    item.components[id] = payload
                else:
                    container = data_root_getter()
                    if isinstance(container, dict):
                        container[field_key] = payload

                set_selected_display(item_id, selected.name, count)

            button.clicked.connect(on_select_item)

        case {"type": "effect", "description": description}:
            layout.addWidget(QLabel(description + "："))
            selected_label = QLabel("未选择")
            selected_label.setMinimumWidth(200)
            layout.addWidget(selected_label)
            button = QPushButton("选择状态效果")
            logger.debug("创建状态效果选择按钮: %s", description)
            layout.addWidget(button)
            layout.addStretch()

            def _strip_effect_dict(effect: dict) -> dict:
                return {
                    key: value
                    for key, value in effect.items()
                    if key not in {"name", "description"}
                }

            def _sanitize_effect_payload(payload: dict | list | None) -> dict | list | None:
                if payload is None:
                    return None
                if isinstance(payload, list):
                    return [
                        _strip_effect_dict(entry) if isinstance(entry, dict) else entry
                        for entry in payload
                    ]
                if isinstance(payload, dict):
                    effects = payload.get("effects")
                    if isinstance(effects, list):
                        sanitized = dict(payload)
                        sanitized["effects"] = [
                            _strip_effect_dict(entry)
                            if isinstance(entry, dict)
                            else entry
                            for entry in effects
                        ]
                        sanitized.pop("name", None)
                        sanitized.pop("description", None)
                        return sanitized
                    return _strip_effect_dict(payload)
                return payload

            def _effect_payload_count(payload: dict | list | None) -> int:
                if isinstance(payload, list):
                    return len(payload)
                if isinstance(payload, dict):
                    effects = payload.get("effects")
                    if isinstance(effects, list):
                        return len(effects)
                return 0

            def set_effect_selected_display(count: int | None):
                if count is None or count <= 0:
                    selected_label.setText("未选择")
                else:
                    selected_label.setText(f"已选择 {count} 个状态效果")

            def set_effect_selected_from_payload(payload: dict | list | None):
                if not payload:
                    selected_label.setText("未选择")
                    return
                if isinstance(payload, list):
                    set_effect_selected_display(len(payload))
                    return
                if isinstance(payload, dict):
                    effects = payload.get("effects")
                    if isinstance(effects, list):
                        set_effect_selected_display(len(effects))
                        return
                selected_label.setText("未选择")

            def get_effect_existing_payload() -> dict | list | None:
                if field_key is None:
                    return item.components.get(id)
                container = data_root_getter()
                if isinstance(container, dict):
                    return container.get(field_key)
                return None

            set_effect_selected_from_payload(get_effect_existing_payload())

            def on_select_effect():
                try:
                    import effect_selector
                except Exception:
                    logger.exception("导入 effect_selector 失败")
                    return

                selected = effect_selector.open_effect_selector(parent=button.window())
                if selected is None:
                    return

                payload = _sanitize_effect_payload(selected.to_dict())
                if field_key is None:
                    item.components[id] = payload
                else:
                    container = data_root_getter()
                    if isinstance(container, dict):
                        container[field_key] = payload

                set_effect_selected_display(_effect_payload_count(payload))

            button.clicked.connect(on_select_effect)

        case {"type": "enchantment", "description": description}:
            layout.addWidget(QLabel(description + "："))
            selected_label = QLabel("未选择")
            selected_label.setMinimumWidth(200)
            layout.addWidget(selected_label)
            button = QPushButton("选择附魔")
            logger.debug("创建附魔选择按钮: %s", description)
            layout.addWidget(button)
            layout.addStretch()

            def set_enchantment_selected_display(count: int | None):
                if count is None or count <= 0:
                    selected_label.setText("未选择")
                else:
                    selected_label.setText(f"已选择 {count} 个附魔")

            def set_enchantment_selected_from_payload(payload: dict | list | None):
                if not payload:
                    selected_label.setText("未选择")
                    return
                if isinstance(payload, dict):
                    set_enchantment_selected_display(len(payload))
                    return
                if isinstance(payload, list):
                    set_enchantment_selected_display(len(payload))
                    return
                selected_label.setText("未选择")

            def get_enchantment_existing_payload() -> dict | list | None:
                if field_key is None:
                    return item.components.get(id)
                container = data_root_getter()
                if isinstance(container, dict):
                    return container.get(field_key)
                return None

            set_enchantment_selected_from_payload(get_enchantment_existing_payload())

            def build_enchantment_payload(group) -> dict:
                payload: dict[str, int] = {}
                enchantments = getattr(group, "enchantments", None)
                if not enchantments:
                    return payload
                for ench in enchantments:
                    ench_id = getattr(ench, "id", None)
                    if not ench_id:
                        continue
                    try:
                        level = int(getattr(ench, "level", 1))
                    except Exception:
                        level = 1
                    payload[ench_id] = level
                return payload

            def on_select_enchantment():
                try:
                    import enchantment_selector
                except Exception:
                    logger.exception("导入 enchantment_selector 失败")
                    return

                selected = enchantment_selector.open_enchantment_selector(
                    parent=button.window()
                )
                if selected is None:
                    return

                payload = build_enchantment_payload(selected)
                if field_key is None:
                    item.components[id] = payload
                else:
                    container = data_root_getter()
                    if isinstance(container, dict):
                        container[field_key] = payload

                set_enchantment_selected_display(len(payload))

            button.clicked.connect(on_select_enchantment)
        
        case {"type": "sound_event", "description": description}:
            layout.addWidget(QLabel(description + "："))
            button = QPushButton("选择声音事件")
            logger.debug("创建声音事件选择按钮: %s", description)
            layout.addWidget(button)
            layout.addStretch()

        case _:
            try:
                t = data.get("type")
            except Exception:
                t = str(data)
            logger.warning("未知或格式错误的数据组件类型：%s", t)

    return layout
