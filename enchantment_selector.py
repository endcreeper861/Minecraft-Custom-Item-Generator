import json
import logging
import sys
from pathlib import Path

from PyQt6.QtCore import QEventLoop, Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QInputDialog,
    QFileDialog,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QToolTip,
    QVBoxLayout,
    QWidget,
)

import enchantment
import utils

logger = logging.getLogger(__name__)


CUSTOM_ENCHANTMENTS_DIR = "custom/enchantments/"


class CustomTableWidget(QTableWidget):
    """自定义表格，用于处理悬停提示和点击事件"""

    def __init__(self, parent=None, is_source=True):
        super().__init__(parent)
        self.is_source = is_source  # True表示是右侧"全部"，False表示左侧"已选"
        self.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )  # 禁止直接编辑文本
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setShowGrid(False)
        self.verticalHeader().setVisible(False)  # type: ignore
        self.horizontalHeader().setStretchLastSection(True)  # type: ignore
        self.setStyleSheet("QTableWidget { border: 1px solid #ddd; }")

        # 绑定鼠标移动事件以显示 Tooltip
        self.cellEntered.connect(self.on_cell_entered)
        logger.debug("自定义表格已初始化（is_source=%s）", self.is_source)

    def on_cell_entered(self, row, col):
        logger.debug("鼠标移入单元格：行=%s 列=%s is_source=%s", row, col, self.is_source)
        if row == -1:
            return
        if self.is_source:
            QToolTip.showText(self.mapToGlobal(self.cursor().pos()), "点击选择", self)
        else:
            QToolTip.showText(self.mapToGlobal(self.cursor().pos()), "点击移除", self)

    def mousePressEvent(self, event):
        # 获取点击位置对应的行
        item = self.itemAt(event.pos())
        if item:
            row = item.row()
            logger.debug("表格被点击：行=%s is_source=%s", row, self.is_source)
            # 使用 self.window() 获取主窗口
            main_window = self.window()
            if isinstance(main_window, EnchantmentWindow):
                if self.is_source:
                    main_window.move_to_selected(row)
                else:
                    main_window.move_to_unselected(row)
        super().mousePressEvent(event)


class EnchantmentWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("附魔选择器")
        self.resize(1000, 600)

        # 存储当前所有可用的附魔数据（用于搜索和恢复）
        self.all_enchantments = enchantment.get_all_enchantments()
        logger.info("已加载 %d 个附魔", len(self.all_enchantments))
        # 存储已选附魔的 ID 集合，防止重复添加
        self.selected_ids = set()
        # 保存后返回的 EnchantmentGroup（若未保存则为 None）
        self.saved_group = None

        self.init_ui()

    def init_ui(self):
        logger.debug("初始化附魔窗口 UI")
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)

        # --- 顶部区域 ---
        top_layout = QHBoxLayout()

        # 左侧：加载/保存预设按钮
        self.load_preset_btn = QPushButton("加载预设")
        self.load_preset_btn.setFixedHeight(35)
        self.load_preset_btn.clicked.connect(self.load_preset)
        top_layout.addWidget(self.load_preset_btn)

        self.save_preset_btn = QPushButton("保存预设")
        self.save_preset_btn.setFixedHeight(35)
        self.save_preset_btn.clicked.connect(self.save_preset)
        top_layout.addWidget(self.save_preset_btn)

        # 在左侧按钮和右侧“确定”之间添加伸缩，使“确定”靠右
        top_layout.addStretch(1)

        # 右侧“确定”按钮（替代旧的“保存”按钮）
        self.ok_btn = QPushButton("确定")
        self.ok_btn.setFixedHeight(35)
        self.ok_btn.setStyleSheet(utils.BIG_GREEN_BUTTON_STYLE)
        self.ok_btn.clicked.connect(self.confirm_group)
        top_layout.addWidget(self.ok_btn)

        main_layout.addLayout(top_layout)

        # --- 主体分割区域 ---
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # 左侧：已选附魔
        left_group = QGroupBox("已选附魔（点击移除）")
        left_layout = QVBoxLayout(left_group)
        self.selected_table = CustomTableWidget(self, is_source=False)
        self.selected_table.setColumnCount(4)
        self.selected_table.setHorizontalHeaderLabels(["名称", "ID", "描述", "等级"])
        self.selected_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)  # type: ignore
        self.selected_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)  # type: ignore
        self.selected_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)  # type: ignore
        self.selected_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)  # type: ignore
        self.selected_table.setColumnWidth(3, 100)  # 等级列固定宽度
        left_layout.addWidget(self.selected_table)

        # 右侧：全部附魔
        right_group = QGroupBox("全部附魔（点击选择）")
        right_layout = QVBoxLayout(right_group)

        # 搜索框
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("表格筛选：输入名称或ID搜索...")
        self.search_input.textChanged.connect(self.filter_table)
        right_layout.addWidget(self.search_input)

        self.all_table = CustomTableWidget(self, is_source=True)
        self.all_table.setColumnCount(3)
        self.all_table.setHorizontalHeaderLabels(["名称", "ID", "描述"])
        self.all_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)  # type: ignore
        self.all_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)  # type: ignore
        self.all_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)  # type: ignore

        # 初始化右侧表格数据
        self.populate_all_table()

        right_layout.addWidget(self.all_table)

        splitter.addWidget(left_group)
        splitter.addWidget(right_group)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 1)
        # 设置初始大小为等分，确保左右各占一半
        splitter.setSizes([500, 500])

        main_layout.addWidget(splitter)

    def populate_all_table(self, filter_text=""):
        logger.debug("填充全部附魔表，筛选=%r", filter_text)
        self.all_table.setRowCount(0)  # 清空
        for i, data in enumerate(self.all_enchantments):
            # 简单的搜索过滤
            if (
                filter_text
                and filter_text.lower() not in data.name.lower()
                and filter_text.lower() not in data.id.lower()
            ):
                continue

            row_pos = self.all_table.rowCount()
            self.all_table.insertRow(row_pos)

            item_name = QTableWidgetItem(data.name)
            item_id = QTableWidgetItem(data.id)
            item_desc = QTableWidgetItem(data.description)

            self.all_table.setItem(row_pos, 0, item_name)
            self.all_table.setItem(row_pos, 1, item_id)
            self.all_table.setItem(row_pos, 2, item_desc)
        logger.debug("填充全部附魔表完成，行数=%d", self.all_table.rowCount())

    def filter_table(self, text):
        logger.debug("筛选表格文本=%r", text)
        self.populate_all_table(text)

    def move_to_selected(self, row):
        logger.debug("将附魔移到已选：行=%s", row)
        # 获取右侧表格该行的数据
        item_id_item = self.all_table.item(row, 1)
        if not item_id_item:
            logger.warning("未在第 %s 行找到项目", row)
            return
        item_id = item_id_item.text()

        if item_id in self.selected_ids:
            logger.warning("尝试添加重复附魔 id=%s", item_id)
            return  # 防止重复添加

        name_item = self.all_table.item(row, 0)
        desc_item = self.all_table.item(row, 2)
        if not name_item or not desc_item:
            logger.warning("第 %s 行缺少名称或描述", row)
            return

        name = name_item.text()
        desc = desc_item.text()

        # 找到原始数据以获取等级限制
        original_data = next((x for x in self.all_enchantments if x.id == item_id), None)
        if not original_data:
            logger.warning("未找到 id=%s 的原始数据", item_id)
            return

        # 添加到左侧表格
        row_pos = self.selected_table.rowCount()
        self.selected_table.insertRow(row_pos)

        self.selected_table.setItem(row_pos, 0, QTableWidgetItem(name))
        self.selected_table.setItem(row_pos, 1, QTableWidgetItem(item_id))
        self.selected_table.setItem(row_pos, 2, QTableWidgetItem(desc))

        # 创建等级输入框
        level_input = QLineEdit()
        level_input.setAlignment(Qt.AlignmentFlag.AlignCenter)
        level_input.setPlaceholderText(f"最高等级：{original_data.max_level}")
        level_input.setStyleSheet("QSpinBox { border: 1px solid #ccc; border-radius: 2px; }")

        self.selected_table.setCellWidget(row_pos, 3, level_input)

        # 标记为已选
        self.selected_ids.add(item_id)
        logger.info("已添加附魔：%s（%s），最大等级=%s", name, item_id, original_data.max_level)

        # 刷新表格显示
        logger.debug("选择后刷新表格，id=%s", item_id)
        self.refresh_tables()

    def move_to_unselected(self, row):
        logger.debug("将附魔从已选移出：行=%s", row)
        # 获取左侧表格该行的 ID
        item_id_item = self.selected_table.item(row, 1)
        if not item_id_item:
            logger.warning("未在第 %s 行找到项目（取消选择）", row)
            return
        item_id = item_id_item.text()

        # 从已选集合移除
        if item_id in self.selected_ids:
            self.selected_ids.remove(item_id)
            logger.info("已从已选集合移除附魔 id=%s", item_id)

        # 从左侧表格移除行
        self.selected_table.removeRow(row)

        # 刷新右侧表格以显示刚才移除的项目
        logger.debug("取消选择后刷新表格，id=%s", item_id)
        self.refresh_tables()

    def refresh_tables(self):
        logger.debug("刷新表格调用")
        # 刷新右侧表格（恢复被移除的项）
        current_filter = self.search_input.text()
        logger.debug("刷新表格，使用筛选=%r", current_filter)
        self.populate_all_table(current_filter)

    def collect_group(self) -> enchantment.EnchantmentGroup:
        logger.debug("收集附魔组，已选行数=%d", self.selected_table.rowCount())
        enchantments = []
        for row in range(self.selected_table.rowCount()):
            item_id_item = self.selected_table.item(row, 1)
            name_item = self.selected_table.item(row, 0)
            if not item_id_item or not name_item:
                continue
            item_id = item_id_item.text()
            name = name_item.text()

            original = next((x for x in self.all_enchantments if x.id == item_id), None)
            max_level = original.max_level if original else None
            desc = original.description if original else ""

            level = 1
            widget = self.selected_table.cellWidget(row, 3)
            if widget:
                try:
                    text = widget.text().strip()  # type: ignore
                    if text:
                        level = int(text)
                except Exception:
                    level = 1

            if max_level is not None and level > max_level:
                level = max_level

            ench = enchantment.Enchantment(
                name=name,
                id=item_id,
                max_level=max_level,
                description=desc,
                level=level,
            )
            enchantments.append(ench)
        logger.debug("收集完成，共 %d 个附魔", len(enchantments))
        return enchantment.EnchantmentGroup(enchantments=enchantments)

    def save_preset(self):
        name, ok = QInputDialog.getText(self, "保存预设", "输入保存名:")
        if not ok:
            return
        name = name.strip()
        if not name:
            return

        safe_name = (
            "".join(c if c.isalnum() or c in (" ", "_", "-") else "_" for c in name)
            .strip()
            .replace(" ", "_")
        )

        out_dir = Path(CUSTOM_ENCHANTMENTS_DIR)
        out_dir.mkdir(parents=True, exist_ok=True)
        file_path = out_dir / f"{safe_name}.json"
        logger.info("保存预设 '%s' 到 %s", safe_name, file_path)
        group = self.collect_group()
        with file_path.open("w", encoding="utf-8") as f:
            json.dump(group.to_dict(), f, ensure_ascii=False, indent=4)
        logger.debug("预设已写入 %s", file_path)
        self.saved_group = group
        QToolTip.showText(
            self.save_preset_btn.mapToGlobal(self.save_preset_btn.rect().center()),
            f"已保存到 {file_path}",
        )
        self.close()

    def load_preset(self):
        start_dir = str(Path(CUSTOM_ENCHANTMENTS_DIR).resolve())
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择附魔组 JSON", start_dir, "JSON Files (*.json)"
        )
        if not file_path:
            return
        logger.info("从 %s 加载预设", file_path)
        try:
            with open(file_path, encoding="utf-8") as f:
                data = json.load(f)

            if isinstance(data, dict) and "enchantments" in data:
                entries = data["enchantments"]
            else:
                entries = data

            # 清空当前已选
            self.selected_table.setRowCount(0)
            self.selected_ids.clear()

            logger.debug("已加载预设条目数量=%d", len(entries) if hasattr(entries, '__len__') else 0)

            for entry in entries:
                item_id = entry.get("id", "")
                name = entry.get("name", "")
                desc = entry.get("description", "")
                level = entry.get("level", 1)

                original = next(
                    (x for x in self.all_enchantments if x.id == item_id), None
                )
                max_level = original.max_level if original else None

                row_pos = self.selected_table.rowCount()
                self.selected_table.insertRow(row_pos)
                self.selected_table.setItem(row_pos, 0, QTableWidgetItem(name))
                self.selected_table.setItem(row_pos, 1, QTableWidgetItem(item_id))
                self.selected_table.setItem(row_pos, 2, QTableWidgetItem(desc))

                level_input = QLineEdit()
                level_input.setAlignment(Qt.AlignmentFlag.AlignCenter)
                level_input.setText(str(level) if level is not None else "")
                if max_level is not None:
                    level_input.setPlaceholderText(f"最高等级：{max_level}")
                self.selected_table.setCellWidget(row_pos, 3, level_input)

                self.selected_ids.add(item_id)

            self.refresh_tables()
        except Exception as e:
            logger.exception("加载预设失败：%s", e)
            QToolTip.showText(
                self.load_preset_btn.mapToGlobal(self.load_preset_btn.rect().center()),
                "加载失败",
            )

    def confirm_group(self):
        group = self.collect_group()
        logger.info("确认附魔组，共 %d 个附魔", len(group.enchantments) if hasattr(group, 'enchantments') else 0)
        self.saved_group = group
        self.close()


