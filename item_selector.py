import logging
import os
import sys

from PyQt6.QtCore import QObject, QSize, Qt, QThread, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QImage, QPainter, QPixmap
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

# ============================================================
# 图标缓存（进程级，跨对话框生命周期）
# ============================================================

# 缓存：item_id → QPixmap（成功加载的真图）或 None（确认文件不存在）
_icon_cache: dict[str, QPixmap | None] = {}

# 哨兵：表示“尚未查询过缓存”
_NOT_LOADED = object()

# 透明占位图（惰性初始化，首次使用时才创建以避免模块导入时 QApplication 未就绪）
_transparent_pixmap: QPixmap | None = None


def _get_transparent_pixmap() -> QPixmap:
    """返回 1×1 透明 QPixmap（惰性初始化）。"""
    global _transparent_pixmap
    if _transparent_pixmap is None:
        _transparent_pixmap = QPixmap(1, 1)
        _transparent_pixmap.fill(Qt.GlobalColor.transparent)
    return _transparent_pixmap


def _get_cached_icon(item_id: str) -> QPixmap | None | object:
    """返回缓存的 QPixmap、None（已知文件缺失）、或 _NOT_LOADED（尚未查询）。"""
    if item_id in _icon_cache:
        return _icon_cache[item_id]
    return _NOT_LOADED


def _make_placeholder_pixmap(item_name: str) -> QPixmap:
    """生成一个带首字母的彩色占位图（用于文件确认不存在的物品）。"""
    pixmap = QPixmap(64, 64)
    pixmap.fill(QColor("#3498db"))  # 默认蓝色
    painter = QPainter(pixmap)
    painter.setPen(QColor("white"))
    font = QFont("Arial", 24, QFont.Weight.Bold)
    painter.setFont(font)
    text = item_name[0] if item_name else "?"
    fm = painter.fontMetrics()
    rect = fm.boundingRect(text)
    x = (64 - rect.width()) // 2
    y = (64 + rect.height()) // 2
    painter.drawText(x, y, text)
    painter.end()
    return pixmap


# ============================================================
# 图标异步加载工作线程
# ============================================================


class IconLoaderWorker(QObject):
    """在子线程中从磁盘读取 PNG 文件，通过信号将 QImage 传回主线程。"""

    icon_loaded = pyqtSignal(str, object)  # item_id, QImage 或 None

    def __init__(self, item_ids: list[str], parent=None):
        super().__init__(parent)
        self._item_ids = item_ids

    def run(self):
        for item_id in self._item_ids:
            if self.thread().isInterruptionRequested():
                return
            short_id = item_id.removeprefix("minecraft:")
            icon_path = f"data/textures/{short_id}.png"
            if os.path.exists(icon_path):
                try:
                    image = QImage(icon_path)
                    if not image.isNull():
                        self.icon_loaded.emit(item_id, image)
                        continue
                except Exception as e:
                    logger.warning(f"加载图标失败: {icon_path}，错误: {e}")
            # 文件不存在或加载失败 → 通知主线程标记为缺失
            self.icon_loaded.emit(item_id, None)


