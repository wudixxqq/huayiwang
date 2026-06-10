"""
页面监控模块 - 实时监控对话框、视频进度、课件列表
"""
import re
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass
from core.browser_controller import BrowserController
from utils.logger import log


@dataclass
class DialogInfo:
    """对话框信息"""
    visible: bool
    title: str = ""
    button_text: str = ""
    rect: Optional[Dict[str, float]] = None
    container_rect: Optional[Dict[str, float]] = None  # 弹窗容器坐标，用于点击校验和范围限制


@dataclass
class VideoProgress:
    """视频进度信息"""
    current_time: str
    total_time: str
    current_seconds: float
    total_seconds: float
    finished: bool


@dataclass
class CourseItem:
    """课件列表项"""
    index: int
    title: str
    status: str  # 待考试 / 学习中 / 未学习
    element_selector: str = ""
    className: str = ""
    hasTopPlay: bool = False  # 是否包含 id="top_play" 的播放图标元素


class PageMonitor:
    """页面状态监控器"""

    # 默认选择器配置（可根据目标网站调整）
    DEFAULT_SELECTORS = {
        # 2号框：温馨提示对话框
        "dialog_container": "div[class*='dialog'], div[class*='modal'], div[class*='popup'], div[class*='tip']",
        "dialog_title_keyword": "温馨提示",
        "dialog_button_keyword": "好的,知道了",
        "dialog_button": "button, .btn, [class*='button'], [class*='btn']",

        # 3号框：视频播放器及时间
        "video_element": "video",
        "video_time_display": ".current-time, .duration, [class*='time'], .vjs-current-time, .vjs-duration",
        "video_progress_bar": ".progress-bar, [class*='progress'], .vjs-progress-holder",

        # 1号框：课件列表
        "course_list_container": ".course-list, [class*='list'], [class*='catalog'], [class*='chapter']",
        "course_item": ".item, [class*='item'], [class*='lesson'], li",
        "course_title": ".title, [class*='title'], h3, h4",
        "course_status": ".status, [class*='status'], [class*='state'], .tag, .label",
    }

    def __init__(self, browser: BrowserController, selectors: Optional[Dict[str, str]] = None):
        self.browser = browser
        self.selectors = selectors or self.DEFAULT_SELECTORS.copy()

    def update_selectors(self, new_selectors: Dict[str, str]):
        """更新选择器配置"""
        self.selectors.update(new_selectors)
        log.info("页面选择器已更新")

    async def detect_dialog(self) -> DialogInfo:
        """检测2号框（温馨提示对话框）是否存在 - 多策略增强版"""
        try:
            # 弹窗检测关键词配置（严格限定，仅保留指定关键词）
            title_keywords = ["温馨提示"]
            btn_keywords = ["好的，知道了"]

            script = """
            (params) => {
                const { titleKeywords, btnKeywords, minWidth, minHeight } = params;

                // 常见弹窗容器选择器（覆盖主流UI框架）
                const dialogSelectors = [
                    'div[class*="dialog"]', 'div[class*="modal"]', 'div[class*="popup"]',
                    'div[class*="tip"]', 'div[class*="notice"]', 'div[class*="alert"]',
                    'div[class*="overlay"]', 'div[class*="float"]', 'div[class*="layer"]',
                    'div[class*="message"]', 'div[class*="confirm"]', 'div[class*="toast"]',
                    '.el-dialog', '.el-message-box', '.ant-modal', '.ant-notification',
                    '.layui-layer', '.van-dialog', '.weui-dialog', '.mui-popup',
                    '[role="dialog"]', '[role="alertdialog"]'
                ];

                const containers = [];
                for (const sel of dialogSelectors) {
                    try {
                        document.querySelectorAll(sel).forEach(el => {
                            // 过滤掉已经处理过的嵌套容器
                            if (!containers.some(c => c === el || c.contains(el) || el.contains(c))) {
                                containers.push(el);
                            }
                        });
                    } catch(e) {}
                }

                const isVisible = (el) => {
                    const rect = el.getBoundingClientRect();
                    const style = window.getComputedStyle(el);
                    return rect.width > 0 && rect.height > 0 &&
                           style.display !== 'none' && style.visibility !== 'hidden' && style.opacity !== '0';
                };

                // 策略1：通过弹窗选择器 + 关键词正向匹配
                for (const container of containers) {
                    if (!isVisible(container)) continue;
                    const cRect = container.getBoundingClientRect();
                    if (cRect.width < minWidth || cRect.height < minHeight) continue;

                    const containerText = (container.innerText || '').trim();
                    const titleMatched = titleKeywords.some(kw => containerText.includes(kw));

                    // 即使标题未匹配，如果容器尺寸合理且包含匹配按钮，也视为候选弹窗
                    const btnSelectors = 'button, .btn, [class*="button"], [class*="btn"], a[href="javascript:void(0)"], a[href="#"], [onclick], [role="button"]';
                    const buttons = container.querySelectorAll(btnSelectors);

                    for (const btn of buttons) {
                        if (!isVisible(btn)) continue;
                        const btnText = (btn.innerText || btn.textContent || '').trim();
                        const matchedBtnKw = btnKeywords.find(kw => btnText.includes(kw));
                        if (matchedBtnKw) {
                            const btnRect = btn.getBoundingClientRect();
                            return {
                                visible: true,
                                title: containerText.substring(0, 100),
                                buttonText: btnText,
                                rect: {
                                    x: btnRect.x,
                                    y: btnRect.y,
                                    width: btnRect.width,
                                    height: btnRect.height
                                },
                                containerRect: {
                                    x: cRect.x,
                                    y: cRect.y,
                                    width: cRect.width,
                                    height: cRect.height
                                },
                                strategy: 'selector_match',
                                titleMatched: titleMatched,
                                matchedBtnKeyword: matchedBtnKw,
                                checkedContainers: containers.length
                            };
                        }
                    }
                }

                // 策略2：关键词反向查找（按钮 -> 向上找容器）
                // 用于处理弹窗没有标准class的情况
                const allBtns = document.querySelectorAll('button, .btn, [class*="button"], [class*="btn"], a[href="javascript:void(0)"], a[href="#"], [onclick], [role="button"]');
                for (const btn of allBtns) {
                    if (!isVisible(btn)) continue;
                    const btnText = (btn.innerText || btn.textContent || '').trim();
                    const matchedBtnKw = btnKeywords.find(kw => btnText.includes(kw));
                    if (!matchedBtnKw) continue;

                    let container = btn.parentElement;
                    let depth = 0;
                    const maxDepth = 5; // 限制向上遍历深度
                    while (container && container.tagName !== 'BODY' && depth < maxDepth) {
                        const cRect = container.getBoundingClientRect();
                        if (cRect.width >= minWidth && cRect.height >= minHeight && isVisible(container)) {
                            const containerText = (container.innerText || '').trim();
                            const titleMatched = titleKeywords.some(kw => containerText.includes(kw));
                            // 标题匹配 或 容器包含该按钮且尺寸合理
                            if (titleMatched || (cRect.width < window.innerWidth * 0.9 && cRect.height < window.innerHeight * 0.9)) {
                                const btnRect = btn.getBoundingClientRect();
                                return {
                                    visible: true,
                                    title: containerText.substring(0, 100),
                                    buttonText: btnText,
                                    rect: {
                                        x: btnRect.x,
                                        y: btnRect.y,
                                        width: btnRect.width,
                                        height: btnRect.height
                                    },
                                    containerRect: {
                                        x: cRect.x,
                                        y: cRect.y,
                                        width: cRect.width,
                                        height: cRect.height
                                    },
                                    strategy: 'keyword_reverse',
                                    titleMatched: titleMatched,
                                    matchedBtnKeyword: matchedBtnKw,
                                    checkedContainers: containers.length
                                };
                            }
                        }
                        container = container.parentElement;
                        depth++;
                    }
                }

                // 策略3：检测页面中新增的固定定位/绝对定位浮层
                // 有时弹窗只是一个简单的固定定位div
                const fixedElems = document.querySelectorAll('div[style*="position: fixed"], div[style*="position:fixed"], div[style*="position: absolute"], div[style*="position:absolute"]');
                for (const el of fixedElems) {
                    if (!isVisible(el)) continue;
                    const cRect = el.getBoundingClientRect();
                    if (cRect.width < minWidth || cRect.height < minHeight) continue;
                    if (cRect.width > window.innerWidth * 0.95 && cRect.height > window.innerHeight * 0.95) continue; // 排除全屏遮罩

                    const text = (el.innerText || '').trim();
                    const titleMatched = titleKeywords.some(kw => text.includes(kw));
                    if (titleMatched) {
                        const btns = el.querySelectorAll('button, .btn, [class*="button"], [class*="btn"]');
                        for (const btn of btns) {
                            if (!isVisible(btn)) continue;
                            const btnText = (btn.innerText || btn.textContent || '').trim();
                            const matchedBtnKw = btnKeywords.find(kw => btnText.includes(kw));
                            if (matchedBtnKw) {
                                const btnRect = btn.getBoundingClientRect();
                                return {
                                    visible: true,
                                    title: text.substring(0, 100),
                                    buttonText: btnText,
                                    rect: {
                                        x: btnRect.x,
                                        y: btnRect.y,
                                        width: btnRect.width,
                                        height: btnRect.height
                                    },
                                    containerRect: {
                                        x: cRect.x,
                                        y: cRect.y,
                                        width: cRect.width,
                                        height: cRect.height
                                    },
                                    strategy: 'fixed_float',
                                    titleMatched: true,
                                    matchedBtnKeyword: matchedBtnKw,
                                    checkedContainers: containers.length
                                };
                            }
                        }
                    }
                }

                return { visible: false, checkedContainers: containers.length };
            }
            """
            result = await self.browser.execute_js(script, {
                "titleKeywords": title_keywords,
                "btnKeywords": btn_keywords,
                "minWidth": 50,
                "minHeight": 30
            })

            if result and result.get("visible"):
                log.info(
                    f"检测到弹窗 [策略:{result.get('strategy')}] "
                    f"标题匹配:{result.get('titleMatched')} "
                    f"按钮:'{result.get('buttonText')}' "
                    f"匹配关键词:'{result.get('matchedBtnKeyword')}' "
                    f"坐标:({result['rect']['x']:.1f}, {result['rect']['y']:.1f})"
                )
                return DialogInfo(
                    visible=True,
                    title=result.get("title", ""),
                    button_text=result.get("buttonText", ""),
                    rect=result.get("rect"),
                    container_rect=result.get("containerRect")
                )
            else:
                checked = result.get("checkedContainers", 0) if result else 0
                log.debug(f"未检测到弹窗，已检查 {checked} 个候选容器")

        except Exception as e:
            log.error(f"检测对话框时出错: {e}")

        return DialogInfo(visible=False)

    async def get_video_progress(self) -> VideoProgress:
        """获取3号框视频播放进度"""
        try:
            script = """
            () => {
                const video = document.querySelector('video');
                if (video) {
                    const cur = video.currentTime || 0;
                    const dur = video.duration || 0;
                    // 格式化时间为 mm:ss 或 hh:mm:ss
                    const fmt = (s) => {
                        if (!isFinite(s)) return "00:00";
                        const h = Math.floor(s / 3600);
                        const m = Math.floor((s % 3600) / 60);
                        const sec = Math.floor(s % 60);
                        if (h > 0) return `${h.toString().padStart(2,'0')}:${m.toString().padStart(2,'0')}:${sec.toString().padStart(2,'0')}`;
                        return `${m.toString().padStart(2,'0')}:${sec.toString().padStart(2,'0')}`;
                    };
                    return {
                        current: fmt(cur),
                        total: fmt(dur),
                        currentSec: cur,
                        totalSec: dur,
                        paused: video.paused
                    };
                }
                // 备选：从DOM中解析时间文本（自定义播放器）
                const timeEls = document.querySelectorAll('.current-time, .duration, [class*="time"], .vjs-current-time-display, .vjs-duration-display');
                let current = "", total = "";
                for (let el of timeEls) {
                    const text = (el.innerText || '').trim();
                    if (/\\d+:\\d+/.test(text)) {
                        if (el.className && el.className.includes('current')) current = text;
                        else if (el.className && el.className.includes('duration')) total = text;
                        else if (!current) current = text;
                        else if (!total) total = text;
                    }
                }
                return { current, total, currentSec: 0, totalSec: 0, paused: true, fromDOM: true };
            }
            """
            result = await self.browser.execute_js(script)
            current = result.get("current", "00:00")
            total = result.get("total", "00:00")
            cur_sec = self._time_to_seconds(current)
            tot_sec = self._time_to_seconds(total)

            # 判断完成：时间一致或差距小于2秒
            finished = False
            if tot_sec > 0 and abs(cur_sec - tot_sec) < 2:
                finished = True
            if current == total and current != "00:00" and current != "":
                finished = True

            return VideoProgress(
                current_time=current,
                total_time=total,
                current_seconds=cur_sec,
                total_seconds=tot_sec,
                finished=finished
            )
        except Exception as e:
            log.debug(f"获取视频进度时出错: {e}")
            return VideoProgress("00:00", "00:00", 0, 0, False)

    @staticmethod
    def _time_to_seconds(time_str: str) -> float:
        """将时间字符串转为秒数"""
        if not time_str:
            return 0
        parts = time_str.strip().split(':')
        try:
            if len(parts) == 3:
                return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
            elif len(parts) == 2:
                return int(parts[0]) * 60 + float(parts[1])
            else:
                return float(parts[0])
        except ValueError:
            return 0

    async def get_course_list(self) -> List[CourseItem]:
        """获取1号框课件列表 - 增强版"""
        courses: List[CourseItem] = []
        try:
            script = """
            () => {
                // 常见课件列表容器选择器（按优先级排序，越具体越优先）
                const containerSelectors = [
                    // 华医网特定结构（用户确认）
                    '.lis-content', '[class*="lis-content"]',
                    // 特定平台常见
                    '.course-list', '.lesson-list', '.chapter-list', '.catalog-list',
                    '.course_catalog', '.course-menu', '.menu-list', '.study-menu',
                    '[class*="course-list"]', '[class*="lesson-list"]', '[class*="chapter-list"]',
                    '[class*="catalog-list"]', '[class*="course-catalog"]',
                    // 通用回退
                    '[class*="catalog"]', '[class*="chapter"]', '[class*="menu"]',
                    '[class*="sidebar"]', '[class*="list"]'
                ];

                // 评分函数：判断一个条目是否是有效的课件条目
                const isValidCourseItem = (text) => {
                    if (!text || text.length < 2) return false;
                    // 过滤版权提示、广告等非课件内容
                    if (text.includes('保利威') && text.includes('提供')) return false;
                    if (text.includes('由') && text.includes('提供视频')) return false;
                    if (text.includes('版权所有') || text.includes('Copyright')) return false;
                    return true;
                };

                let bestContainer = null;
                let bestScore = -1;
                let checkedContainers = 0;

                for (const sel of containerSelectors) {
                    try {
                        const containers = document.querySelectorAll(sel);
                        for (const container of containers) {
                            const items = container.querySelectorAll('li, .item, [class*="item"], [class*="lesson"], [class*="chapter"], [class*="course"], tr');
                            if (items.length === 0) continue;
                            checkedContainers++;

                            // 计算有效课件条目数
                            let validCount = 0;
                            for (const item of items) {
                                const text = (item.innerText || '').trim();
                                if (isValidCourseItem(text)) validCount++;
                            }

                            // 评分 = 有效条目数 * 100 + 选择器精确度加分
                            let score = validCount * 100;
                            if (sel.includes('lis-content')) score += 500;  // 用户明确确认的DOM结构，最高优先级
                            else if (sel.startsWith('.course-list') || sel.startsWith('.lesson-list') || sel.startsWith('.chapter-list')) score += 200;
                            else if (sel.includes('course') || sel.includes('lesson') || sel.includes('chapter')) score += 100;
                            else if (sel.includes('catalog') || sel.includes('menu')) score += 50;

                            if (score > bestScore && validCount > 0) {
                                bestScore = score;
                                bestContainer = container;
                            }
                        }
                    } catch (e) {}
                }

                if (!bestContainer) {
                    return { containerFound: false, checkedContainers, items: [] };
                }

                const items = bestContainer.querySelectorAll('li, .item, [class*="item"], [class*="lesson"], [class*="chapter"], [class*="course"], tr');
                const data = [];
                for (let idx = 0; idx < items.length; idx++) {
                    const item = items[idx];
                    const fullText = (item.innerText || '').trim();

                    // 跳过非课件条目
                    if (!isValidCourseItem(fullText)) continue;

                    // === 标题提取（分优先级，避免匹配到状态标签）===
                    const titleSelectors = [
                        '.cw-title-text', '[class*="cw-title"]', // 华医网特定结构
                        '.name', '[class*="name"]',              // 常见名称
                        '.title', '[class*="title"]',            // 通用标题
                        'h2', 'h3', 'h4', 'h5', 'h6',             // 标题标签
                        'a'                                        // 链接文本
                    ];
                    let title = '';
                    for (const sel of titleSelectors) {
                        const el = item.querySelector(sel);
                        if (el) {
                            const t = (el.innerText || el.textContent || '').trim();
                            // 排除纯状态词、过短文本、纯序号行（如 "1." / "(2)" / "①"）
                            if (t.length >= 2 && !/^(已完成|待考试|学习中|未学习|未开始|已看完|锁定的)$/i.test(t) && !/^\d+[.\)、．]/.test(t)) {
                                title = t;
                                break;
                            }
                        }
                    }
                    // 如果以上选择器都失败，使用第一行非状态非序号文本
                    if (!title) {
                        const lines = fullText.split('\\n').map(l => l.trim()).filter(l => l.length > 0);
                        for (const line of lines) {
                            if (!/^(已完成|待考试|学习中|未学习|未开始|已看完|锁定的)$/i.test(line) && !/^\d+[.\)、．]/.test(line)) {
                                title = line;
                                break;
                            }
                        }
                        if (!title) title = lines[0] || fullText;
                    }
                    // 清理开头的状态词和序号，但确保不会清空整个标题
                    const cleanedTitle = title.replace(/^(已完成|待考试|学习中|未学习|未开始|已看完|锁定的)\s*[\-:]?\s*/i, '').replace(/^\d+[.\)、．]\s*/, '').trim();
                    if (cleanedTitle && cleanedTitle.length >= 2) title = cleanedTitle;

                    // === 状态推断（分优先级，避免 span 泛查询误判）===
                    let status = "未知";
                    let statusSource = "none";

                    // 优先级1：明确的状态元素（class包含status/state）
                    const explicitStatusEls = item.querySelectorAll('.status, [class*="status"], [class*="state"]');
                    for (let s of explicitStatusEls) {
                        const st = (s.innerText || '').trim();
                        if (st.length > 0 && st.length < 20) {
                            if (/已完成|待考试|已学习|已看完/.test(st)) { status = "待考试"; statusSource = "explicit_status"; break; }
                            if (/学习中|正在学|播放|当前/.test(st)) { status = "学习中"; statusSource = "explicit_status"; break; }
                            if (/未学习|未开始|锁|待解锁/.test(st)) { status = "未学习"; statusSource = "explicit_status"; break; }
                        }
                    }

                    // 优先级2：通用标签元素（不含span，避免误伤标题）
                    if (status === "未知") {
                        const tagEls = item.querySelectorAll('.tag, .label, em, i');
                        for (let s of tagEls) {
                            const st = (s.innerText || '').trim();
                            if (st.length > 0 && st.length < 20) {
                                if (/已完成|待考试|已学习|已看完/.test(st)) { status = "待考试"; statusSource = "tag"; break; }
                                if (/学习中|正在学|播放|当前/.test(st)) { status = "学习中"; statusSource = "tag"; break; }
                                if (/未学习|未开始|锁|待解锁/.test(st)) { status = "未学习"; statusSource = "tag"; break; }
                            }
                        }
                    }

                    // 优先级3：span元素（仅限短文本，且排除可能是标题的span）
                    if (status === "未知") {
                        const spans = item.querySelectorAll('span');
                        for (let s of spans) {
                            const st = (s.innerText || '').trim();
                            // span文本超过8个字符或等于标题，则视为标题而非状态
                            if (st.length === 0 || st.length > 8 || st === title) continue;
                            if (/已完成|待考试|已学习|已看完/.test(st)) { status = "待考试"; statusSource = "short_span"; break; }
                            if (/学习中|正在学|播放|当前/.test(st)) { status = "学习中"; statusSource = "short_span"; break; }
                            if (/未学习|未开始|锁|待解锁/.test(st)) { status = "未学习"; statusSource = "short_span"; break; }
                        }
                    }

                    // 优先级4：从整个条目文本推断（比className更可靠，避免current-playing覆盖实际状态）
                    if (status === "未知") {
                        const txt = fullText;
                        if (/已完成|已学习|已看完|待考试/.test(txt)) { status = "待考试"; statusSource = "fullText"; }
                        else if (/学习中|正在播放|当前/.test(txt)) { status = "学习中"; statusSource = "fullText"; }
                        else if (/未学习|未开始|锁/.test(txt)) { status = "未学习"; statusSource = "fullText"; }
                    }

                    // 优先级5：从 className 推断（仅在文本中无明确状态时回退）
                    if (status === "未知") {
                        const cls = ' ' + (item.className || '').toString() + ' ';
                        if (/\b(done|finish|complete|finished)\b/i.test(cls)) { status = "待考试"; statusSource = "className"; }
                        else if (/\b(active|current|playing|selected|on)\b/i.test(cls)) { status = "学习中"; statusSource = "className"; }
                        else if (/\b(lock|disable|disabled|off)\b/i.test(cls)) { status = "未学习"; statusSource = "className"; }
                    }

                    data.push({
                        index: idx,
                        title: title.substring(0, 100),
                        status: status,
                        statusSource: statusSource,
                        className: item.className,
                        id: item.id,
                        rawText: fullText.substring(0, 200),
                        hasTopPlay: !!item.querySelector('#top_play')
                    });
                }

                return {
                    containerFound: true,
                    checkedContainers,
                    selectedTag: bestContainer.tagName,
                    selectedClass: (bestContainer.className || '').toString().substring(0, 100),
                    itemCount: data.length,
                    items: data
                };
            }
            """
            result = await self.browser.execute_js(script)

            # 兼容旧格式（直接返回数组）和新格式（返回对象）
            items = result if isinstance(result, list) else (result.get('items', []) if isinstance(result, dict) else [])
            meta = result if isinstance(result, dict) else {}

            if meta.get('containerFound') is False:
                log.warning(f"未找到课件列表容器，检查了 {meta.get('checkedContainers', 0)} 个候选容器")
            else:
                log.info(
                    f"课件列表解析完成: 找到 {meta.get('itemCount', len(items))} 个课件 "
                    f"(检查容器:{meta.get('checkedContainers', 'N/A')}, "
                    f"选中容器:{meta.get('selectedTag', '')}.{meta.get('selectedClass', '')})"
                )

            for item in items:
                raw_cls = item.get('className') or ''
                cls_parts = str(raw_cls).split()
                cls_hint = cls_parts[0] if cls_parts else ''
                element_selector = (
                    f"#{item['id']}" if item.get('id')
                    else (f"[class*='{cls_hint}']" if cls_hint else f"li:nth-child({item.get('index', 0) + 1})")
                )
                courses.append(CourseItem(
                    index=item.get("index", 0),
                    title=item.get("title", "未命名课件"),
                    status=item.get("status", "未知"),
                    element_selector=element_selector,
                    className=item.get("className", ""),
                    hasTopPlay=item.get("hasTopPlay", False)
                ))
        except Exception as e:
            log.error(f"获取课件列表时出错: {e}")
        return courses

    async def get_page_title(self) -> str:
        """获取当前页面标题"""
        try:
            return await self.browser.execute_js("() => document.title")
        except Exception:
            return "未知页面"