def open_enchantment_selector():
    """
    打开附魔选择器窗口并阻塞直到窗口关闭。

    Returns:
        保存后返回 EnchantmentGroup 实例；若未保存直接关闭则返回 None。
    """
    logger.debug("调用打开附魔选择器")
    app_created = False
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
        app_created = True

    window = EnchantmentWindow()
    window.show()

    if app_created:
        # 如果我们创建了 QApplication，就运行主循环直到退出
        logger.debug("运行 app.exec()（已创建 QApplication）")
        app.exec()
        saved = getattr(window, "saved_group", None)
        logger.info("附魔选择器已关闭（app_created=True），saved_group=%s", "已保存" if saved else "无")
        return saved
    else:
        # 如果已有运行的 QApplication，使用局部事件循环等待窗口销毁
        loop = QEventLoop()
        window.destroyed.connect(loop.quit)
        loop.exec()
        saved = getattr(window, "saved_group", None)
        logger.info("附魔选择器已关闭（app_created=False），saved_group=%s", "已保存" if saved else "无")
        return saved


if __name__ == "__main__":
    logger.info("作为主应用启动附魔窗口")
    app = QApplication(sys.argv)
    app.setFont(QFont(utils.DEFAULT_FONT, 9))
    window = EnchantmentWindow()
    window.show()
    sys.exit(app.exec())
