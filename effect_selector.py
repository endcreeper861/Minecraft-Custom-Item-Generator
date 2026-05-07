import json
import logging
import sys
from pathlib import Path

from PyQt6.QtCore import QEventLoop, Qt, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
	QAbstractItemView,
	QApplication,
	QCheckBox,
	QComboBox,
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

import effect
import utils

logger = logging.getLogger(__name__)


CUSTOM_EFFECTS_DIR = "custom/effects/"


class CustomTableWidget(QTableWidget):
	"""自定义表格，用于处理悬停提示和点击事件"""

	def __init__(self, parent=None, is_source=True):
		super().__init__(parent)
		self.is_source = is_source  # True表示是右侧"全部"，False表示左侧"已选"
		self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
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
			main_window = self.window()
			if isinstance(main_window, EffectWindow):
				if self.is_source:
					main_window.move_to_selected(row)
				else:
					main_window.move_to_unselected(row)
		super().mousePressEvent(event)


class EffectWindow(QMainWindow):
	closed = pyqtSignal()

	def __init__(self, parent=None):
		super().__init__(parent)
		self.setWindowTitle("状态效果选择器")
		self.resize(1100, 650)

		# 存储当前所有可用的状态效果数据（用于搜索和恢复）
		self.all_effects = effect.get_all_effects()
		logger.info("已加载 %d 个状态效果", len(self.all_effects))
		# 存储已选效果的 ID 集合，防止重复添加
		self.selected_ids = set()
		# 保存后返回的 EffectGroup（若未保存则为 None）
		self.saved_group = None

		self.init_ui()

	def init_ui(self):
		logger.debug("初始化状态效果窗口 UI")
		central_widget = QWidget()
		self.setCentralWidget(central_widget)
		main_layout = QVBoxLayout(central_widget)
		main_layout.setContentsMargins(10, 10, 10, 10)
		main_layout.setSpacing(10)

		# --- 顶部区域 ---
		top_layout = QHBoxLayout()

		self.load_preset_btn = QPushButton("加载预设")
		self.load_preset_btn.setFixedHeight(35)
		self.load_preset_btn.clicked.connect(self.load_preset)
		top_layout.addWidget(self.load_preset_btn)

		self.save_preset_btn = QPushButton("保存预设")
		self.save_preset_btn.setFixedHeight(35)
		self.save_preset_btn.clicked.connect(self.save_preset)
		top_layout.addWidget(self.save_preset_btn)

		top_layout.addStretch(1)

		self.ok_btn = QPushButton("确定")
		self.ok_btn.setFixedHeight(35)
		self.ok_btn.setStyleSheet(utils.BIG_GREEN_BUTTON_STYLE)
		self.ok_btn.clicked.connect(self.confirm_group)
		top_layout.addWidget(self.ok_btn)

		main_layout.addLayout(top_layout)

		# --- 主体分割区域 ---
		splitter = QSplitter(Qt.Orientation.Horizontal)

		# 左侧：已选状态效果
		left_group = QGroupBox("已选状态效果（点击移除）")
		left_layout = QVBoxLayout(left_group)
		self.selected_table = CustomTableWidget(self, is_source=False)
		self.selected_table.setColumnCount(6)
		self.selected_table.setHorizontalHeaderLabels(
			["名称", "ID", "倍率", "持续时间", "粒子", "图标"]
		)
		self.selected_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)  # type: ignore
		self.selected_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)  # type: ignore
		self.selected_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)  # type: ignore
		self.selected_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)  # type: ignore
		self.selected_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)  # type: ignore
		self.selected_table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)  # type: ignore
		self.selected_table.setColumnWidth(2, 40)
		self.selected_table.setColumnWidth(3, 70)
		self.selected_table.setColumnWidth(4, 50)
		self.selected_table.setColumnWidth(5, 80)
		left_layout.addWidget(self.selected_table)

		# 右侧：全部状态效果
		right_group = QGroupBox("全部状态效果（点击选择）")
		right_layout = QVBoxLayout(right_group)

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

		self.populate_all_table()
		right_layout.addWidget(self.all_table)

		splitter.addWidget(left_group)
		splitter.addWidget(right_group)
		splitter.setStretchFactor(0, 1)
		splitter.setStretchFactor(1, 1)
		splitter.setSizes([550, 550])

		main_layout.addWidget(splitter)

	def closeEvent(self, event):
		self.closed.emit()
		super().closeEvent(event)

	def populate_all_table(self, filter_text=""):
		logger.debug("填充全部状态效果表，筛选=%r", filter_text)
		self.all_table.setRowCount(0)
		for data in self.all_effects:
			if (
				filter_text
				and filter_text.lower() not in data.name.lower()
				and filter_text.lower() not in data.id.lower()
			):
				continue

			row_pos = self.all_table.rowCount()
			self.all_table.insertRow(row_pos)

			self.all_table.setItem(row_pos, 0, QTableWidgetItem(data.name))
			self.all_table.setItem(row_pos, 1, QTableWidgetItem(data.id))
			self.all_table.setItem(row_pos, 2, QTableWidgetItem(data.description))
		logger.debug("填充全部状态效果表完成，行数=%d", self.all_table.rowCount())

	def filter_table(self, text):
		logger.debug("筛选表格文本=%r", text)
		self.populate_all_table(text)

	def move_to_selected(self, row):
		logger.debug("将状态效果移到已选：行=%s", row)
		item_id_item = self.all_table.item(row, 1)
		if not item_id_item:
			logger.warning("未在第 %s 行找到项目", row)
			return
		item_id = item_id_item.text()

		if item_id in self.selected_ids:
			logger.warning("尝试添加重复效果 id=%s", item_id)
			return

		name_item = self.all_table.item(row, 0)
		desc_item = self.all_table.item(row, 2)
		if not name_item or not desc_item:
			logger.warning("第 %s 行缺少名称或描述", row)
			return

		name = name_item.text()
		desc = desc_item.text()

		original_data = next((x for x in self.all_effects if x.id == item_id), None)
		if not original_data:
			logger.warning("未找到 id=%s 的原始数据", item_id)
			return

		row_pos = self.selected_table.rowCount()
		self.selected_table.insertRow(row_pos)

		self.selected_table.setItem(row_pos, 0, QTableWidgetItem(name))
		self.selected_table.setItem(row_pos, 1, QTableWidgetItem(item_id))

		amplifier_input = QLineEdit()
		amplifier_input.setAlignment(Qt.AlignmentFlag.AlignCenter)
		amplifier_input.setPlaceholderText("默认0")
		amplifier_input.setStyleSheet(
			"QLineEdit { border: 1px solid #ccc; border-radius: 2px; }"
		)
		self.selected_table.setCellWidget(row_pos, 2, amplifier_input)

		duration_input = QLineEdit()
		duration_input.setAlignment(Qt.AlignmentFlag.AlignCenter)
		duration_input.setPlaceholderText("刻，-1无限")
		duration_input.setStyleSheet(
			"QLineEdit { border: 1px solid #ccc; border-radius: 2px; }"
		)
		self.selected_table.setCellWidget(row_pos, 3, duration_input)

		particles_check = QCheckBox()
		particles_check.setChecked(True)
		particles_check.setTristate(False)
		particles_check.setStyleSheet("QCheckBox { margin-left: 18px; }")
		self.selected_table.setCellWidget(row_pos, 4, particles_check)

		icon_combo = QComboBox()
		icon_combo.addItems(["默认", "显示", "隐藏"])
		icon_combo.setCurrentIndex(0)
		self.selected_table.setCellWidget(row_pos, 5, icon_combo)

		self.selected_ids.add(item_id)
		logger.info("已添加效果：%s（%s）", name, item_id)

		self.refresh_tables()

	def move_to_unselected(self, row):
		logger.debug("将状态效果从已选移出：行=%s", row)
		item_id_item = self.selected_table.item(row, 1)
		if not item_id_item:
			logger.warning("未在第 %s 行找到项目（取消选择）", row)
			return
		item_id = item_id_item.text()

		if item_id in self.selected_ids:
			self.selected_ids.remove(item_id)
			logger.info("已从已选集合移除效果 id=%s", item_id)

		self.selected_table.removeRow(row)
		self.refresh_tables()

	def refresh_tables(self):
		logger.debug("刷新表格调用")
		current_filter = self.search_input.text()
		logger.debug("刷新表格，使用筛选=%r", current_filter)
		self.populate_all_table(current_filter)

	def collect_group(self) -> effect.EffectGroup:
		logger.debug("收集状态效果组，已选行数=%d", self.selected_table.rowCount())
		effects = []
		for row in range(self.selected_table.rowCount()):
			item_id_item = self.selected_table.item(row, 1)
			name_item = self.selected_table.item(row, 0)
			if not item_id_item or not name_item:
				continue
			item_id = item_id_item.text()
			name = name_item.text()

			original = next((x for x in self.all_effects if x.id == item_id), None)
			desc = original.description if original else ""

			amplifier = 0
			amp_widget = self.selected_table.cellWidget(row, 2)
			if amp_widget:
				try:
					text = amp_widget.text().strip()  # type: ignore
					if text:
						amplifier = int(text)
				except Exception:
					amplifier = 0

			duration = 0
			duration_widget = self.selected_table.cellWidget(row, 3)
			if duration_widget:
				try:
					text = duration_widget.text().strip()  # type: ignore
					if text:
						duration = int(text)
				except Exception:
					duration = 0

			show_particles = True
			particles_widget = self.selected_table.cellWidget(row, 4)
			if isinstance(particles_widget, QCheckBox):
				show_particles = particles_widget.isChecked()

			show_icon = None
			icon_widget = self.selected_table.cellWidget(row, 5)
			if isinstance(icon_widget, QComboBox):
				if icon_widget.currentIndex() == 1:
					show_icon = True
				elif icon_widget.currentIndex() == 2:
					show_icon = False

			eff = effect.Effect(
				name=name,
				id=item_id,
				description=desc,
				amplifier=amplifier,
				duration=duration,
				show_particles=show_particles,
				show_icon=show_icon,
			)
			effects.append(eff)
		logger.debug("收集完成，共 %d 个状态效果", len(effects))
		return effect.EffectGroup(effects=effects)

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

		out_dir = Path(CUSTOM_EFFECTS_DIR)
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
		start_dir = str(Path(CUSTOM_EFFECTS_DIR).resolve())
		file_path, _ = QFileDialog.getOpenFileName(
			self, "选择状态效果组 JSON", start_dir, "JSON Files (*.json)"
		)
		if not file_path:
			return
		logger.info("从 %s 加载预设", file_path)
		try:
			with open(file_path, encoding="utf-8") as f:
				data = json.load(f)

			if isinstance(data, dict) and "effects" in data:
				entries = data["effects"]
			else:
				entries = data

			self.selected_table.setRowCount(0)
			self.selected_ids.clear()

			logger.debug(
				"已加载预设条目数量=%d", len(entries) if hasattr(entries, "__len__") else 0
			)

			for entry in entries:
				item_id = entry.get("id", "")
				name = entry.get("name", "")
				desc = entry.get("description", "")
				amplifier = entry.get("amplifier", 0)
				duration = entry.get("duration", 0)
				show_particles = entry.get("show_particles", True)
				show_icon = entry.get("show_icon", None)

				row_pos = self.selected_table.rowCount()
				self.selected_table.insertRow(row_pos)
				self.selected_table.setItem(row_pos, 0, QTableWidgetItem(name))
				self.selected_table.setItem(row_pos, 1, QTableWidgetItem(item_id))
				self.selected_table.setItem(row_pos, 2, QTableWidgetItem(desc))

				amplifier_input = QLineEdit()
				amplifier_input.setAlignment(Qt.AlignmentFlag.AlignCenter)
				amplifier_input.setText(str(amplifier) if amplifier is not None else "")
				self.selected_table.setCellWidget(row_pos, 3, amplifier_input)

				duration_input = QLineEdit()
				duration_input.setAlignment(Qt.AlignmentFlag.AlignCenter)
				duration_input.setText(str(duration) if duration is not None else "")
				self.selected_table.setCellWidget(row_pos, 4, duration_input)

				particles_check = QCheckBox()
				particles_check.setChecked(bool(show_particles))
				particles_check.setTristate(False)
				particles_check.setStyleSheet("QCheckBox { margin-left: 18px; }")
				self.selected_table.setCellWidget(row_pos, 5, particles_check)

				icon_combo = QComboBox()
				icon_combo.addItems(["默认", "显示", "隐藏"])
				if show_icon is True:
					icon_combo.setCurrentIndex(1)
				elif show_icon is False:
					icon_combo.setCurrentIndex(2)
				else:
					icon_combo.setCurrentIndex(0)
				self.selected_table.setCellWidget(row_pos, 6, icon_combo)

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
		logger.info(
			"确认状态效果组，共 %d 个效果",
			len(group.effects) if hasattr(group, "effects") else 0,
		)
		self.saved_group = group
		self.close()


