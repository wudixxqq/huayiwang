# 自动化学习辅助程序  华医网

基于 PyQt5 + Playwright 的浏览器自动化工具，用于辅助完成在线视频课程学习。通过连接已开启远程调试模式的 Chrome 浏览器，实现课件列表自动获取、视频播放监控、弹窗自动关闭及课件自动切换等功能。

---

## 功能特性

- **浏览器连接**：通过 Chrome DevTools Protocol (CDP) 连接本地 Chrome 浏览器
- **课件列表获取**：自动识别并解析课程目录，支持华医网 `.lis-content` 等特殊 DOM 结构
- **视频播放监控**：实时监控视频播放进度，检测播放完成状态
- **弹窗自动关闭**：多策略检测温馨提示弹窗，精确定位按钮并模拟真实点击
- **课件自动切换**：视频播放完毕后自动切换至下一个未学习课件
- **GUI 可视化界面**：基于 PyQt5 的实时状态面板，显示播放进度、课件列表和系统日志

---

## 环境要求

- **操作系统**：Windows 10/11
- **Python**：3.10 或更高版本
- **浏览器**：Google Chrome（需开启远程调试模式）

---

## 安装步骤

### 1. 克隆仓库

```bash
git clone <仓库地址>
cd 3333
```

### 2. 安装 Python 依赖

```bash
pip install -r requirements.txt
```

### 3. 安装 Playwright 浏览器

```bash
playwright install chromium
```

---

## 使用说明

### 启动 Chrome 远程调试

右键 Chrome 快捷方式 → **属性** → 在"目标"末尾添加：

```
--remote-debugging-port=9222
```

例如：
```
"C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222
```

启动 Chrome 后，登录到目标学习网站。

### 运行程序

```bash
python main.py
```

### 操作步骤

1. 点击 **"连接浏览器"** — 程序将连接至 `http://127.0.0.1:9222`
2. 确认状态栏显示 **"已连接"** 及当前页面网址
3. 点击 **"▶ 启动自动学习"** — 程序开始自动监控视频播放、关闭弹窗并切换课件
4. 点击 **"⏹ 停止"** 可随时中断自动学习

---

## 打包为可执行文件

如需在无 Python 环境的电脑上运行，可使用 PyInstaller 打包：

```bash
pip install pyinstaller
python -m PyInstaller -F -w --name="自动学习助手" main.py
```

打包后的 exe 位于 `dist/自动学习助手.exe`。

> **注意**：目标电脑仍需安装 Playwright 浏览器（运行 `playwright install chromium`），或将本机的 `%LOCALAPPDATA%\ms-playwright` 目录复制过去。

---

## 项目结构

```
3333/
├── main.py                      # 程序入口
├── requirements.txt             # 依赖列表
├── core/                        # 核心模块
│   ├── browser_controller.py   # 浏览器控制（Playwright 封装）
│   ├── page_monitor.py         # 页面监控（弹窗检测、视频进度、课件列表）
│   ├── auto_interactor.py      # 自动交互（点击关闭弹窗、切换课件）
│   └── course_manager.py       # 课件状态管理
├── gui/                         # 图形界面
│   └── main_window.py          # PyQt5 主窗口
├── utils/                       # 工具模块
│   └── logger.py               # 日志配置
└── dist/                        # 打包输出目录（由 PyInstaller 生成）
```

---

## 技术栈

- **GUI**：PyQt5
- **浏览器自动化**：Playwright（Chromium）
- **异步编程**：asyncio
- **打包工具**：PyInstaller

---

## 注意事项

- 本工具仅供学习交流使用，请遵守相关网站的使用条款
- 使用期间请保持 Chrome 窗口正常显示，避免最小化或切换到其他标签页导致播放暂停
- 程序依赖浏览器的远程调试端口，请确保端口 `9222` 未被其他程序占用
- 部分网站可能使用字体混淆或动态 DOM 技术，如遇识别异常可参考日志进行调试

---

## 许可证

MIT License
