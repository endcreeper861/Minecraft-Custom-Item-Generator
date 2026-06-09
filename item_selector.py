import logging
import os
import sys

from PyQt6.QtCore import QSize, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QPainter, QPixmap
from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

import item
import item_editor

logger = logging.getLogger(__name__)


class ItemWidget(QWidget):
    """
    单个物品的显示组件：图标 + 名称
    点击时发射 clicked 信号
    """

    clicked = pyqtSignal(object)  # 发射选中的 Item 对象

    def __init__(self, item: item.Item, parent=None):
        super().__init__(parent)
        self.item = item
        self.setup_ui()
        # 设置悬停提示为 ID
        self.setToolTip(item.id)
        # 设置鼠标跟踪以支持 hover 效果（如果需要改变样式）
        self.setMouseTracking(True)

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(2)

        # 图标标签
        self.icon_label = QLabel()
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.icon_label.setFixedSize(64, 64)

        # 尝试加载图片，如果失败则生成一个占位图
        pixmap = self.load_icon_or_placeholder(self.item)
        self.icon_label.setPixmap(
            pixmap.scaled(
                64,
                64,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.FastTransformation,
            )
        )

        # 名称标签
        self.name_label = QLabel(self.item.name)
        self.name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.name_label.setWordWrap(True)
        self.name_label.setFont(QFont("Segoe UI", 9))
        # 限制最大行数，防止名字太长
        self.name_label.setMaximumHeight(40)

        layout.addWidget(self.icon_label)
        layout.addWidget(self.name_label)

        # 设置样式，使其看起来像可选中的项目
        self.setStyleSheet("""
            ItemWidget {
                border-radius: 4px;
                background-color: transparent;
            }
            ItemWidget:hover {
                background-color: rgba(0, 0, 0, 0.1);
            }
        """)

    def load_icon_or_placeholder(self, item: item.Item) -> QPixmap:
        icon_path = "data/textures" + "/" + item.id.removeprefix("minecraft:") + ".png"

        if os.path.exists(icon_path):
            try:
                return QPixmap(icon_path)
            except Exception as e:
                logger.warning(f"加载图标失败: {icon_path}，错误: {e}")

        # 生成一个带首字母的彩色占位图
        pixmap = QPixmap(64, 64)
        pixmap.fill(QColor("#3498db"))  # 默认蓝色
        painter = QPainter(pixmap)
        painter.setPen(QColor("white"))
        font = QFont("Arial", 24, QFont.Weight.Bold)
        painter.setFont(font)
        text = item.name[0] if item.name else "?"
        # 简单计算文字居中
        fm = painter.fontMetrics()
        rect = fm.boundingRect(text)
        x = (64 - rect.width()) // 2
        y = (64 + rect.height()) // 2  # 基线调整
        painter.drawText(x, y, text)
        painter.end()
        return pixmap

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.item)
        super().mousePressEvent(event)


# --- 主窗口 (ItemSelectorDialog) ---