class ItemWidget(QWidget):
    """
    单个物品的显示组件：图标 + 名称，支持三态图标加载（透明→真图→彩色占位）。
    点击时发射 clicked 信号。
    """

    clicked = pyqtSignal(object)  # 发射选中的 Item 对象

    def __init__(self, item: item.Item, parent=None):
        super().__init__(parent)
        self.item = item
        self.setup_ui()
        self.setToolTip(item.id)
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

        # 三态图标加载（不阻塞主线程）
        self._apply_icon()

        # 名称标签
        self.name_label = QLabel(self.item.name)
        self.name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.name_label.setWordWrap(True)
        self.name_label.setFont(QFont("Segoe UI", 9))
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

    # ------------------------------------------------------------------
    # 图标状态机
    # ------------------------------------------------------------------

    def _get_or_create_icon(self) -> QPixmap:
        """根据缓存状态返回图标：
        - 真图（已缓存）→ QPixmap
        - 已知缺失 → 彩色字母占位图
        - 尚未加载 → 1×1 透明占位图
        """
        cached = _get_cached_icon(self.item.id)
        if cached is _NOT_LOADED:
            return _get_transparent_pixmap()
        elif cached is None:
            return _make_placeholder_pixmap(self.item.name)
        else:
            return cached

    def _apply_icon(self):
        """将当前图标状态应用到 icon_label。"""
        pixmap = self._get_or_create_icon()
        self.icon_label.setPixmap(
            pixmap.scaled(
                64,
                64,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.FastTransformation,
            )
        )

    def update_icon(self):
        """主线程回调：图标缓存已更新，刷新显示。"""
        self._apply_icon()

    # ------------------------------------------------------------------
    # 交互
    # ------------------------------------------------------------------

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

        # 图标异步加载状态
        self._item_widgets: dict[str, ItemWidget] = {}  # item_id → widget
        self._pending_loads: set[str] = set()
        self._icon_thread: QThread | None = None
        self._icon_worker: IconLoaderWorker | None = None

        # 分批刷新版本号（防止旧批处理与新刷新冲突）
        self._refresh_version = 0

        # 搜索防抖定时器
        self._search_timer = QTimer()
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(300)
        self._search_timer.timeout.connect(self.refresh_list)

        self.setWindowTitle("选择物品")
        self.resize(800, 600)
        self.setup_ui()
        # 延迟到对话框 exec() 显示后再填充列表，避免 __init__ 阶段阻塞窗口出现
        QTimer.singleShot(0, self.refresh_list)

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
        self.search_box.textChanged.connect(self._on_search_text_changed)
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
        self._cancel_icon_loader()
        item_editor.open_item_editor()
        self.all_items = (
            item.get_all_items(self.only_basic)
        )  # 重新加载物品列表，包含新创建的自定义物品
        self.refresh_list()

    # ------------------------------------------------------------------
    # 搜索防抖
    # ------------------------------------------------------------------

    def _on_search_text_changed(self):
        """搜索文本变化时启动防抖定时器，避免高频重建列表。"""
        self._search_timer.start()

    # ------------------------------------------------------------------
    # 列表刷新（分批创建 + 图标惰性加载）
    # ------------------------------------------------------------------

    def refresh_list(self):
        """刷新物品列表：分批创建 ItemWidget（透明占位）+ 异步加载真图。"""
        # 取消上一轮仍在进行的图标加载和批处理
        self._cancel_icon_loader()
        self._refresh_version += 1  # 使旧批处理失效
        version = self._refresh_version

        self._item_widgets.clear()
        self.item_list.clear()

        # 获取当前分类 tag
        category_text = self.category_combo.currentText()
        target_category = self.CATEGORY_MAP[category_text]

        # 获取搜索文本
        search_text = self.search_box.text().lower()

        # 构建过滤后的物品列表 + 收集未缓存 ID
        filtered: list[item.Item] = []
        unloaded_ids: list[str] = []

        for it in self.all_items:
            # 1. 分类过滤
            if target_category != "all":
                if it.categories is None:
                    continue
                if target_category not in it.categories:
                    continue

            # 2. 搜索过滤
            if search_text:
                if (
                    search_text not in it.name.lower()
                    and search_text not in it.id.lower()
                ):
                    continue

            filtered.append(it)

            # 3. 判断是否需要异步加载
            if _get_cached_icon(it.id) is _NOT_LOADED:
                unloaded_ids.append(it.id)

        # 保存到实例变量供分批处理使用
        self._refresh_queue = filtered
        self._refresh_unloaded = unloaded_ids
        self._refresh_index = 0

        # 延迟启动第一批（让对话框先完成首次绘制）
        QTimer.singleShot(0, lambda: self._process_next_batch(version))

    def _process_next_batch(self, version: int):
        """处理下一批 ItemWidget 创建（每批 30 个），批次间让出事件循环。"""
        if version != self._refresh_version:
            return  # 已被新的 refresh_list 调用取代

        BATCH_SIZE = 30
        queue = self._refresh_queue
        start = self._refresh_index
        end = min(start + BATCH_SIZE, len(queue))

        self.item_list.setUpdatesEnabled(False)
        for i in range(start, end):
            it = queue[i]
            list_item = QListWidgetItem()
            list_item.setSizeHint(QSize(90, 110))
            widget = ItemWidget(it)
            widget.clicked.connect(self.on_item_clicked)
            self._item_widgets[it.id] = widget
            self.item_list.addItem(list_item)
            self.item_list.setItemWidget(list_item, widget)
        self.item_list.setUpdatesEnabled(True)

        self._refresh_index = end

        if end < len(queue):
            # 还有更多 → 下一批
            QTimer.singleShot(0, lambda: self._process_next_batch(version))
        else:
            # 全部完成 → 启动图标加载
            if self._refresh_unloaded:
                self._start_icon_loader(self._refresh_unloaded)

    # ------------------------------------------------------------------
    # 图标异步加载管理
    # ------------------------------------------------------------------

    def _start_icon_loader(self, item_ids: list[str]):
        """启动子线程批量加载图标。"""
        self._pending_loads = set(item_ids)

        self._icon_thread = QThread()
        self._icon_worker = IconLoaderWorker(item_ids)
        self._icon_worker.moveToThread(self._icon_thread)

        # 连接信号
        self._icon_worker.icon_loaded.connect(self._on_icon_loaded)
        self._icon_thread.started.connect(self._icon_worker.run)

        # 线程结束后自动清理
        self._icon_thread.finished.connect(self._icon_thread.deleteLater)
        self._icon_thread.finished.connect(
            lambda: setattr(self, '_icon_thread', None)
        )

        self._icon_thread.start()

    def _cancel_icon_loader(self):
        """取消正在运行的图标加载线程。"""
        if self._icon_thread is not None and self._icon_thread.isRunning():
            self._icon_thread.requestInterruption()
            self._icon_thread.quit()
            self._icon_thread.wait(1000)
        self._pending_loads.clear()
        self._icon_thread = None
        self._icon_worker = None

    def _on_icon_loaded(self, item_id: str, qimage_or_none):
        """主线程槽：子线程加载完一张图后回调。"""
        self._pending_loads.discard(item_id)

        # 写入缓存
        if qimage_or_none is not None:
            _icon_cache[item_id] = QPixmap.fromImage(qimage_or_none)
        else:
            _icon_cache[item_id] = None  # 标记文件不存在

        # 更新对应 widget（如果该 widget 仍存在）
        widget = self._item_widgets.get(item_id)
        if widget is not None:
            widget.update_icon()

    # ------------------------------------------------------------------
    # 生命周期
    # ------------------------------------------------------------------

    def closeEvent(self, event):
        self._cancel_icon_loader()
        self._refresh_version += 1  # 使所有待处理批次失效
        super().closeEvent(event)

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
