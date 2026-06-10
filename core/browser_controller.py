"""
浏览器控制器 - 通过Chrome DevTools Protocol连接并控制浏览器
"""
import asyncio
from typing import Optional, List, Dict, Any
from playwright.async_api import async_playwright, Browser, BrowserContext, Page
from utils.logger import log


class BrowserController:
    """基于Playwright + CDP的浏览器控制器"""

    def __init__(self, cdp_url: str = "http://localhost:9222"):
        self.cdp_url = cdp_url
        self.playwright = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self._connected = False

    async def connect(self) -> bool:
        """连接到已开启远程调试的Chrome浏览器"""
        try:
            log.info(f"正在连接到Chrome CDP: {self.cdp_url}")
            self.playwright = await async_playwright().start()
            self.browser = await self.playwright.chromium.connect_over_cdp(self.cdp_url)
            contexts = self.browser.contexts
            if contexts:
                self.context = contexts[0]
                pages = self.context.pages
                if pages:
                    self.page = pages[0]
                    log.info(f"已连接到现有页面: {self.page.url}")
                else:
                    self.page = await self.context.new_page()
                    log.info("已新建页面")
            else:
                self.context = await self.browser.new_context()
                self.page = await self.context.new_page()
                log.info("已新建上下文和页面")
            self._connected = True
            log.info("浏览器连接成功")
            return True
        except Exception as e:
            log.error(f"浏览器连接失败: {e}")
            self._connected = False
            return False

    async def disconnect(self):
        """断开浏览器连接"""
        try:
            if self.browser:
                await self.browser.close()
            if self.playwright:
                await self.playwright.stop()
            self._connected = False
            log.info("浏览器已断开连接")
        except Exception as e:
            log.error(f"断开连接时出错: {e}")

    def is_connected(self) -> bool:
        return self._connected and self.page is not None and not self.page.is_closed()

    async def get_current_url(self) -> str:
        if self.page:
            return self.page.url
        return ""

    async def execute_js(self, script: str, arg: Any = None) -> Any:
        """在页面上下文中执行JavaScript"""
        if not self.page:
            raise RuntimeError("页面未初始化")
        return await self.page.evaluate(script, arg)

    async def query_elements(self, selector: str) -> List[Dict[str, Any]]:
        """使用CSS选择器查询元素基本信息（性能优化，不返回完整句柄）"""
        script = """
        (selector) => {
            const elements = document.querySelectorAll(selector);
            return Array.from(elements).map(el => ({
                tagName: el.tagName,
                text: el.innerText || el.textContent || '',
                className: el.className,
                id: el.id,
                rect: el.getBoundingClientRect ? {
                    x: el.getBoundingClientRect().x,
                    y: el.getBoundingClientRect().y,
                    width: el.getBoundingClientRect().width,
                    height: el.getBoundingClientRect().height
                } : null
            }));
        }
        """
        return await self.execute_js(script, selector)

    async def find_element_by_text(self, tag: str, text_keyword: str) -> Optional[Dict[str, Any]]:
        """通过文本内容模糊查找元素"""
        script = """
        (params) => {
            const { tag, keyword } = params;
            const elements = document.getElementsByTagName(tag);
            for (let el of elements) {
                const text = (el.innerText || el.textContent || '').trim();
                if (text.includes(keyword)) {
                    const rect = el.getBoundingClientRect();
                    return {
                        tagName: el.tagName,
                        text: text,
                        className: el.className,
                        id: el.id,
                        rect: { x: rect.x, y: rect.y, width: rect.width, height: rect.height }
                    };
                }
            }
            return null;
        }
        """
        return await self.execute_js(script, {"tag": tag, "keyword": text_keyword})

    async def click_at(self, x: float, y: float, delay: int = 50):
        """在指定坐标模拟鼠标点击（支持按压时长）"""
        if not self.page:
            return
        await self.page.mouse.click(x, y, delay=delay)
        log.debug(f"鼠标点击: ({x}, {y}), 按压时长: {delay}ms")

    async def click_element(self, selector: str, index: int = 0):
        """点击CSS选择器匹配的元素"""
        if not self.page:
            return
        elements = self.page.locator(selector)
        count = await elements.count()
        if count > index:
            await elements.nth(index).click()
            log.debug(f"点击元素: {selector}[{index}]")
        else:
            log.warning(f"点击失败，未找到元素: {selector}[{index}]")

    async def scroll_into_view(self, selector: str, index: int = 0):
        """滚动元素到可视区域"""
        script = """
        (params) => {
            const { selector, index } = params;
            const elements = document.querySelectorAll(selector);
            if (elements.length > index) {
                elements[index].scrollIntoView({ behavior: 'smooth', block: 'center' });
                return true;
            }
            return false;
        }
        """
        return await self.execute_js(script, {"selector": selector, "index": index})