class ItemSelectorDialog(QDialog):
    # 分类映射：显示文本 -> 对应 tag
    CATEGORY_MAP = {
        "所有物品": "all",
        "自定义物品": "custom",
        "建筑方块": "building",
        "染色方块": "dyed",
        "自然方块": "natural",
        "功能方块": "functional",
        "红石方块": "redstone",
        "工具与实用物品": "tool",
        "战斗用品": "combat",
        "食物与饮品": "food",
        "原材料": "material",
        "刷怪蛋": "spawn_egg",
        "管理员用品": "admin",
    }

    def __init__(self, all_items: list[item.Item], only_basic=False, parent=None):
        super().__init__(parent)
        self.all_items = all_items
        self.selected_item: item.Item | None = None
        self.only_basic = only_basic

        self.setWindowTitle("选择物品")
        self.resize(800, 600)
        self.setup_ui()
        self.refresh_list()

    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)

        # --- 顶部区域 ---
        top_layout = QHBoxLayout()

        # 左侧：分类下拉框
        self.category_combo = QComboBox()
        if self.only_basic:
            # 只显示非自定义物品的分类
            for display, tag in self.CATEGORY_MAP.items():
                if tag != "custom":
                    self.category_combo.addItem(display)
        else:
            self.category_combo.addItems(self.CATEGORY_MAP.keys())
        self.category_combo.currentTextChanged.connect(self.refresh_list)
        # 设置最小宽度，防止太窄
        self.category_combo.setMinimumWidth(150)

        # 右侧：创建新物品按钮
        if not self.only_basic:
            self.create_btn = QPushButton("创建新自定义物品")
            self.create_btn.clicked.connect(self.on_create_new)

        top_layout.addWidget(self.category_combo)
        top_layout.addStretch()  # 弹簧，把按钮推到右边
        if not self.only_basic:
            top_layout.addWidget(self.create_btn)

        # --- 中间区域：搜索框 ---
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("搜索物品名称或 ID...")
        self.search_box.textChanged.connect(self.refresh_list)
        # 搜索框样式
        self.search_box.setStyleSheet("""
            QLineEdit {
                padding: 8px;
                border-radius: 4px;
                border: 1px solid #ccc;
            }
            QLineEdit:focus {
                border: 2px solid #3498db;
            }
        """)

        # --- 底部区域：网格列表 ---
        self.item_list = QListWidget()
        self.item_list.setViewMode(QListWidget.ViewMode.IconMode)
        self.item_list.setMovement(QListWidget.Movement.Static)  # 不可拖拽
        self.item_list.setResizeMode(QListWidget.ResizeMode.Adjust)  # 适应宽度
        self.item_list.setWrapping(True)  # 允许换行
        self.item_list.setGridSize(QSize(90, 110))  # 每个格子的大小
        self.item_list.setSpacing(10)
        self.item_list.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )  # 隐藏横向滚动条，靠自动换行
        # 隐藏默认的项目文本，因为我们用自定义 Widget
        self.item_list.setModelColumn(0)

        # 组装布局
        main_layout.addLayout(top_layout)
        main_layout.addWidget(self.search_box)
        main_layout.addWidget(self.item_list)

    def on_create_new(self):
        item_editor.open_item_editor()
        self.all_items = (
            item.get_all_items(self.only_basic)
        )  # 重新加载物品列表，包含新创建的自定义物品
        self.refresh_list()

    def refresh_list(self):
        self.item_list.clear()

        # 获取当前分类 tag
        category_text = self.category_combo.currentText()
        target_category = self.CATEGORY_MAP[category_text]

        # 获取搜索文本
        search_text = self.search_box.text().lower()

        for item in self.all_items:
            # 1. 分类过滤
            if target_category != "all":
                if item.categories is None:
                    continue
                if target_category not in item.categories:
                    continue

            # 2. 搜索过滤
            if search_text:
                if (
                    search_text not in item.name.lower()
                    and search_text not in item.id.lower()
                ):
                    continue

            # 创建列表项
            list_item = QListWidgetItem()
            # 设置大小以匹配 GridSize，确保布局整齐
            list_item.setSizeHint(QSize(90, 110))

            # 创建自定义 Widget
            widget = ItemWidget(item)
            widget.clicked.connect(self.on_item_clicked)

            self.item_list.addItem(list_item)
            self.item_list.setItemWidget(list_item, widget)

    def on_item_clicked(self, item: item.Item):
        self.selected_item = item
        self.accept()  # 关闭对话框并返回 Accepted

    def get_selected_item(self) -> item.Item | None:
        return self.selected_item


def choose_item(only_basic=False, parent=None) -> item.Item | None:
    """
    打开物品选择窗口。

    Args:
        only_basic: 如果为 True，则只可选择自定义物品外的基本物品。
        parent: 父级窗口。

    Returns:
        选中的 Item 对象，或 None（如果取消选择）。
    """
    logger.info("打开物品选择窗口")

    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)

    # 确保应用了系统样式（深色/浅色模式支持）
    # PyQt6 6.2+ 通常会自动跟随系统，但显式设置 Fusion 风格通常兼容性更好
    app.setStyle("Fusion")  # type: ignore
    dialog = ItemSelectorDialog(
        item.get_all_items(only_basic), only_basic=only_basic, parent=parent
    )

    # 居中显示
    dialog.move(app.primaryScreen().geometry().center() - dialog.rect().center())  # type: ignore

    if dialog.exec() == QDialog.DialogCode.Accepted:
        logger.info(f"选择物品: {dialog.get_selected_item().name} ({dialog.get_selected_item().id})")  # type: ignore
        return dialog.get_selected_item()

    logger.info("取消物品选择")
    return None


# --- 测试运行 ---

if __name__ == "__main__":
    # 模拟调用
    app = QApplication(sys.argv)

    # 设置深色模式测试（可选，注释掉则跟随系统）
    # app.setStyle("Fusion")
    # from PyQt6.QtGui import QPalette, QColor
    # palette = QPalette()
    # palette.setColor(QPalette.ColorRole.Window, QColor(53, 53, 53))
    # palette.setColor(QPalette.ColorRole.WindowText, Qt.GlobalColor.white)
    # app.setPalette(palette)

    print("打开物品选择窗口...")

    result = choose_item()

    if result:
        print(f"用户选择了: {result.name} (ID: {result.id})")
    else:
        print("用户取消了选择。")
