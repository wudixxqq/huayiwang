"""
日志工具模块 - 支持信号发射供GUI实时显示
"""
import logging
import sys
from datetime import datetime
from PyQt5.QtCore import QObject, pyqtSignal


class LogEmitter(QObject):
    """日志信号发射器"""
    log_record = pyqtSignal(str, str)  # (level, message)


class GuiLogHandler(logging.Handler):
    """自定义日志处理器，将日志发送到GUI"""
    def __init__(self, emitter: LogEmitter):
        super().__init__()
        self.emitter = emitter

    def emit(self, record: logging.LogRecord):
        try:
            msg = self.format(record)
            self.emitter.log_record.emit(record.levelname, msg)
        except Exception:
            pass


class AppLogger:
    """应用日志管理器"""
    _instance = None
    emitter = LogEmitter()

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._init_logger()
        return cls._instance

    def _init_logger(self):
        self.logger = logging.getLogger("AutoLearningAssistant")
        self.logger.setLevel(logging.DEBUG)

        # 控制台处理器
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.DEBUG)
        console_fmt = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(message)s",
            datefmt="%H:%M:%S"
        )
        console_handler.setFormatter(console_fmt)
        self.logger.addHandler(console_handler)

        # GUI处理器
        gui_handler = GuiLogHandler(self.emitter)
        gui_handler.setLevel(logging.DEBUG)
        gui_fmt = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(message)s",
            datefmt="%H:%M:%S"
        )
        gui_handler.setFormatter(gui_fmt)
        self.logger.addHandler(gui_handler)

        # 文件处理器
        file_handler = logging.FileHandler(
            f"auto_learning_{datetime.now().strftime('%Y%m%d')}.log",
            encoding="utf-8"
        )
        file_handler.setLevel(logging.DEBUG)
        file_fmt = logging.Formatter(
            "%(asctime)s [%(levelname)s] [%(filename)s:%(lineno)d] %(message)s"
        )
        file_handler.setFormatter(file_fmt)
        self.logger.addHandler(file_handler)

    def debug(self, msg: str):
        self.logger.debug(msg)

    def info(self, msg: str):
        self.logger.info(msg)

    def warning(self, msg: str):
        self.logger.warning(msg)

    def error(self, msg: str):
        self.logger.error(msg)

    def critical(self, msg: str):
        self.logger.critical(msg)


# 全局日志实例
log = AppLogger()
