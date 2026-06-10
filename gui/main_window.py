"""
PyQt5 主界面模块
"""
import sys
import asyncio
import threading
import time
from typing import Optional, List

from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QLineEdit, QProgressBar,
    QListWidget, QTextEdit, QGroupBox, QMessageBox,
    QListWidgetItem, QSplitter
)
from PyQt5.QtCore import Qt, pyqtSignal, QThread, QObject
from PyQt5.QtGui import QColor, QTextCharFormat, QFont

from utils.logger import log, AppLogger
from core.browser_controller import BrowserController
from core.page_monitor import PageMonitor, DialogInfo, VideoProgress, CourseItem
from core.auto_interactor import AutoInteractor
from core.course_manager import CourseManager


class AsyncWorker(QObject):
    """
    后台异步工作线程，运行Playwright事件循环和主控逻辑
    """
    # 发往GUI的信号
    sig_connected = pyqtSignal(bool, str)       # (success, message)
    sig_status = pyqtSignal(str, str, str, int) # (page_title, video_title, time_str, progress_percent)
    sig_courses = pyqtSignal(list)              # List[CourseItem] 的序列化形式
    sig_log = pyqtSignal(str, str)              # (level, message)  由logger直接连接
    sig_running = pyqtSignal(bool)              # 运行状态

    def __init__(self):
        super().__init__()
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self.browser: Optional[BrowserController] = None
        self.monitor: Optional[PageMonitor] = None
        self.interactor: Optional[AutoInteractor] = None
        self.course_mgr = CourseManager()
        self.cdp_url = "http://localhost:9222"
        self._stop_event = threading.Event()

        # 绑定日志信号
        AppLogger.emitter.log_record.connect(self._on_log)

    def _on_log(self, level: str, msg: str):
        self.sig_log.emit(level, msg)

    def start_loop(self):
        """在独立线程启动asyncio事件循环"""
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def _run_loop(self):
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()

    def stop_loop(self):
        """停止事件循环"""
        self._stop_event.set()
        self._running = False
        if self._loop and self._loop.is_running():
            self._loop.call_soon_threadsafe(self._loop.stop)
        if self._thread:
            self._thread.join(timeout=3)

    def schedule(self, coro):
        """将协程调度到事件循环中执行"""
        if self._loop and self._loop.is_running():
            return asyncio.run_coroutine_threadsafe(coro, self._loop)
        return None

    async def _connect_browser(self):
        self.browser = BrowserController(self.cdp_url)
        ok = await self.browser.connect()
        if ok:
            self.monitor = PageMonitor(self.browser)
            self.interactor = AutoInteractor(self.browser, self.monitor)
            self.sig_connected.emit(True, f"已连接到 {self.browser.page.url if self.browser.page else 'unknown'}")
        else:
            self.sig_connected.emit(False, "连接失败，请确认Chrome已开启远程调试端口")

    def connect_browser(self, cdp_url: str):
        self.cdp_url = cdp_url
        self.schedule(self._connect_browser())

    async def _disconnect_browser(self):
        self._running = False
        if self.browser:
            await self.browser.disconnect()
            self.browser = None
        self.monitor = None
        self.interactor = None
        self.sig_connected.emit(False, "已断开连接")

    def disconnect_browser(self):
        self.schedule(self._disconnect_browser())

    def start_auto(self):
        if self._running:
            return
        if not self.browser or not self.browser.is_connected():
            self.sig_log.emit("ERROR", "请先连接浏览器")
            return
        self._running = True
        self.sig_running.emit(True)
        self.schedule(self._main_loop())

    def stop_auto(self):
        self._running = False
        self.sig_running.emit(False)

    async def _main_loop(self):
        """主监控循环"""
        log.info("===== 自动化学习助手已启动 =====")
        last_course_switch_time = 0
        video_finished_flag = False
        empty_dialog_count = 0

        while self._running and not self._stop_event.is_set():
            try:
                if not self.browser.is_connected():
                    log.warning("浏览器连接已断开")
                    break

                # 1. 检测并关闭温馨提示对话框（2号框）
                dialog = await self.monitor.detect_dialog()
                if dialog.visible:
                    clicked = await self.interactor.dismiss_dialog(dialog)
                    if clicked:
                        empty_dialog_count = 0
                        await asyncio.sleep(0.5)
                    else:
                        empty_dialog_count += 1
                        if empty_dialog_count >= 3:
                            log.warning(f"弹窗连续 {empty_dialog_count} 次检测但未成功关闭，请检查按钮坐标或页面响应")
                else:
                    if empty_dialog_count > 0:
                        empty_dialog_count = 0

                # 2. 获取视频进度（3号框）
                progress = await self.monitor.get_video_progress()

                # 3. 获取课件列表（1号框）
                courses = await self.monitor.get_course_list()
                self.course_mgr.update_courses(courses)

                # 4. 更新GUI状态
                page_title = await self.monitor.get_page_title()
                current_course = self.course_mgr.get_current_course()
                # 视频标题优先使用当前课件标题（通过"学习中"状态或current-playing类精确定位），失败时回退页面标题
                video_title = current_course.title if current_course else page_title
                percent = int(progress.current_seconds / progress.total_seconds * 100) if progress.total_seconds > 0 else 0
                time_str = f"{progress.current_time} / {progress.total_time}"
                self.sig_status.emit(page_title, video_title, time_str, percent)
                self.sig_courses.emit([
                    (c.index, c.title, c.status, c.index == (self.course_mgr.current_index if self.course_mgr.current_index >=0 else -1))
                    for c in courses
                ])

                # 5. 视频完成后自动切换
                if progress.finished and not video_finished_flag and progress.total_seconds > 10:
                    log.info(f"视频播放完毕: {video_title}")
                    video_finished_flag = True
                    self.course_mgr.mark_current_done(video_title)
                    # 查找并切换到下一个课件
                    next_course = self.course_mgr.get_next_unfinished()
                    if next_course:
                        await asyncio.sleep(2)
                        log.info(f"准备切换至下一个课件: [{next_course.index}] {next_course.title} (状态: {next_course.status})")
                        switched = await self.interactor.switch_to_course(next_course.index)
                        if switched:
                            video_finished_flag = False
                            last_course_switch_time = time.time()
                            self.course_mgr.current_index = next_course.index
                            self.course_mgr.current_title = next_course.title
                    else:
                        log.info("全部课件学习完成！")
                        self._running = False
                        self.sig_running.emit(False)
                        break

                # 如果视频进度回退或变化，重置完成标志
                if not progress.finished:
                    video_finished_flag = False

                # 6. 确保视频在播放（某些对话框关闭后可能暂停）
                await self.interactor.ensure_video_playing()

                # 循环间隔：弹窗检测时间间隔调整为60秒
                await asyncio.sleep(60)

            except Exception as e:
                log.error(f"主循环异常: {e}")
                await asyncio.sleep(5)

        log.info("===== 自动化学习助手已停止 =====")
        self.sig_running.emit(False)