def open_effect_selector(parent=None):
	"""
	打开状态效果选择器窗口并阻塞直到窗口关闭。

	Returns:
		保存后返回 EffectGroup 实例；若未保存直接关闭则返回 None。
	"""
	logger.debug("调用打开状态效果选择器")
	app_created = False
	app = QApplication.instance()
	if app is None:
		app = QApplication(sys.argv)
		app_created = True

	window = EffectWindow(parent=parent)
	if parent is not None:
		window.setWindowModality(Qt.WindowModality.WindowModal)
	window.show()
	window.activateWindow()

	if app_created:
		logger.debug("运行 app.exec()（已创建 QApplication）")
		app.exec()
		saved = getattr(window, "saved_group", None)
		logger.info(
			"状态效果选择器已关闭（app_created=True），saved_group=%s",
			"已保存" if saved else "无",
		)
		return saved
	else:
		loop = QEventLoop()
		window.closed.connect(loop.quit)
		window.destroyed.connect(loop.quit)
		loop.exec()
		saved = getattr(window, "saved_group", None)
		logger.info(
			"状态效果选择器已关闭（app_created=False），saved_group=%s",
			"已保存" if saved else "无",
		)
		return saved


if __name__ == "__main__":
	logger.info("作为主应用启动状态效果窗口")
	app = QApplication(sys.argv)
	app.setFont(QFont(utils.DEFAULT_FONT, 9))
	window = EffectWindow()
	window.show()
	sys.exit(app.exec())
