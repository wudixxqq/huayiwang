"""
自动交互模块 - 执行自动点击、课件切换等操作
"""
import asyncio
from typing import Optional, Dict, Any
from core.browser_controller import BrowserController
from core.page_monitor import PageMonitor, DialogInfo
from utils.logger import log


class AutoInteractor:
    """自动交互执行器"""

    def __init__(self, browser: BrowserController, monitor: PageMonitor):
        self.browser = browser
        self.monitor = monitor
        self._last_dialog_hash = ""
        self._click_cooldown = 2.0  # 按钮点击冷却时间（秒）
        self._last_click_time = 0.0

    async def dismiss_dialog(self, dialog: DialogInfo) -> bool:
        """
        自动关闭2号温馨提示对话框
        优先复用 detect_dialog 已确认的按钮坐标直接点击；若失败，再在弹窗容器内二次搜索并校验坐标偏差
        """
        if not dialog.visible or not dialog.rect:
            return False

        # 冷却检查，防止重复点击
        import time
        now = time.time()
        if now - self._last_click_time < self._click_cooldown:
            log.debug(f"点击冷却中，跳过本次点击 (剩余 {self._click_cooldown - (now - self._last_click_time):.1f}s)")
            return False

        try:
            # 1) 随机等待 1-10 秒，模拟真实用户反应，防止被系统检测
            import random
            wait_sec = random.randint(1, 10)
            log.info(f"检测到弹窗，随机等待 {wait_sec} 秒后执行点击...")
            await asyncio.sleep(wait_sec)

            # 2) 优先直接使用 detect_dialog 已确认的按钮坐标（最可靠）
            rect = dialog.rect
            x = rect["x"] + rect["width"] / 2
            y = rect["y"] + rect["height"] / 2
            log.info(f"优先使用 detect_dialog 坐标: ({x:.1f}, {y:.1f})")

            # 模拟真实用户点击（100ms按压时长 + 随机偏移）
            click_x = x + random.uniform(-2, 2)
            click_y = y + random.uniform(-2, 2)
            log.info(f"执行模拟点击: ({click_x:.1f}, {click_y:.1f}), 按压时长: 100ms")
            await self.browser.click_at(click_x, click_y, delay=100)

            # 2) 验证弹窗是否成功关闭
            await asyncio.sleep(0.8)
            verify_dialog = await self.monitor.detect_dialog()
            if not verify_dialog.visible:
                self._last_click_time = now
                log.info("弹窗已成功关闭")
                return True

            log.warning(f"直接点击未生效，启用二次定位 (按钮: '{dialog.button_text}')")

            # 3) 二次尝试：在弹窗容器内搜索按钮，并校验坐标偏差
            container_rect = dialog.container_rect
            find_script = """
                (params) => {
                    const { keyword, expectedX, expectedY, maxDistance, containerRect } = params;

                    // 优先在弹窗容器内搜索；若容器信息缺失，则回退到 document.body
                    const root = containerRect
                        ? document.elementFromPoint(
                            containerRect.x + containerRect.width / 2,
                            containerRect.y + containerRect.height / 2
                          )
                        : document.body;
                    const searchRoot = root || document.body;

                    const walker = document.createTreeWalker(searchRoot, NodeFilter.SHOW_ELEMENT);
                    let el;
                    while (el = walker.nextNode()) {
                        const text = (el.innerText || el.textContent || '').trim();
                        if (text.includes(keyword)) {
                            const r = el.getBoundingClientRect();
                            if (r.width > 0 && r.height > 0) {
                                const cx = r.x + r.width / 2;
                                const cy = r.y + r.height / 2;
                                const dist = Math.sqrt(Math.pow(cx - expectedX, 2) + Math.pow(cy - expectedY, 2));
                                if (dist <= maxDistance) {
                                    return {
                                        found: true,
                                        x: cx,
                                        y: cy,
                                        width: r.width,
                                        height: r.height,
                                        tag: el.tagName,
                                        text: text.substring(0, 50),
                                        distance: Math.round(dist)
                                    };
                                }
                            }
                        }
                    }
                    return { found: false };
                }
            """
            btn_info = await self.browser.execute_js(find_script, {
                "keyword": "好的，知道了",
                "expectedX": x,
                "expectedY": y,
                "maxDistance": 100,
                "containerRect": container_rect
            })

            if btn_info and btn_info.get("found"):
                x2 = btn_info["x"]
                y2 = btn_info["y"]
                log.info(f"二次定位到按钮: '{btn_info.get('text')}' ({btn_info.get('tag')}) 位置: ({x2:.1f}, {y2:.1f}) 偏差: {btn_info.get('distance')}px")
            else:
                # 回退：仍使用原始弹窗中心坐标
                x2 = x
                y2 = y
                log.warning(f"容器内未找到有效按钮，回退到弹窗中心: ({x2:.1f}, {y2:.1f})")

            click_x2 = x2 + random.uniform(-2, 2)
            click_y2 = y2 + random.uniform(-2, 2)
            log.info(f"执行二次模拟点击: ({click_x2:.1f}, {click_y2:.1f})")
            await self.browser.click_at(click_x2, click_y2, delay=100)

            # 再次验证
            await asyncio.sleep(0.8)
            verify_dialog = await self.monitor.detect_dialog()
            if verify_dialog.visible:
                log.warning(f"二次点击后弹窗仍然存在，可能点击未生效 (按钮: '{dialog.button_text}')")
                return False

            self._last_click_time = now
            log.info("弹窗已成功关闭（二次点击）")
            return True
        except Exception as e:
            log.error(f"点击对话框按钮失败: {e}")
            return False

    async def click_by_text(self, tag: str, keyword: str) -> bool:
        """通过文本关键词点击元素"""
        try:
            el = await self.browser.find_element_by_text(tag, keyword)
            if el and el.get("rect"):
                rect = el["rect"]
                x = rect["x"] + rect["width"] / 2
                y = rect["y"] + rect["height"] / 2
                await self.browser.click_at(x, y)
                log.info(f"通过文本点击元素: {keyword}")
                return True
        except Exception as e:
            log.error(f"文本点击失败: {e}")
        return False

    async def switch_to_course(self, course_index: int, course_selector_hint: str = "") -> bool:
        """
        切换到指定课件
        优先通过索引点击，其次通过选择器提示
        """
        try:
            # 策略1：通过JavaScript直接点击列表项（优先匹配lis-content容器）
            script = """
            (index) => {
                // 优先匹配lis-content容器（华医网页面结构）
                const containerSelectors = [
                    '.lis-content', '[class*="lis-content"]',
                    '.course-list', '.lesson-list', '.chapter-list', '.catalog-list',
                    '[class*="course-list"]', '[class*="lesson-list"]', '[class*="chapter-list"]',
                    '[class*="catalog"]', '[class*="menu"]', '[class*="list"]'
                ];
                for (let sel of containerSelectors) {
                    const container = document.querySelector(sel);
                    if (!container) continue;
                    const items = container.querySelectorAll('li, .item, [class*="item"], [class*="lesson"]');
                    if (items.length > index) {
                        const target = items[index];
                        target.scrollIntoView({ behavior: 'smooth', block: 'center' });
                        const clickable = target.querySelector('a, button, [onclick]') || target;
                        clickable.click();
                        return { success: true, title: (target.innerText || '').trim().substring(0, 50) };
                    }
                }
                return { success: false };
            }
            """
            result = await self.browser.execute_js(script, course_index)
            if result and result.get("success"):
                log.info(f"已切换至课件: {result.get('title', course_index)}")
                # 等待页面加载和视频初始化
                await asyncio.sleep(3)
                return True

            # 策略2：使用选择器提示
            if course_selector_hint:
                await self.browser.click_element(course_selector_hint)
                await asyncio.sleep(3)
                return True

            log.warning(f"切换课件失败，未找到索引为 {course_index} 的课件")
            return False
        except Exception as e:
            log.error(f"切换课件时出错: {e}")
            return False

    async def ensure_video_playing(self):
        """确保视频处于播放状态"""
        try:
            script = """
            () => {
                const video = document.querySelector('video');
                if (video) {
                    if (video.paused) {
                        video.play();
                        return { action: 'played', paused: false };
                    }
                    return { action: 'already_playing', paused: false };
                }
                return { action: 'no_video', paused: true };
            }
            """
            result = await self.browser.execute_js(script)
            action = result.get("action", "")
            if action == "played":
                log.info("视频已自动恢复播放")
            elif action == "no_video":
                log.debug("页面中未检测到video元素")
        except Exception as e:
            log.debug(f"确保视频播放时出错: {e}")

    async def try_next_unfinished_course(self, courses: list) -> bool:
        """
        尝试切换到下一个未完成的课件
        courses: CourseItem列表
        """
        for course in courses:
            if course.status in ("学习中", "未学习"):
                log.info(f"准备切换至下一个课件: [{course.index}] {course.title} (状态: {course.status})")
                return await self.switch_to_course(course.index)
        log.info("所有课件均已学习完毕")
        return False
