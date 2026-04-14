import platform
from typing import TYPE_CHECKING

from PyQt6.QtCore import QPoint, QRect, QSize, Qt
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QLayout,
    QLayoutItem,
    QTableWidget,
    QToolTip,
)


system_name = platform.system()
if system_name == "Windows":
    chinese_font = "Microsoft YaHei"  # 微软雅黑
elif system_name == "Darwin":  # macOS
    chinese_font = "PingFang SC"  # 苹方
else:  # Linux 或其他
    chinese_font = "WenQuanYi Micro Hei"  # 文泉驿

DEFAULT_FONT = chinese_font


DEFAULT_GROUP_STYLE = """
QGroupBox {
    font-weight: bold;
    border: 1px solid #ccc;
    border-radius: 4px;
    margin-top: 10px;
    padding-top: 10px;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 5px;
}
"""


BIG_GREEN_BUTTON_STYLE = """
QPushButton {
    padding: 6px 16px;
    border-radius: 4px;
    background-color: #27ae60;
    color: white;
    border: none;
}
QPushButton:hover {
    background-color: #2ecc71;
}
QPushButton:pressed {
    background-color: #219653;
}
"""


def clear_layout(layout):
    while layout.count():
        item = layout.takeAt(0)
        if item is None:
            continue
        w = item.widget()
        if w is not None:
            w.setParent(None)
            w.deleteLater()
            continue
        child_layout = item.layout()
        if child_layout is not None:
            clear_layout(child_layout)


class FlowLayout(QLayout):
    """A flow layout that arranges child widgets horizontally and wraps them.

    Minimal implementation adapted for PyQt6 usage.
    """

    def __init__(self, parent=None, margin=0, spacing=-1):
        super().__init__(parent)
        if parent is not None:
            self.setContentsMargins(margin, margin, margin, margin)
        self._item_list: list[QLayoutItem] = []
        if spacing >= 0:
            self.setSpacing(spacing)

    def addItem(self, item: QLayoutItem) -> None:
        self._item_list.append(item)

    def count(self) -> int:
        return len(self._item_list)

    def itemAt(self, index: int):
        if 0 <= index < len(self._item_list):
            return self._item_list[index]
        return None

    def takeAt(self, index: int):
        if 0 <= index < len(self._item_list):
            return self._item_list.pop(index)
        return None

    def expandingDirections(self):
        return Qt.Orientation(0)

    def hasHeightForWidth(self) -> bool:
        return True

    def heightForWidth(self, width: int) -> int:
        return self._do_layout(QRect(0, 0, width, 0), True)

    def setGeometry(self, rect: QRect) -> None:
        super().setGeometry(rect)
        self._do_layout(rect, False)

    def sizeHint(self) -> QSize:
        return self.minimumSize()

    def minimumSize(self) -> QSize:
        size = QSize()
        for item in self._item_list:
            size = size.expandedTo(item.minimumSize())
        left, top, right, bottom = self.getContentsMargins()
        size += QSize(left + right, top + bottom)  # type: ignore
        return size

    def _do_layout(self, rect: QRect, test_only: bool) -> int:
        x = rect.x()
        y = rect.y()
        line_height = 0
        max_width = rect.width()
        space_x = self.spacing()
        space_y = self.spacing()

        for item in self._item_list:
            widget_size = item.sizeHint()
            next_x = x + widget_size.width() + space_x
            if line_height > 0 and next_x - space_x > rect.x() + max_width:
                x = rect.x()
                y += line_height + space_y
                next_x = x + widget_size.width() + space_x
                line_height = 0

            if not test_only:
                item.setGeometry(QRect(QPoint(x, y), widget_size))

            x = next_x
            line_height = max(line_height, widget_size.height())

        return y + line_height - rect.y()
