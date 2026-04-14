"""
创建和保存自定义物品。
"""

import json
import logging
import os
import sys
from pathlib import Path

from PyQt6.QtCore import QPoint, QRect, QSize, Qt
from PyQt6.QtGui import QColor, QFont, QPainter, QPixmap
from PyQt6.QtWidgets import (QApplication, QCheckBox, QComboBox, QDialog,
                             QGridLayout, QGroupBox, QHBoxLayout, QLabel,
                             QLayout, QLayoutItem, QLineEdit, QMessageBox,
                             QPushButton, QScrollArea, QSizePolicy, QSpinBox,
                             QVBoxLayout, QWidget)

import component
import item
import item_selector
import utils

logger = logging.getLogger(__name__)


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

        save_layout.addWidget(QLabel("保存名："))
        self.save_name_edit = QLineEdit()
        self.save_name_edit.setPlaceholderText("输入文件名（不含.json）")
        self.save_name_edit.setMinimumWidth(160)
        self.save_name_edit.setStyleSheet(
            """
            QLineEdit {
                padding: 6px;
                border-radius: 4px;
                border: 1px solid #ccc;
            }
            QLineEdit:focus {
                border: 2px solid #3498db;
            }
            """
        )
        save_layout.addWidget(self.save_name_edit)

        self.save_btn = QPushButton("保存")
        self.save_btn.clicked.connect(self.on_save)
        self.save_btn.setMinimumWidth(80)
        self.save_btn.setStyleSheet(utils.BIG_GREEN_BUTTON_STYLE)
        save_layout.addWidget(self.save_btn)

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
        basic_group = QGroupBox("基本设置")
        basic_group.setStyleSheet(utils.DEFAULT_GROUP_STYLE)
        basic_layout = QVBoxLayout(basic_group)
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

        # === 物品堆叠组件功能（把若干控制开关放入横向换行的分组） ===
        self.components_group = QGroupBox("物品堆叠组件功能")
        self.components_group.setStyleSheet(utils.DEFAULT_GROUP_STYLE)
        comps_layout = QVBoxLayout(self.components_group)
        comps_layout.setContentsMargins(10, 0, 10, 10)
        comps_layout.setSpacing(6)

        flow_container = QWidget()
        flow = utils.FlowLayout()
        flow.setSpacing(8)
        flow_container.setLayout(flow)

        comps_layout.addWidget(flow_container)
        basic_layout.addWidget(self.components_group)

        # 将分区放入 content_widget 的布局中，后续根据窗口宽度自动分栏
        self.content_groups = [basic_group]

        for file in Path("data/components").glob("*.json"):
            with open(file, "r", encoding="utf-8") as f:
                try:
                    comp_data = json.load(f)
                    comp_id = comp_data["id"]
                    comp_desc = comp_data["description"]
                    comp_check_box = QCheckBox(comp_desc)
                    if comp_data.get("components", {}) != {}:
                        comp_group = QGroupBox(comp_desc)
                        comp_group.setVisible(False)
                        comp_group.setStyleSheet(utils.DEFAULT_GROUP_STYLE)
                        comp_check_box.stateChanged.connect(
                            self._gen_toggle_settings_visibility(
                                comp_check_box, comp_group
                            )
                        )

                        comp_layout = QVBoxLayout(comp_group)
                        comp_layout.setContentsMargins(10, 0, 10, 10)
                        comp_layout.setSpacing(10)

                        layout = component.load_component(
                            comp_data["components"], self.current_item, comp_id
                        )
                        comp_layout.addLayout(layout)

                        self.content_groups.append(comp_group)

                    flow.addWidget(comp_check_box)

                except Exception as e:
                    logger.error(f"加载组件定义文件 {file.name} 失败: {e}")
                else:
                    logger.info(f"已加载组件定义文件: {file.name}")

        # 初始把控件属性设置，实际放置到列中在 _arrange_columns 时完成
        for w in self.content_groups:
            # 设置 size policy 以避免被强制垂直拉伸（高度随内容变化）
            w.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)

        main_layout.addWidget(self.scroll_area)

        # 根据当前窗口宽度安排列数
        self._last_cols = 0
        self._arrange_columns()

        # === 占位：其他分区后续添加 ===
        # TODO: 添加组件编辑、分类选择、NBT编辑等其他分区

    def _update_count(self, value):
        """更新当前编辑物品的数量"""
        self.current_item.count = value

    def _gen_toggle_settings_visibility(
        self, check_box: QCheckBox, group_box: QGroupBox
    ):
        """工厂函数，根据 check_box 的状态显示/隐藏 group_box"""

        def toggle():
            is_checked = check_box.isChecked()
            group_box.setVisible(is_checked)

        return toggle

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
        icon_path = "data/textures" + "/" + item.id.removeprefix("minecraft:") + ".png"

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
        save_dir = "data/items"
        os.makedirs(save_dir, exist_ok=True)

        # 构建保存路径
        save_path = os.path.join(save_dir, f"{save_name}.json")

        try:
            # 使用Item的to_json方法生成JSON内容
            json_content = self.current_item.to_json()

            # 写入文件
            with open(save_path, "w", encoding="utf-8") as f:
                json.dump(json_content, f, ensure_ascii=False, indent=4)

            logger.info(f"自定义物品已保存: {save_path}")
            QMessageBox.information(self, "保存成功", f"物品已保存到:\n{save_path}")

        except Exception as e:
            logger.error(f"保存失败: {e}")
            QMessageBox.critical(self, "保存失败", f"保存文件时发生错误:\n{e}")


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
