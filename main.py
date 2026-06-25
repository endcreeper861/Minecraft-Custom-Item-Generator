import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from PyQt6.QtWidgets import QApplication, QMessageBox

import item_editor
from utils import get_app_dir


def setup_logging():
    log_dir = get_app_dir() / "logs"
    os.makedirs(str(log_dir), exist_ok=True)

    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)

    if logger.handlers:
        return  # 避免重复添加 handler

    # 控制台输出
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    console_handler.setFormatter(console_formatter)

    # 文件输出（支持轮转）
    file_handler = RotatingFileHandler(
        str(log_dir / "app.log"),
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(console_formatter)

    logger.addHandler(console_handler)
    logger.addHandler(file_handler)


def ensure_custom_dirs():
    """确保 custom/ 下的预设目录存在（首次运行时自动创建）。"""
    for subdir in ("items", "effects", "enchantments"):
        (get_app_dir() / "custom" / subdir).mkdir(parents=True, exist_ok=True)


def check_resources():
    """检测关键资源目录是否存在，不存在则弹出错误对话框并退出。"""
    data_dir = get_app_dir() / "data"
    if not data_dir.is_dir():
        # 需要 QApplication 实例才能弹出对话框
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)
        QMessageBox.critical(
            None,
            "资源缺失",
            "缺少资源文件 data/，请确认程序包未被损坏或移动。\n\n"
            "请重新解压程序包，确保 data/ 文件夹与程序在同一目录。",
        )
        sys.exit(1)


if __name__ == "__main__":
    setup_logging()

    logger = logging.getLogger(__name__)
    logger.info("主程序启动")

    check_resources()
    ensure_custom_dirs()

    item_editor.open_item_editor()