"""
创建和保存自定义物品。
"""

import json
import logging
import os
import sys
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont, QGuiApplication, QPainter, QPixmap
from PyQt6.QtWidgets import (QApplication, QCheckBox, QComboBox, QDialog,
                             QFileDialog, QGroupBox, QHBoxLayout, QLabel,
                             QLineEdit, QMessageBox, QPlainTextEdit,
                             QPushButton, QScrollArea, QSizePolicy, QSpinBox,
                             QVBoxLayout, QWidget)

import component
import item
import item_selector
import utils
from data_path import DataPath
from utils import get_app_dir

logger = logging.getLogger(__name__)

TOGGLE_DEFAULT_UNSET = object()


class ItemEditorDialog(QDialog):
    """
    自定义物品编辑器窗口
    允许用户基于基础物品创建自定义物品，并保存为JSON文件
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_item: item.Item = item.Item(
            id="", name="", count=1
        )  # 当前编辑的物品对象
        self._checkbox_to_comp_id: dict[QCheckBox, str] = (
            {}
        )  # checkbox → component_id 映射
        self.current_version: str = ""  # 当前选中的游戏版本
        self._versions: dict[str, str] = {}  # 版本 → 组件映射表文件名
        self._default_version: str = ""  # 默认版本
        self._component_table: dict[str, str] = {}  # 组件ID → 组件数据文件相对路径
        self._comp_id_to_category: dict[str, str] = {}  # 组件ID → 分类名
        self._category_flows: dict[str, utils.FlowLayout] = {}  # 分类名 → FlowLayout
        self._category_groups: dict[str, QGroupBox] = {}  # 分类名 → QGroupBox
        self._comp_group_boxes: list[QGroupBox] = []  # 已创建的组件编辑分组

        self.setWindowTitle("自定义物品编辑器")
        self.resize(700, 500)
        self.setup_ui()

    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)

        # === 顶部：保存区域 ===
        save_layout = QHBoxLayout()
        save_layout.setSpacing(8)

        self.load_btn = QPushButton("加载")
        self.load_btn.clicked.connect(self.on_load)
        self.load_btn.setMinimumWidth(40)
        save_layout.addWidget(self.load_btn)

        save_layout.addWidget(QLabel("保存名："))
        self.save_name_edit = QLineEdit()
        self.save_name_edit.setPlaceholderText("输入文件名（不含.json）")
        self.save_name_edit.setMinimumWidth(160)
        self.save_name_edit.setStyleSheet("""
            QLineEdit {
                padding: 6px;
                border-radius: 4px;
                border: 1px solid #ccc;
            }
            QLineEdit:focus {
                border: 2px solid #3498db;
            }
            """)
        save_layout.addWidget(self.save_name_edit)

        self.save_btn = QPushButton("保存")
        self.save_btn.clicked.connect(self.on_save)
        self.save_btn.setMinimumWidth(80)
        self.save_btn.setStyleSheet(utils.BIG_GREEN_BUTTON_STYLE)
        save_layout.addWidget(self.save_btn)

        self.generate_btn = QPushButton("生成命令")
        self.generate_btn.clicked.connect(self.on_generate)
        self.generate_btn.setMinimumWidth(80)
        self.generate_btn.setStyleSheet(utils.BIG_GREEN_BUTTON_STYLE)
        save_layout.addWidget(self.generate_btn)

        main_layout.addLayout(save_layout)

        # === 可滚动的内容区域（会放置各分区） ===
        self.content_widget = QWidget()
        # 使用水平布局作为列容器，内部每列为一个垂直布局，避免不同列间高度互相影响
        self.content_layout = QHBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(6, 6, 6, 6)
        self.content_layout.setSpacing(12)
        # 列容器列表（每项为 QWidget，内部使用 QVBoxLayout）
        self._column_widgets: list[QWidget] = []

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setWidget(self.content_widget)

        # === 基本设置 ===
        self.basic_group = QGroupBox("基本设置")
        self.basic_group.setStyleSheet(utils.DEFAULT_GROUP_STYLE)
        basic_layout = QVBoxLayout(self.basic_group)
        basic_layout.setContentsMargins(10, 0, 10, 10)
        basic_layout.setSpacing(10)

        # --- 选择基础物品行 ---
        select_layout = QHBoxLayout()
        select_layout.setSpacing(10)

        self.select_base_btn = QPushButton("选择基础物品")
        self.select_base_btn.clicked.connect(self.on_select_base_item)
        select_layout.addWidget(self.select_base_btn)

        # 图标显示标签
        self.base_icon_label = QLabel()
        self.base_icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.base_icon_label.setFixedSize(64, 64)
        self.base_icon_label.setStyleSheet(
            "border: 1px solid #ccc; border-radius: 4px; background-color: #8b8b8b;"
        )
        self.base_icon_label.setToolTip("基础物品图标")
        select_layout.addWidget(self.base_icon_label)

        # 显示选中的基础物品信息
        self.base_item_info = QLabel("未选择基础物品")
        self.base_item_info.setFont(QFont("Segoe UI", 9))
        self.base_item_info.setWordWrap(True)
        self.base_item_info.setMinimumWidth(200)
        select_layout.addWidget(self.base_item_info)

        select_layout.addStretch()
        basic_layout.addLayout(select_layout)

        # --- 数量输入行 ---
        input_layout = QHBoxLayout()
        input_layout.setSpacing(15)

        # 物品数量
        qty_layout = QHBoxLayout()
        qty_layout.setSpacing(5)
        qty_layout.addWidget(QLabel("物品数量："))
        self.count_spin = QSpinBox()
        self.count_spin.setRange(1, 6400)
        self.count_spin.setValue(1)
        self.count_spin.setMinimumWidth(80)
        self.count_spin.valueChanged.connect(self._update_count)
        qty_layout.addWidget(self.count_spin)
        input_layout.addLayout(qty_layout)

        input_layout.addStretch()
        basic_layout.addLayout(input_layout)

        # --- 目标版本选择行 ---
        version_layout = QHBoxLayout()
        version_layout.setSpacing(10)
        version_layout.addWidget(QLabel("目标版本："))
        self.version_combo = QComboBox()
        self.version_combo.setMinimumWidth(140)
        version_layout.addWidget(self.version_combo)
        version_layout.addStretch()
        basic_layout.addLayout(version_layout)

        # 加载版本映射表并填充下拉框（连接信号前先设好初始项，避免重复触发重建）
        self._load_versions()
        self.version_combo.blockSignals(True)
        for ver in self._versions:
            self.version_combo.addItem(ver)
        if self._default_version and self._default_version in self._versions:
            idx = self.version_combo.findText(self._default_version)
            if idx >= 0:
                self.version_combo.setCurrentIndex(idx)
        self.version_combo.blockSignals(False)

        # === 物品堆叠组件功能（按分类组织组件开关） ===
        self.components_group = QGroupBox("物品堆叠组件功能")
        self.components_group.setStyleSheet(utils.DEFAULT_GROUP_STYLE)
        comps_layout = QVBoxLayout(self.components_group)
        comps_layout.setContentsMargins(10, 0, 10, 10)
        comps_layout.setSpacing(6)

        # 加载组件分类数据
        self._comp_id_to_category: dict[str, str] = {}
        categories_order: list[str] = []
        try:
            cat_path = get_app_dir() / "data/component_categories.json"
            if cat_path.exists():
                with open(cat_path, "r", encoding="utf-8") as f:
                    cat_data = json.load(f)
                for cat in cat_data.get("categories", []):
                    cat_name = cat["name"]
                    categories_order.append(cat_name)
                    for comp_id in cat.get("components", []):
                        self._comp_id_to_category.setdefault(comp_id, cat_name)
        except Exception as e:
            logger.warning(f'加载分类文件失败，全部归入"其他": {e}')

        categories_order.append("其他")  # 兜底分类

        # 预创建分类子分组（每个分类一个 QGroupBox，内含 FlowLayout）
        self._category_groups: dict[str, QGroupBox] = {}
        self._category_flows: dict[str, utils.FlowLayout] = {}
        for cat_name in categories_order:
            cat_group = QGroupBox(cat_name)
            cat_group.setStyleSheet(utils.DEFAULT_GROUP_STYLE)
            cat_inner = QVBoxLayout(cat_group)
            cat_inner.setContentsMargins(6, 0, 6, 6)
            cat_inner.setSpacing(4)
            flow_container = QWidget()
            flow = utils.FlowLayout()
            flow.setSpacing(8)
            flow_container.setLayout(flow)
            cat_inner.addWidget(flow_container)
            comps_layout.addWidget(cat_group)
            self._category_groups[cat_name] = cat_group
            self._category_flows[cat_name] = flow

        basic_layout.addWidget(self.components_group)

        # 将分区放入 content_widget 的布局中，后续根据窗口宽度自动分栏
        self.content_groups = [self.basic_group]

        main_layout.addWidget(self.scroll_area)

        # 根据当前窗口宽度安排列数
        self._last_cols = 0
        self._arrange_columns()

        # 连接版本切换信号并加载默认版本的组件定义
        self.version_combo.currentTextChanged.connect(self._load_version)
        self._load_version(self.version_combo.currentText())

        # === 占位：其他分区后续添加 ===
        # TODO: 添加组件编辑、分类选择、NBT编辑等其他分区

    def _update_count(self, value):
        """更新当前编辑物品的数量"""
        self.current_item.count = value

    def _load_versions(self):
        """加载版本映射表 (data/versions/versions.json)。

        版本映射表保存所有支持的版本，并将每个版本对应到一份组件映射表文件。
        """
        self._versions = {}
        self._default_version = ""
        try:
            versions_path = get_app_dir() / "data/versions/versions.json"
            if versions_path.exists():
                with open(versions_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self._versions = data.get("versions", {})
                self._default_version = data.get("default", "")
        except Exception as e:
            logger.warning(f"加载版本映射表失败: {e}")

    def _load_version(self, version: str):
        """加载指定版本的组件映射表并重建组件 UI。

        切换版本时保留基础物品、数量与已编辑的组件值（按组件 ID 保留）。
        """
        if not version:
            return
        self.current_version = version

        # 1. 加载当前版本的组件映射表（组件ID → 组件数据文件相对路径）
        table_file = self._versions.get(version, "")
        self._component_table = {}
        if table_file:
            try:
                table_path = get_app_dir() / "data/component_tables" / table_file
                if table_path.exists():
                    with open(table_path, "r", encoding="utf-8") as f:
                        self._component_table = json.load(f)
            except Exception as e:
                logger.warning(f"加载组件映射表 {table_file} 失败: {e}")

        # 2. 清理旧组件 UI（复选框与编辑分组）
        self._checkbox_to_comp_id.clear()
        for flow in self._category_flows.values():
            utils.clear_layout(flow)
        for group_box in self._comp_group_boxes:
            group_box.deleteLater()
        self._comp_group_boxes = []
        self.content_groups = [self.basic_group]

        # 3. 按组件映射表重建复选框与编辑分组
        for comp_id, rel_path in self._component_table.items():
            try:
                comp_file = get_app_dir() / "data/components" / rel_path
                with open(comp_file, "r", encoding="utf-8") as f:
                    comp_data = json.load(f)
                comp_desc = comp_data["description"]
                comp_check_box = QCheckBox(comp_desc)
                self._checkbox_to_comp_id[comp_check_box] = comp_id
                component_def = comp_data.get("components", {})
                if component_def != {}:
                    comp_group = QGroupBox(comp_desc)
                    comp_group.setVisible(False)
                    comp_group.setStyleSheet(utils.DEFAULT_GROUP_STYLE)
                    default_value = TOGGLE_DEFAULT_UNSET
                    default_factory = None
                    if isinstance(component_def, dict):
                        component_type = component_def.get("type")
                        if component_type == "bool":
                            default_value = component_def.get("default", False)
                        elif component_type == "list":
                            default_factory = list
                        elif component_type == "dict":
                            default_factory = dict
                    comp_check_box.stateChanged.connect(
                        self._gen_toggle_component(
                            comp_check_box,
                            comp_id,
                            comp_group,
                            default_value,
                            default_factory,
                            component_def,
                        )
                    )

                    self._comp_group_boxes.append(comp_group)
                    self.content_groups.append(comp_group)

                if component_def == {}:
                    comp_check_box.stateChanged.connect(
                        self._gen_toggle_component(comp_check_box, comp_id)
                    )

                cat = self._comp_id_to_category.get(comp_id, "其他")
                self._category_flows[cat].addWidget(comp_check_box)

            except Exception as e:
                logger.error(f"加载组件定义文件 {rel_path} 失败: {e}")
            else:
                logger.info(f"已加载组件定义文件: {rel_path}")

        # 4. 显示有组件的分类子分组，隐藏空分类
        for cat_name, flow_obj in self._category_flows.items():
            self._category_groups[cat_name].setVisible(flow_obj.count() > 0)

        # 5. 还原当前物品中已勾选的组件（按组件 ID 保留已编辑的值）
        for comp_id in self.current_item.components:
            for checkbox, cid in self._checkbox_to_comp_id.items():
                if cid == comp_id:
                    checkbox.setChecked(True)
                    break

        # 6. 设置大小策略并重新布局列
        for w in self.content_groups:
            # 设置 size policy 以避免被强制垂直拉伸（高度随内容变化）
            w.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
        self._last_cols = 0
        self._arrange_columns()

    def _gen_toggle_component(
        self,
        check_box: QCheckBox,
        comp_id: str,
        group_box: QGroupBox | None = None,
        default_value=TOGGLE_DEFAULT_UNSET,
        default_factory=None,
        component_def: dict | None = None,
    ):
        """工厂函数，切换组件启用状态并同步到 Item.components。"""

        def toggle():
            is_checked = check_box.isChecked()
            path = DataPath(self.current_item, comp_id)
            if is_checked:
                if path.read() is None:
                    if default_value is not TOGGLE_DEFAULT_UNSET:
                        path.write(default_value)
                    elif default_factory is not None:
                        path.write(default_factory())
                    else:
                        path.write({})
                if group_box is not None and component_def is not None:
                    self._rebuild_component_group(group_box, component_def, comp_id)
            else:
                path.delete()
                if group_box is not None:
                    layout = group_box.layout()
                    if layout is not None:
                        utils.clear_layout(layout)
            if group_box is not None:
                group_box.setVisible(is_checked)

        return toggle

    def _rebuild_component_group(
        self, group_box: QGroupBox, component_def: dict, comp_id: str
    ) -> None:
        layout = group_box.layout()
        if layout is None:
            layout = QVBoxLayout(group_box)
        else:
            utils.clear_layout(layout)
        layout.setContentsMargins(10, 0, 10, 10)
        layout.setSpacing(10)
        layout.addLayout(component.load_component(component_def, self.current_item, comp_id))  # type: ignore

    def _arrange_columns(self):
        """根据窗口宽度把 content_groups 布局为 1/2/3 列。"""
        if not hasattr(self, "content_layout"):
            return

        width = max(200, self.width())
        # 简单阈值：小窗 -> 1 列，中窗 -> 2 列，大窗 -> 3 列
        if width < 900:
            cols = 1
        elif width < 1350:
            cols = 2
        else:
            cols = 3

        # 如果列数与上次相同且已存在列容器，则不重新布局（减少无谓重建以避免闪烁）
        if getattr(self, "_last_cols", 0) == cols and self._column_widgets:
            return

        # 要分配的 widgets 列表（保持原始顺序，包含所有分区，隐藏的分区会被 layout 忽略）
        widgets = [w for w in self.content_groups]

        # 清空当前 content_layout（移除旧的列容器）并保留原列容器以便回收
        # 先收集当前列 widgets（若存在）
        old_columns = list(self._column_widgets)
        # 移除所有 column widget 从 layout 中
        while self.content_layout.count():
            item = self.content_layout.takeAt(0)
            if item is None:
                break
            wid = item.widget()
            if wid:
                try:
                    self.content_layout.removeWidget(wid)
                except Exception:
                    pass

        # 清空旧列记录
        self._column_widgets = []

        # 创建 cols 个列容器（每列内部为 QVBoxLayout），并加入 content_layout
        for i in range(cols):
            col_widget = QWidget()
            col_layout = QVBoxLayout(col_widget)
            col_layout.setContentsMargins(0, 0, 0, 0)
            col_layout.setSpacing(6)
            # 列内部顶部对齐
            try:
                col_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
            except Exception:
                pass
            self.content_layout.addWidget(col_widget)
            self._column_widgets.append(col_widget)

        # 将分区按轮询放入各列（列内垂直堆叠，列之间高度互不影响）
        for idx, w in enumerate(widgets):
            target = idx % cols
            col_layout = self._column_widgets[target].layout()
            if col_layout is not None:
                # 移除 widget 在旧父布局中的位置（如果存在），再加入新列
                try:
                    parent_layout = w.parent().layout() if w.parent() else None  # type: ignore
                    if parent_layout is not None:
                        try:
                            parent_layout.removeWidget(w)
                        except Exception:
                            pass
                except Exception:
                    pass
                col_layout.addWidget(w)

        self._last_cols = cols

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # 在调整大小时重新布局列
        try:
            self._arrange_columns()
        except Exception:
            pass

    def on_select_base_item(self):
        """选择基础物品作为模板"""
        # 调用外部函数选择基础物品（only_basic=True 排除自定义物品）
        base_item = item_selector.choose_item(only_basic=True)
        if base_item:
            self._apply_base_item(base_item)

    def _apply_base_item(self, base_item: item.Item):
        """应用选中的基础物品到编辑器"""
        self.current_item.name = base_item.name
        self.current_item.id = base_item.id

        # 更新图标显示
        pixmap = self._load_icon_or_placeholder(self.current_item)
        self.base_icon_label.setPixmap(
            pixmap.scaled(
                64,
                64,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.FastTransformation,
            )
        )

        # 更新基础物品信息文本
        self.base_item_info.setText(
            f"{self.current_item.name}\n({self.current_item.id})"
        )

        # 更新数量输入框
        self.count_spin.setValue(self.current_item.count)

        logger.info(
            f"已加载基础物品: {self.current_item.name} ({self.current_item.id})"
        )

    def _load_icon_or_placeholder(self, item: item.Item) -> QPixmap:
        """加载物品图标或生成占位图（复用ItemWidget的逻辑）"""
        icon_path = str(get_app_dir() / "data/textures" / f"{item.id.removeprefix('minecraft:')}.png")

        if os.path.exists(icon_path):
            try:
                return QPixmap(icon_path)
            except Exception as e:
                logger.warning(f"加载图标失败: {icon_path}，错误: {e}")

        # 生成带首字母的彩色占位图
        pixmap = QPixmap(64, 64)
        pixmap.fill(QColor("#3498db"))
        painter = QPainter(pixmap)
        painter.setPen(QColor("white"))
        font = QFont("Arial", 24, QFont.Weight.Bold)
        painter.setFont(font)
        text = item.name[0] if item.name else "?"
        fm = painter.fontMetrics()
        rect = fm.boundingRect(text)
        x = (64 - rect.width()) // 2
        y = (64 + rect.height()) // 2
        painter.drawText(x, y, text)
        painter.end()
        return pixmap

    def on_save(self):
        """保存自定义物品到JSON文件"""
        if self.current_item is None:
            QMessageBox.warning(self, "提示", "请先选择基础物品！")
            return

        save_name = self.save_name_edit.text().strip()
        if not save_name:
            QMessageBox.warning(self, "提示", "请输入保存文件名！")
            self.save_name_edit.setFocus()
            return

        # 确保data/items目录存在
        save_dir = get_app_dir() / "custom/items"
        save_dir.mkdir(parents=True, exist_ok=True)

        # 构建保存路径
        save_path = save_dir / f"{save_name}.json"

        try:
            # 使用Item的to_json方法生成JSON内容
            json_content = self.current_item.to_dict()
            del json_content["categories"]  # 不保存分类信息

            # 写入文件
            with open(save_path, "w", encoding="utf-8") as f:
                json.dump(json_content, f, ensure_ascii=False, indent=4)

            logger.info(f"自定义物品已保存: {save_path}")
            QMessageBox.information(self, "保存成功", f"物品已保存到:\n{save_path}")

        except Exception as e:
            logger.error(f"保存失败: {e}")
            QMessageBox.critical(self, "保存失败", f"保存文件时发生错误:\n{e}")

    def on_load(self):
        """从 JSON 文件加载已保存的自定义物品。"""
        # 检查是否有未保存的修改
        if self._has_unsaved_changes():
            reply = QMessageBox.question(
                self,
                "确认加载",
                "当前编辑器中有未保存的修改，加载将丢弃这些修改。\n是否继续？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return

        # 打开文件选择对话框
        start_dir = str((get_app_dir() / "custom/items").resolve())
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择自定义物品 JSON", start_dir, "JSON Files (*.json)"
        )
        if not file_path:
            return

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            loaded_item = item.Item.from_dict(data)
            self._apply_loaded_item(loaded_item, file_path)
            logger.info(f"已加载自定义物品: {file_path}")

        except Exception as e:
            logger.exception("加载物品失败")
            QMessageBox.critical(self, "加载失败", f"读取文件时发生错误:\n{e}")

    def _has_unsaved_changes(self) -> bool:
        """检查当前是否有未保存的编辑内容。"""
        return bool(self.current_item.id) or bool(self.current_item.components)

    def _apply_loaded_item(self, loaded_item: item.Item, file_path: str) -> None:
        """将加载的物品应用到编辑器 UI。

        流程：先取消所有复选框（操作旧 current_item）→ 替换 current_item
        → 更新基础信息显示 → 勾选加载数据中存在的组件 → toggle 自动重建 UI。
        """
        # 1. 取消所有已勾选的复选框（toggle 会操作旧的 current_item，即将被替换）
        for checkbox in self._checkbox_to_comp_id:
            if checkbox.isChecked():
                checkbox.setChecked(False)

        # 2. 替换为加载的物品
        self.current_item = loaded_item

        # 3. 更新基础物品显示
        pixmap = self._load_icon_or_placeholder(self.current_item)
        self.base_icon_label.setPixmap(
            pixmap.scaled(
                64,
                64,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.FastTransformation,
            )
        )
        self.base_item_info.setText(
            f"{self.current_item.name}\n({self.current_item.id})"
        )

        # 4. 更新数量
        self.count_spin.setValue(self.current_item.count)

        # 5. 从文件路径提取文件名填入保存名
        save_name = Path(file_path).stem
        self.save_name_edit.setText(save_name)

        # 6. 勾选加载数据中存在的组件
        for comp_id in self.current_item.components:
            for checkbox, cid in self._checkbox_to_comp_id.items():
                if cid == comp_id:
                    checkbox.setChecked(True)
                    break

        logger.info(
            f"已还原物品到编辑器: {loaded_item.name} ({loaded_item.id}), "
            f"组件数={len(loaded_item.components)}"
        )

    def on_generate(self):
        """生成并展示Minecraft标准give命令"""
        if self.current_item is None or not self.current_item.id:
            QMessageBox.warning(self, "提示", "请先选择基础物品！")
            return

        item_stack = self.current_item.item_stack()
        command = f"/give @p {item_stack}"
        if self.current_item.count != 1:
            command += f" {self.current_item.count}"

        dialog = QDialog(self)
        dialog.setWindowTitle("命令窗口")
        dialog.resize(560, 240)

        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        if len(command) > 256:
            command = command.removeprefix("/")
            warning_label = QLabel(
                "命令长度超过256个字符，请在命令方块或服务器控制台中执行。"
            )
            warning_label.setWordWrap(True)
            warning_label.setStyleSheet("font-weight: bold;")
            layout.addWidget(warning_label)

        text_box = QPlainTextEdit()
        text_box.setReadOnly(True)
        text_box.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        text_box.setPlainText(command)
        layout.addWidget(text_box)

        button_layout = QHBoxLayout()
        button_layout.addStretch()

        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(dialog.accept)
        button_layout.addWidget(close_btn)

        copy_btn = QPushButton("复制命令")
        copy_btn.setStyleSheet(utils.BIG_GREEN_BUTTON_STYLE)

        def copy_command():
            QGuiApplication.clipboard().setText(command)  # type: ignore

        copy_btn.clicked.connect(copy_command)
        button_layout.addWidget(copy_btn)

        layout.addLayout(button_layout)

        dialog.exec()


def open_item_editor(parent=None) -> item.Item | None:
    """
    打开自定义物品编辑器窗口。

    Returns:
        如果保存成功，返回创建的Item对象；否则返回None。
    """
    logger.info("打开自定义物品编辑器")

    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)

    app.setStyle("Fusion")  # type: ignore
    dialog = ItemEditorDialog(parent)

    # 居中显示
    if app.primaryScreen():  # type: ignore
        dialog.move(app.primaryScreen().geometry().center() - dialog.rect().center())  # type: ignore

    if dialog.exec() == QDialog.DialogCode.Accepted:
        return dialog.current_item
    return None


if __name__ == "__main__":
    open_item_editor()