class MainWindow(QMainWindow):
    """主窗口"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("自动化学习辅助程序")
        self.setMinimumSize(1100, 750)
        self.worker = AsyncWorker()
        self.worker.sig_connected.connect(self.on_connected)
        self.worker.sig_status.connect(self.on_status_update)
        self.worker.sig_courses.connect(self.on_courses_update)
        self.worker.sig_log.connect(self.on_log_message)
        self.worker.sig_running.connect(self.on_running_changed)

        self._init_ui()
        self.worker.start_loop()

    def _init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_h = QHBoxLayout(central)
        main_h.setContentsMargins(12, 12, 12, 12)
        main_h.setSpacing(12)

        # ===== 左侧面板 =====
        left_widget = QWidget()
        left_v = QVBoxLayout(left_widget)
        left_v.setContentsMargins(0, 0, 0, 0)
        left_v.setSpacing(10)

        # 连接控制组
        conn_group = QGroupBox("浏览器连接控制")
        conn_v = QVBoxLayout(conn_group)
        self.edit_cdp = QLineEdit("http://127.0.0.1:9222")
        self.edit_cdp.setPlaceholderText("Chrome CDP地址，例如 http://localhost:9222")
        conn_v.addWidget(QLabel("CDP地址:"))
        conn_v.addWidget(self.edit_cdp)
        btn_h = QHBoxLayout()
        self.btn_connect = QPushButton("连接浏览器")
        self.btn_connect.clicked.connect(self.do_connect)
        self.btn_disconnect = QPushButton("断开连接")
        self.btn_disconnect.clicked.connect(self.do_disconnect)
        self.btn_disconnect.setEnabled(False)
        btn_h.addWidget(self.btn_connect)
        btn_h.addWidget(self.btn_disconnect)
        conn_v.addLayout(btn_h)
        self.lbl_conn_status = QLabel("状态: 未连接")
        self.lbl_conn_status.setWordWrap(True)
        self.lbl_conn_status.setMaximumWidth(420)
        conn_v.addWidget(self.lbl_conn_status)
        left_v.addWidget(conn_group)

        # 自动化控制组
        auto_group = QGroupBox("自动化控制")
        auto_v = QVBoxLayout(auto_group)
        btn_auto_h = QHBoxLayout()
        self.btn_start = QPushButton("▶ 启动自动学习")
        self.btn_start.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold; padding: 8px;")
        self.btn_start.clicked.connect(self.do_start)
        self.btn_stop = QPushButton("⏹ 停止")
        self.btn_stop.setStyleSheet("background-color: #f44336; color: white; font-weight: bold; padding: 8px;")
        self.btn_stop.clicked.connect(self.do_stop)
        self.btn_stop.setEnabled(False)
        btn_auto_h.addWidget(self.btn_start)
        btn_auto_h.addWidget(self.btn_stop)
        auto_v.addLayout(btn_auto_h)
        left_v.addWidget(auto_group)

        # 课件列表组
        list_group = QGroupBox("课件列表 (1号框)")
        list_v = QVBoxLayout(list_group)
        self.list_courses = QListWidget()
        self.list_courses.setFont(QFont("Microsoft YaHei", 10))
        list_v.addWidget(self.list_courses)
        self.lbl_stats = QLabel("统计: 总计 0 | 待考试 0 | 学习中 0 | 未学习 0")
        list_v.addWidget(self.lbl_stats)
        left_v.addWidget(list_group, stretch=1)

        main_h.addWidget(left_widget, stretch=1)

        # ===== 右侧面板 =====
        right_widget = QWidget()
        right_v = QVBoxLayout(right_widget)
        right_v.setContentsMargins(0, 0, 0, 0)
        right_v.setSpacing(10)

        # 当前视频状态组
        status_group = QGroupBox("当前播放状态 (3号框)")
        status_v = QVBoxLayout(status_group)
        self.lbl_page_title = QLabel("页面标题: --")
        self.lbl_page_title.setWordWrap(True)
        status_v.addWidget(self.lbl_page_title)
        self.lbl_video_title = QLabel("视频标题: --")
        self.lbl_video_title.setWordWrap(True)
        status_v.addWidget(self.lbl_video_title)
        self.lbl_time = QLabel("播放进度: --")
        status_v.addWidget(self.lbl_time)
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFormat("%p%")
        status_v.addWidget(self.progress_bar)
        self.lbl_run_status = QLabel("运行状态: 已停止")
        status_v.addWidget(self.lbl_run_status)
        right_v.addWidget(status_group)

        # 日志组
        log_group = QGroupBox("运行日志")
        log_v = QVBoxLayout(log_group)
        self.text_log = QTextEdit()
        self.text_log.setReadOnly(True)
        self.text_log.setFont(QFont("Consolas", 9))
        log_v.addWidget(self.text_log)
        right_v.addWidget(log_group, stretch=1)

        main_h.addWidget(right_widget, stretch=1)

        # 添加初始提示
        self.text_log.append("欢迎使用自动化学习辅助程序！")
        self.text_log.append("使用前请确保Chrome已以远程调试模式启动，例如：")
        self.text_log.append('chrome.exe --remote-debugging-port=9222')

    # ===== 槽函数 =====
    def do_connect(self):
        url = self.edit_cdp.text().strip()
        if not url:
            QMessageBox.warning(self, "提示", "请输入CDP地址")
            return
        self.worker.connect_browser(url)
        self.btn_connect.setEnabled(False)

    def do_disconnect(self):
        self.worker.disconnect_browser()
        self.btn_start.setEnabled(False)
        self.btn_stop.setEnabled(False)

    def do_start(self):
        self.worker.start_auto()

    def do_stop(self):
        self.worker.stop_auto()

    @staticmethod
    def _wrap_text(text: str, max_len: int = 30) -> str:
        """将长文本按每行最多 max_len 个字符插入换行符"""
        if len(text) <= max_len:
            return text
        lines = []
        for i in range(0, len(text), max_len):
            lines.append(text[i:i + max_len])
        return "\n".join(lines)

    def on_connected(self, success: bool, message: str):
        if success:
            wrapped = self._wrap_text(message, 50)
            self.lbl_conn_status.setText(f"状态: 已连接 ({wrapped})")
            self.lbl_conn_status.setStyleSheet("color: green;")
            self.btn_connect.setEnabled(False)
            self.btn_disconnect.setEnabled(True)
            self.btn_start.setEnabled(True)
        else:
            self.lbl_conn_status.setText(f"状态: 连接失败 - {message}")
            self.lbl_conn_status.setStyleSheet("color: red;")
            self.btn_connect.setEnabled(True)
            self.btn_disconnect.setEnabled(False)
            self.btn_start.setEnabled(False)

    def on_status_update(self, page_title: str, video_title: str, time_str: str, percent: int):
        self.lbl_page_title.setText(f"页面标题: {page_title}")
        self.lbl_video_title.setText(f"视频标题: {video_title}")
        self.lbl_time.setText(f"播放进度: {time_str}")
        self.progress_bar.setValue(max(0, min(100, percent)))

    def on_courses_update(self, courses_data: list):
        self.list_courses.clear()
        done = learning = not_started = 0
        for idx, title, status, is_current in courses_data:
            item = QListWidgetItem()
            prefix = "▶ " if is_current else "   "
            item.setText(f"{prefix}[{idx+1}] {title} — {status}")
            if status == "待考试":
                item.setForeground(QColor("#4CAF50"))
                done += 1
            elif status == "学习中":
                item.setForeground(QColor("#2196F3"))
                learning += 1
            elif status == "未学习":
                item.setForeground(QColor("#9E9E9E"))
                not_started += 1
            self.list_courses.addItem(item)
        total = len(courses_data)
        self.lbl_stats.setText(
            f"统计: 总计 {total} | 待考试 {done} | 学习中 {learning} | 未学习 {not_started}"
        )

    def on_log_message(self, level: str, msg: str):
        fmt = QTextCharFormat()
        color = "#000000"
        if level == "DEBUG":
            color = "#757575"
        elif level == "INFO":
            color = "#1565C0"
        elif level == "WARNING":
            color = "#F57C00"
        elif level in ("ERROR", "CRITICAL"):
            color = "#C62828"
        fmt.setForeground(QColor(color))
        self.text_log.setCurrentCharFormat(fmt)
        self.text_log.append(msg)
        self.text_log.setCurrentCharFormat(QTextCharFormat())
        # 自动滚动到底部
        sb = self.text_log.verticalScrollBar()
        sb.setValue(sb.maximum())

    def on_running_changed(self, running: bool):
        if running:
            self.lbl_run_status.setText("运行状态: 正在自动学习中...")
            self.lbl_run_status.setStyleSheet("color: green; font-weight: bold;")
            self.btn_start.setEnabled(False)
            self.btn_stop.setEnabled(True)
        else:
            self.lbl_run_status.setText("运行状态: 已停止")
            self.lbl_run_status.setStyleSheet("color: black;")
            self.btn_start.setEnabled(True)
            self.btn_stop.setEnabled(False)

    def closeEvent(self, event):
        self.worker.stop_auto()
        self.worker.disconnect_browser()
        self.worker.stop_loop()
        event.accept()
