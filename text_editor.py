"""
富文本编辑器 —— 基于 QTextEdit 的 IME 安全输入窗口。

提供 ``SafeTextEdit``（IME 安全的 QTextEdit 子类）和 ``TextEditorDialog``
（模态对话框外壳）。采用 Word 风格 Run 级格式引擎，以 QTextFragment
为最小格式判定单元，五种格式互不干扰。

参考：<https://zh.minecraft.wiki/w/%E6%96%87%E6%9C%AC%E7%BB%84%E4%BB%B6>
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from PyQt6.QtCore import QRect, Qt, pyqtSignal
from PyQt6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QFontDatabase,
    QGuiApplication,
    QInputMethodEvent,
    QTextBlock,
    QTextCharFormat,
    QTextCursor,
    QTextFragment,
)
from PyQt6.QtWidgets import (
    QColorDialog,
    QDialog,
    QGridLayout,
    QHBoxLayout,
    QMenu,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
    QWidgetAction,
)

import utils  # DEFAULT_FONT 等
from utils import get_app_dir

logger = logging.getLogger(__name__)

# ── 混淆效果标记色（半透明红，作为 Minecraft obfuscated 的视觉替身）──
OBFUSCATED_BG = QColor(255, 80, 80, 80)

# ── Minecraft 16 种预设文字颜色 ──
MINECRAFT_COLORS: dict[str, QColor] = {
    "black":        QColor(0, 0, 0),
    "dark_blue":    QColor(0, 0, 170),
    "dark_green":   QColor(0, 170, 0),
    "dark_aqua":    QColor(0, 170, 170),
    "dark_red":     QColor(170, 0, 0),
    "dark_purple":  QColor(170, 0, 170),
    "gold":         QColor(255, 170, 0),
    "gray":         QColor(170, 170, 170),
    "dark_gray":    QColor(85, 85, 85),
    "blue":         QColor(85, 85, 255),
    "green":        QColor(85, 255, 85),
    "aqua":         QColor(85, 255, 255),
    "red":          QColor(255, 85, 85),
    "light_purple": QColor(255, 85, 255),
    "yellow":       QColor(255, 255, 85),
    "white":        QColor(255, 255, 255),
}

# ── 本阶段支持的布尔格式键 ──
_FORMAT_KEYS = ("bold", "italic", "underline", "strikethrough", "obfuscated")


# ═══════════════════════════════════════════════════════════════
#  SafeTextEdit — IME 安全的 QTextEdit
# ═══════════════════════════════════════════════════════════════


class SafeTextEdit(QTextEdit):
    """IME 输入安全的富文本编辑框。

    在 QTextEdit 基础上增强中文输入法支持，消除候选框定位不准、
    提交文本重复/丢失等常见问题。同时提供 Word 风格 Run 级格式引擎，
    以 QTextFragment 为最小格式判定单元。

    .. warning::
       如需在子类中进一步重写 ``inputMethodEvent``，**必须**调用
       ``super().inputMethodEvent(event)``，否则所有 IME 逻辑失效。
    """

    # ── 信号 ──────────────────────────────────────────────
    formatChanged = pyqtSignal(QTextCharFormat)
    """当光标位置变化导致当前格式变化时发射。

    工具栏按钮可连接此信号同步 toggle 状态
    （例如光标移到加粗文本上时，加粗按钮自动高亮）。
    """

    # ── 初始化 ────────────────────────────────────────────

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        # ── 焦点策略：必须 StrongFocus，否则 IME 收不到键盘事件 ──
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        # ── 输入法提示：无限制文本输入 ──
        self.setInputMethodHints(Qt.InputMethodHint.ImhNone)

        # ── 保留富文本模式（不调用 setAcceptRichText(False)）──

        # ── 如有Unifont用Unifont，否则回退到默认字体 ──
        unifont_path = get_app_dir() / "unifont-16.0.02.otf"
        font_id = QFontDatabase.addApplicationFont(str(unifont_path))
        if font_id != -1:
            families = QFontDatabase.applicationFontFamilies(font_id)
            if families:
                font = QFont(families[0], 16)
            else:
                font = QFont(utils.DEFAULT_FONT, 16)
        else:
            font = QFont(utils.DEFAULT_FONT, 16)
        self.setFont(font)
        self.document().setDefaultFont(font)  # type: ignore[union-attr]

        # ── 光标位置变化 → 通知 IME 更新候选框位置 ──
        self.cursorPositionChanged.connect(self._on_cursor_position_changed)

        # ── 内部状态标志 ──
        self._updating = False  # 防止 textChanged 递归

    # ═══════════════════════════════════════════════════════════
    #  IME 事件处理
    # ═══════════════════════════════════════════════════════════

    def inputMethodEvent(self, event: QInputMethodEvent) -> None:
        """处理输入法事件。

        **关键规则**：必须调用 ``super().inputMethodEvent(event)``，
        让基类负责所有文本插入、预编辑渲染和替换长度处理。
        自定义逻辑仅放在 super 调用之前或之后做日志/样式调整。
        """
        if event.commitString():
            logger.debug("IME 提交: %r", event.commitString())
        if event.preeditString():
            logger.debug("IME 预编辑: %r", event.preeditString())

        # ── 核心：委托基类处理所有 IME 逻辑 ──
        super().inputMethodEvent(event)

        if event.commitString():
            self._after_commit()

    def inputMethodQuery(self, query: Qt.InputMethodQuery):
        """为输入法提供编辑器状态信息。

        重点实现 ``ImCursorRectangle`` 查询，
        返回**屏幕全局坐标**（通过 ``mapToGlobal``），
        确保 IME 候选框正确显示在光标附近。
        """
        if query == Qt.InputMethodQuery.ImCursorRectangle:
            cursor = self.textCursor()
            rect = self.cursorRect(cursor)
            global_pos = self.viewport().mapToGlobal(rect.topLeft())  # type: ignore[union-attr]
            return QRect(global_pos, rect.size())
        return super().inputMethodQuery(query)

    # ═══════════════════════════════════════════════════════════
    #  光标 / 内部回调
    # ═══════════════════════════════════════════════════════════

    def _on_cursor_position_changed(self) -> None:
        """光标移动时通知输入法更新候选框位置并发射格式变化信号。"""
        input_method = QGuiApplication.inputMethod()
        input_method.update(Qt.InputMethodQuery.ImCursorRectangle)  # type: ignore[union-attr]

        # 发射当前格式（保持信号兼容，对话框侧用 selection_format_state() 做精确判定）
        self.formatChanged.emit(self.currentCharFormat())

    def _after_commit(self) -> None:
        """IME 提交文本后的钩子（当前为空，可供子类扩展）。"""

    # ═══════════════════════════════════════════════════════════
    #  安全的文本操作（通过 QTextCursor API，保留撤销栈）
    # ═══════════════════════════════════════════════════════════

    def safe_set_text(self, text: str) -> None:
        """安全设置全部文本内容（纯文本，保留撤销栈）。"""
        cursor = self.textCursor()
        cursor.beginEditBlock()
        cursor.select(QTextCursor.SelectionType.Document)
        cursor.insertText(text)
        cursor.endEditBlock()

    def safe_set_html(self, html: str) -> None:
        """安全设置全部文本内容（HTML，保留撤销栈和富文本格式）。"""
        cursor = self.textCursor()
        cursor.beginEditBlock()
        cursor.select(QTextCursor.SelectionType.Document)
        cursor.insertHtml(html)
        cursor.endEditBlock()

    def safe_insert_text(self, text: str) -> None:
        """在光标处安全插入纯文本。"""
        cursor = self.textCursor()
        cursor.beginEditBlock()
        cursor.insertText(text)
        cursor.endEditBlock()

    def plain_text(self) -> str:
        """获取当前文档的纯文本内容。"""
        return self.toPlainText()

    # ═══════════════════════════════════════════════════════════
    #  Word 风格 Run 级格式引擎
    # ═══════════════════════════════════════════════════════════

    @staticmethod
    def _fragment_has_format(fragment: QTextFragment, key: str) -> bool:
        """判定一个 QTextFragment（= Word 的 Run）是否具有指定格式。

        五种格式键的判定规则各自独立、互不干扰。
        """
        fmt = fragment.charFormat()
        if key == "bold":
            return fmt.fontWeight() == QFont.Weight.Bold
        elif key == "italic":
            return fmt.fontItalic()
        elif key == "underline":
            return fmt.fontUnderline()
        elif key == "strikethrough":
            return fmt.fontStrikeOut()
        elif key == "obfuscated":
            bg = fmt.background()
            return bg.style() != Qt.BrushStyle.NoBrush and bg.color() == OBFUSCATED_BG
        return False

    @staticmethod
    def _fragment_color(fragment: QTextFragment) -> str | None:
        """获取 fragment 的 Minecraft 文字颜色名或十六进制串。

        Returns:
            - 颜色名（如 ``"red"``）若匹配预设色
            - ``"#RRGGBB"`` 若为自定义色
            - ``None`` 若为默认前景色
        """
        fmt = fragment.charFormat()
        fg = fmt.foreground()
        if fg.style() == Qt.BrushStyle.NoBrush:
            return None
        color = fg.color()
        for name, mc_color in MINECRAFT_COLORS.items():
            if color == mc_color:
                return name
        return color.name()  # "#RRGGBB"

    def current_color(self) -> str | None:
        """获取当前光标/选区处第一个 fragment 的颜色。"""
        fragments = list(self._iter_fragments_in_selection())
        if not fragments:
            return None
        return self._fragment_color(fragments[0])

    def _iter_fragments_in_selection(self):
        """生成选区（或无选区时光标所在处）覆盖的所有 QTextFragment。

        使用 QTextBlock.iterator() 遍历，高效 O(片段数)。
        """
        cursor = self.textCursor()
        doc = self.document()

        if cursor.hasSelection():
            start = cursor.selectionStart()
            end = cursor.selectionEnd()
        else:
            start = end = cursor.position()

        block: QTextBlock = doc.findBlock(start)  # type: ignore[union-attr]
        while block.isValid() and block.position() < end:
            it = block.begin()
            while it != block.end():
                fragment: QTextFragment = it.fragment()
                if not fragment.isValid():
                    it += 1
                    continue
                frag_start = block.position() + fragment.position()
                frag_end = frag_start + fragment.length()
                # fragment 与 [start, end] 有交集（含边界）
                if frag_start <= end and frag_end >= start:
                    yield fragment
                it += 1
            block = block.next()

    def selection_format_state(self) -> dict[str, bool | None]:
        """Word 风格：检查当前选区/光标处的格式均匀性。

        Returns:
            dict 映射格式键 → 三态值：
            - ``True``  — 所选范围全部字符都应用了该格式
            - ``False`` — 所选范围全部字符都未应用该格式
            - ``None``  — 混合状态（部分有、部分无）

        五种格式各自独立判定，互不干扰。
        """
        fragments = list(self._iter_fragments_in_selection())
        if not fragments:
            # 空文档 → 全部 False
            return {key: False for key in _FORMAT_KEYS}

        state: dict[str, bool | None] = {}
        for key in _FORMAT_KEYS:
            has_it = [self._fragment_has_format(f, key) for f in fragments]
            if all(has_it):
                state[key] = True
            elif not any(has_it):
                state[key] = False
            else:
                state[key] = None  # 混合
        return state

    # ═══════════════════════════════════════════════════════════
    #  格式化接口
    # ═══════════════════════════════════════════════════════════

    def mergeFormat(self, fmt: QTextCharFormat) -> None:
        """核心格式化入口：将字符格式应用到当前选区/后续输入。

        有选区时仅调用 ``mergeCharFormat``（属性级合并，不覆盖其他格式）；
        无选区时额外调用 ``setCurrentCharFormat`` 为后续输入预设格式。
        """
        cursor = self.textCursor()
        cursor.mergeCharFormat(fmt)
        if not cursor.hasSelection():
            # 无选区 → 设置后续输入格式
            self.setCurrentCharFormat(fmt)

    # ── toggle 系列（使用 selection_format_state 三态判定）──

    def toggleBold(self) -> None:
        """切换加粗状态。混合选区 → 统一应用。"""
        fmt = QTextCharFormat()
        state = self.selection_format_state()
        if state["bold"] is True:
            fmt.setFontWeight(QFont.Weight.Normal)
        else:
            fmt.setFontWeight(QFont.Weight.Bold)
        self.mergeFormat(fmt)

    def toggleItalic(self) -> None:
        """切换斜体状态。混合选区 → 统一应用。"""
        fmt = QTextCharFormat()
        state = self.selection_format_state()
        fmt.setFontItalic(state["italic"] is not True)
        self.mergeFormat(fmt)

    def toggleUnderline(self) -> None:
        """切换下划线状态。混合选区 → 统一应用。"""
        fmt = QTextCharFormat()
        state = self.selection_format_state()
        fmt.setFontUnderline(state["underline"] is not True)
        self.mergeFormat(fmt)

    def toggleStrikethrough(self) -> None:
        """切换删除线状态。混合选区 → 统一应用。"""
        fmt = QTextCharFormat()
        state = self.selection_format_state()
        fmt.setFontStrikeOut(state["strikethrough"] is not True)
        self.mergeFormat(fmt)

    def toggleObfuscated(self) -> None:
        """切换混淆状态（红色半透明背景标记）。混合选区 → 统一应用。"""
        fmt = QTextCharFormat()
        state = self.selection_format_state()
        if state["obfuscated"] is True:
            fmt.setBackground(QColor(0, 0, 0, 0))  # 透明背景 = 清除混淆
        else:
            fmt.setBackground(OBFUSCATED_BG)
        self.mergeFormat(fmt)

    # ── set 系列（后续阶段扩展用）─────────────────────────

    def setTextColor(self, color: QColor) -> None:
        """设置选中文本/当前输入的文字颜色。"""
        fmt = QTextCharFormat()
        fmt.setForeground(color)
        self.mergeFormat(fmt)

    def setTextBackground(self, color: QColor) -> None:
        fmt = QTextCharFormat()
        fmt.setBackground(color)
        self.mergeFormat(fmt)

    def setFontFamily(self, family: str) -> None:
        fmt = QTextCharFormat()
        fmt.setFontFamilies([family])
        self.mergeFormat(fmt)

    def setPointSize(self, size: int) -> None:
        fmt = QTextCharFormat()
        fmt.setFontPointSize(size)
        self.mergeFormat(fmt)


# ═══════════════════════════════════════════════════════════════
#  TextEditorDialog — 模态文本编辑对话框
# ═══════════════════════════════════════════════════════════════


class TextEditorDialog(QDialog):
    """文本组件编辑对话框。

    内嵌 ``SafeTextEdit`` + 格式化工具栏，提供确定/取消按钮。
    通过 ``from_dict()`` 类方法加载现有文本组件，
    通过 ``to_dict()`` 方法导出为 Minecraft 列表格式。

    支持两种模式：
    - ``multiline=False``（默认）：单组件 ↔ ``str | dict``
    - ``multiline=True``：多行组件列表 ↔ ``list[dict]``，每行一个组件

    布局结构（自上而下）：
        _toolbar_area  — 格式化工具栏（B I U S O）
        SafeTextEdit   — 核心编辑区域
        按钮行         — 确定 / 取消
    """

    def __init__(self, parent: QWidget | None = None, multiline: bool = False) -> None:
        super().__init__(parent)
        self.multiline = multiline
        self.setWindowTitle("编辑多行文本" if multiline else "编辑文本组件")
        self.resize(500, 350)
        self._setup_ui()

    def _setup_ui(self) -> None:
        """构建对话框布局。"""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(8)

        # ── IME 安全编辑框（先创建，工具栏按钮需引用它）──
        self.editor = SafeTextEdit(self)

        # ── 格式化工具栏 ──
        self._toolbar_area = QWidget()
        self._setup_toolbar()
        main_layout.addWidget(self._toolbar_area)

        # ── 编辑框 ──
        main_layout.addWidget(self.editor, stretch=1)

        # ── 按钮行 ──
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)

        ok_btn = QPushButton("确定")
        ok_btn.setDefault(True)
        ok_btn.clicked.connect(self.accept)
        button_layout.addWidget(ok_btn)

        main_layout.addLayout(button_layout)

        # ── 格式变化 → 按钮状态同步 ──
        self.editor.cursorPositionChanged.connect(self._sync_format_buttons)

    # ═══════════════════════════════════════════════════════════
    #  格式化工具栏
    # ═══════════════════════════════════════════════════════════

    def _setup_toolbar(self) -> None:
        """构建 5 个格式化按钮（B I U S O）。"""
        layout = QHBoxLayout(self._toolbar_area)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        self._format_buttons: dict[str, QPushButton] = {}

        # B — 粗体
        btn_b = self._create_format_button("B", "粗体 (Ctrl+B)")
        btn_b.setFont(QFont(utils.DEFAULT_FONT, 10, QFont.Weight.Bold))
        btn_b.clicked.connect(self.editor.toggleBold)
        self._format_buttons["bold"] = btn_b
        layout.addWidget(btn_b)

        # I — 斜体
        btn_i = self._create_format_button("I", "斜体 (Ctrl+I)")
        btn_i.setFont(QFont(utils.DEFAULT_FONT, 10, -1, True))
        btn_i.clicked.connect(self.editor.toggleItalic)
        self._format_buttons["italic"] = btn_i
        layout.addWidget(btn_i)

        # U — 下划线
        btn_u = self._create_format_button("U", "下划线 (Ctrl+U)")
        font_u = QFont(utils.DEFAULT_FONT, 10)
        font_u.setUnderline(True)
        btn_u.setFont(font_u)
        btn_u.clicked.connect(self.editor.toggleUnderline)
        self._format_buttons["underline"] = btn_u
        layout.addWidget(btn_u)

        # S — 删除线
        btn_s = self._create_format_button("S", "删除线")
        font_s = QFont(utils.DEFAULT_FONT, 10)
        font_s.setStrikeOut(True)
        btn_s.setFont(font_s)
        btn_s.clicked.connect(self.editor.toggleStrikethrough)
        self._format_buttons["strikethrough"] = btn_s
        layout.addWidget(btn_s)

        # O — 混淆
        btn_o = self._create_format_button("O", "混淆（随机字符）")
        btn_o.setStyleSheet(
            "QPushButton { background-color: rgba(255,80,80,80); }"
            "QPushButton:checked { background-color: rgba(255,40,40,120); }"
        )
        btn_o.clicked.connect(self.editor.toggleObfuscated)
        self._format_buttons["obfuscated"] = btn_o
        layout.addWidget(btn_o)

        # ── 颜色按钮 ──
        self._color_btn = QPushButton()
        self._color_btn.setFixedSize(28, 24)
        self._color_btn.setToolTip("文字颜色")
        self._color_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._color_btn.clicked.connect(self._show_color_menu)
        self._update_color_button_indicator(None)
        layout.addWidget(self._color_btn)

        layout.addStretch()

    def _update_color_button_indicator(self, color: QColor | None) -> None:
        """更新颜色按钮的指示器样式。"""
        if color is None:
            self._color_btn.setStyleSheet(
                "QPushButton { border: 1px solid #999; border-radius: 2px; }"
            )
            self._color_btn.setText("A")
        else:
            hex_color = color.name()
            self._color_btn.setStyleSheet(
                f"QPushButton {{ background-color: {hex_color}; "
                f"border: 1px solid #666; border-radius: 2px; "
                f"color: {'#fff' if color.lightness() < 128 else '#000'}; }}"
            )
            self._color_btn.setText("A")

    def _show_color_menu(self) -> None:
        """弹出颜色选择菜单（16 种预设 + 自定义）。"""
        menu = QMenu(self)

        # ── 4×4 预设色块网格 ──
        grid_widget = QWidget()
        grid = QGridLayout(grid_widget)
        grid.setContentsMargins(4, 4, 4, 4)
        grid.setSpacing(1)

        for idx, (name, mc_color) in enumerate(MINECRAFT_COLORS.items()):
            btn = QPushButton()
            btn.setFixedSize(22, 22)
            btn.setToolTip(name)
            btn.setStyleSheet(
                f"QPushButton {{ background-color: {mc_color.name()}; "
                f"border: 1px solid #888; border-radius: 2px; }}"
                f"QPushButton:hover {{ border: 2px solid #fff; }}"
            )
            btn.clicked.connect(lambda checked, c=mc_color: self._apply_color(c))
            grid.addWidget(btn, idx // 4, idx % 4)

        grid_action = QWidgetAction(menu)
        grid_action.setDefaultWidget(grid_widget)
        menu.addAction(grid_action)

        menu.addSeparator()

        # ── 自定义颜色 ──
        custom_action = menu.addAction("自定义颜色...")
        custom_action.triggered.connect(self._pick_custom_color)  # type: ignore[union-attr]

        menu.addSeparator()

        # ── 清除颜色 ──
        clear_action = menu.addAction("清除颜色")
        clear_action.triggered.connect(self._clear_color)  # type: ignore[union-attr]

        # 定位菜单在按钮下方
        menu.exec(self._color_btn.mapToGlobal(
            self._color_btn.rect().bottomLeft()))

    def _apply_color(self, color: QColor) -> None:
        """应用指定颜色到选区/当前输入。"""
        self.editor.setTextColor(color)
        self._update_color_button_indicator(color)

    def _pick_custom_color(self) -> None:
        """打开 QColorDialog 选择自定义颜色。"""
        color = QColorDialog.getColor(parent=self, title="选择自定义文字颜色")
        if color.isValid():
            self._apply_color(color)

    def _clear_color(self) -> None:
        """清除选区/当前输入的文字颜色（恢复默认）。"""
        fmt = QTextCharFormat()
        fmt.setForeground(QBrush())  # 默认画刷 = 无前景色
        self.editor.mergeFormat(fmt)
        self._update_color_button_indicator(None)

    def _sync_color_button(self) -> None:
        """同步颜色按钮指示器到当前光标/选区颜色。"""
        color_name = self.editor.current_color()
        if color_name is None:
            self._update_color_button_indicator(None)
        elif color_name.startswith("#"):
            self._update_color_button_indicator(QColor(color_name))
        else:
            self._update_color_button_indicator(MINECRAFT_COLORS.get(color_name))

    @staticmethod
    def _create_format_button(text: str, tooltip: str) -> QPushButton:
        """创建统一的格式化按钮。"""
        btn = QPushButton(text)
        btn.setCheckable(True)
        btn.setFixedSize(28, 24)
        btn.setToolTip(tooltip)
        btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)  # 不抢夺编辑器焦点
        return btn

    def _sync_format_buttons(self) -> None:
        """根据当前光标/选区格式同步按钮 checked 状态。

        调用 ``selection_format_state()`` 获取 Word 风格三态判定。
        mixed（None）时按钮为 unchecked，点按将统一应用格式。
        """
        state = self.editor.selection_format_state()
        for key, btn in self._format_buttons.items():
            btn.setChecked(state.get(key) is True)
        self._sync_color_button()

    # ═══════════════════════════════════════════════════════════
    #  工厂类方法 & 导入导出
    # ═══════════════════════════════════════════════════════════

    @classmethod
    def from_dict(cls, parent: QWidget | None, data: str | dict | list | None,
                  multiline: bool = False) -> TextEditorDialog:
        """从现有数据创建编辑对话框。

        Args:
            parent: 父窗口
            data: 文本组件数据，可为：
                - ``str``：纯文本（单行模式）
                - ``dict``：复合标签（单行模式）
                - ``list[dict]``：组件列表（多行模式）
                - ``None``：空白编辑
            multiline: 是否使用多行模式
        """
        dlg = cls(parent, multiline=multiline)

        if data is None:
            return dlg

        if multiline and isinstance(data, list):
            dlg._load_from_dict_list(data)
            return dlg

        if isinstance(data, str):
            dlg.editor.safe_set_text(data)
            return dlg

        if isinstance(data, dict):
            dlg._load_from_dict(data)
            return dlg

        return dlg

    def _load_from_dict(self, data: dict) -> None:
        """从字典加载文本组件到编辑器。

        支持两种形式：
        - 列表格式：``{"text": "", "extra": [...]}`` → 遍历 extra 逐段还原
        - 单组件：``{"text": "...", "bold": True}`` → 单次插入
        """
        if "extra" in data and isinstance(data["extra"], list):
            # 列表格式
            cursor = self.editor.textCursor()
            cursor.beginEditBlock()
            for child in data["extra"]:
                if not isinstance(child, dict):
                    continue
                text = child.get("text", "")
                if not text:
                    continue
                fmt = self._style_to_char_format(child)
                cursor.insertText(text, fmt)
            cursor.endEditBlock()
        else:
            # 单组件格式
            text = data.get("text", "")
            if text:
                fmt = self._style_to_char_format(data)
                cursor = self.editor.textCursor()
                cursor.beginEditBlock()
                cursor.insertText(text, fmt)
                cursor.endEditBlock()

    def _load_from_dict_list(self, data: list) -> None:
        """多行模式：从组件列表加载，组件间用 ``\\n`` 连接。

        列表中每个元素可以是：
        - ``str``：纯文本行
        - ``dict``：含样式的文本组件（单组件或含 extra 的列表格式）
        """
        cursor = self.editor.textCursor()
        cursor.beginEditBlock()
        for i, item in enumerate(data):
            if i > 0:
                cursor.insertText("\n")
            if isinstance(item, str):
                cursor.insertText(item)
            elif isinstance(item, dict):
                if "extra" in item and isinstance(item["extra"], list):
                    for child in item["extra"]:
                        if not isinstance(child, dict):
                            continue
                        text = child.get("text", "")
                        if text:
                            fmt = self._style_to_char_format(child)
                            cursor.insertText(text, fmt)
                else:
                    text = item.get("text", "")
                    if text:
                        fmt = self._style_to_char_format(item)
                        cursor.insertText(text, fmt)
        cursor.endEditBlock()

    def to_dict(self) -> str | dict | list:
        """导出编辑结果。

        - 多行模式（``self.multiline=True``）→ ``list[dict]``，每行一个组件
        - 单行模式 → ``str | dict``

        返回空字符串或空列表表示内容为空。
        """
        if self.multiline:
            return self._to_dict_list()
        return self._to_dict_single()

    def _to_dict_single(self) -> str | dict:
        """导出编辑结果为文本组件字典（或空字符串）。

        基于 QTextFragment 遍历，每个 fragment 映射为一个 TextComponent。
        复用 ``_fragment_has_format()`` 保证与编辑器内判定一致。
        block 间插入 ``\\n`` 虚拟 fragment 防止换行丢失。

        Returns:
            - ``dict``：有内容时返回 ``{"text": "..."}`` 或
              ``{"text": "", "extra": [...]}``
            - ``""``：内容为空时返回空字符串
        """
        doc = self.editor.document()
        extra: list[dict] = []
        has_any_format = False
        prev_block: QTextBlock | None = None

        block: QTextBlock = doc.begin()  # type: ignore[union-attr]
        while block.isValid():
            # ── 非首个 block 前插入换行标记 ──
            if prev_block is not None:
                extra.append({"text": "\n"})

            it = block.begin()
            while it != block.end():
                fragment: QTextFragment = it.fragment()
                if not fragment.isValid():
                    it += 1
                    continue
                text = fragment.text()
                if not text:
                    it += 1
                    continue

                comp: dict[str, Any] = {"text": text}
                fragment_has_format = False
                for key in _FORMAT_KEYS:
                    if SafeTextEdit._fragment_has_format(fragment, key):
                        comp[key] = True
                        fragment_has_format = True

                # 颜色（值类型，独立于布尔格式键）
                color_name = SafeTextEdit._fragment_color(fragment)
                if color_name is not None:
                    comp["color"] = color_name
                    fragment_has_format = True

                if fragment_has_format:
                    has_any_format = True

                extra.append(comp)
                it += 1
            prev_block = block
            block = block.next()

        if not extra:
            return ""

        if not has_any_format:
            # 全部纯文本 → 合并为单组件
            full_text = "".join(c["text"] for c in extra)
            return {"text": full_text}

        # 单 fragment 有格式 → 简单形式（与 _to_dict_list 一致）
        if len(extra) == 1:
            c = extra[0]
            simple: dict[str, Any] = {"text": c["text"]}
            for k in _FORMAT_KEYS:
                if k in c:
                    simple[k] = True
            if "color" in c:
                simple["color"] = c["color"]
            return simple

        # 多 fragment 有格式 → 列表格式
        return {"text": "", "extra": extra}

    def _to_dict_list(self) -> list[dict]:
        """多行模式导出：每行一个文本组件。

        基于 QTextBlock 遍历，每个 block 对应一行。
        行的组件格式与 ``_to_dict_single()`` 一致。
        """
        doc = self.editor.document()
        result: list[dict] = []

        # 检查是否完全为空（无任何文本）
        if self.editor.toPlainText() == "":
            return []

        block: QTextBlock = doc.begin()  # type: ignore[union-attr]
        while block.isValid():
            line_fragments: list[dict] = []
            it = block.begin()
            while it != block.end():
                fragment: QTextFragment = it.fragment()
                if not fragment.isValid() or not fragment.text():
                    it += 1
                    continue
                comp: dict[str, Any] = {"text": fragment.text()}
                for key in _FORMAT_KEYS:
                    if SafeTextEdit._fragment_has_format(fragment, key):
                        comp[key] = True
                color_name = SafeTextEdit._fragment_color(fragment)
                if color_name is not None:
                    comp["color"] = color_name
                line_fragments.append(comp)
                it += 1

            # 将此 block 的内容构建为一个 TextComponent
            if not line_fragments:
                result.append({"text": ""})
            elif len(line_fragments) == 1:
                # 单 fragment → 简单形式（可能有格式键）
                c = line_fragments[0]
                has_any = any(k in c for k in _FORMAT_KEYS) or "color" in c
                if has_any:
                    result.append(dict(c))
                else:
                    result.append({"text": c["text"]})
            else:
                has_format = any(
                    any(k in c for k in _FORMAT_KEYS) or "color" in c
                    for c in line_fragments
                )
                if not has_format:
                    # 多 fragment 无格式 → 合并为纯文本
                    full_text = "".join(c["text"] for c in line_fragments)
                    result.append({"text": full_text})
                else:
                    # 多 fragment 有格式 → 列表格式
                    extra: list[dict] = []
                    for c in line_fragments:
                        stripped: dict[str, Any] = {"text": c["text"]}
                        for k in _FORMAT_KEYS:
                            if k in c:
                                stripped[k] = True
                        if "color" in c:
                            stripped["color"] = c["color"]
                        extra.append(stripped)
                    result.append({"text": "", "extra": extra})

            block = block.next()

        return result

    # ═══════════════════════════════════════════════════════════
    #  样式映射（导入/导出共用）
    # ═══════════════════════════════════════════════════════════

    @staticmethod
    def _style_to_char_format(style: dict) -> QTextCharFormat:
        """将 TextComponent 样式字段转换为 QTextCharFormat。

        处理五种布尔格式键及颜色（值类型）。
        """
        fmt = QTextCharFormat()
        if style.get("bold"):
            fmt.setFontWeight(QFont.Weight.Bold)
        if style.get("italic"):
            fmt.setFontItalic(True)
        if style.get("underline"):
            fmt.setFontUnderline(True)
        if style.get("strikethrough"):
            fmt.setFontStrikeOut(True)
        if style.get("obfuscated"):
            fmt.setBackground(OBFUSCATED_BG)
        # 颜色
        if "color" in style:
            color_str = style["color"]
            if color_str.startswith("#"):
                fmt.setForeground(QColor(color_str))
            else:
                fmt.setForeground(MINECRAFT_COLORS.get(color_str, QColor(255, 255, 255)))
        return fmt

    # ── 辅助（向后兼容）───────────────────────────────────

    @staticmethod
    def _extract_plain_text(data: str | dict) -> str:
        """从文本组件数据中提取纯文本摘要（向后兼容）。"""
        if isinstance(data, str):
            return data
        if isinstance(data, dict):
            try:
                from text import TextComponent
                tc = TextComponent.from_dict(data)
                return TextEditorDialog._plain_text_summary(tc)
            except Exception:
                logger.warning("无法解析文本组件数据", exc_info=True)
                return str(data)
        return ""

    @staticmethod
    def _plain_text_summary(tc) -> str:
        """递归收集 TextComponent 树中所有纯文本。"""
        from text import TextComponent
        parts: list[str] = []
        if tc.text:
            parts.append(tc.text)
        for child in tc.extra:
            if isinstance(child, TextComponent):
                parts.append(TextEditorDialog._plain_text_summary(child))
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


# ═══════════════════════════════════════════════════════════════
#  main — 独立运行测试
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import json
    import sys
    from PyQt6.QtWidgets import QApplication

    logging.basicConfig(level=logging.DEBUG, format="%(levelname)s: %(message)s")

    app = QApplication(sys.argv)

    # 测试 1：空白编辑器
    dlg = TextEditorDialog.from_dict(None, None)
    if dlg.exec() == QDialog.DialogCode.Accepted:
        result = dlg.to_dict()
        print("空白 →", json.dumps(result, ensure_ascii=False))

    # 测试 2：从字符串加载（纯文本往返）
    dlg2 = TextEditorDialog.from_dict(None, "Hello 你好！")
    if dlg2.exec() == QDialog.DialogCode.Accepted:
        result = dlg2.to_dict()
        print("纯文本 →", json.dumps(result, ensure_ascii=False))

    # 测试 3：从列表格式加载（含样式）
    dlg3 = TextEditorDialog.from_dict(None, {
        "text": "",
        "extra": [
            {"text": "粗体", "bold": True},
            {"text": "斜体", "italic": True},
            {"text": "下划线", "underlined": True},
            {"text": "混淆", "obfuscated": True},
        ],
    })
    if dlg3.exec() == QDialog.DialogCode.Accepted:
        result = dlg3.to_dict()
        print("列表格式 →", json.dumps(result, ensure_ascii=False, indent=2))
