"""
自动化学习辅助程序 - 入口文件

使用说明：
1. 安装依赖: pip install -r requirements.txt
2. 安装Playwright浏览器: playwright install chromium
3. 先关闭所有Chrome窗口，然后启动Chrome远程调试模式（PowerShell）:
   & "C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222
   （如果提示端口占用，确保没有其它Chrome实例在运行）
4. 在Chrome中登录并打开学习页面
5. 运行本程序: python main.py
6. 点击"连接浏览器"，然后点击"启动自动学习"

功能说明：
- 实时监控并自动关闭"温馨提示"对话框（2号框）
- 监控视频播放进度（3号框），播放完毕后自动切换下一课件
- 解析课件列表（1号框），自动识别学习状态并顺序播放
- 所有操作实时显示在GUI中，并记录到日志文件
"""
import sys
from PyQt5.QtWidgets import QApplication
from gui.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
