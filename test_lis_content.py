"""
华医网真实 DOM 结构课件列表识别测试
基于实际日志中的 DOM 结构验证
"""
import asyncio
from playwright.async_api import async_playwright
from core.browser_controller import BrowserController
from core.page_monitor import PageMonitor


# 模拟华医网真实 DOM 结构（从日志提取）
TEST_HTML = """
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
body { font-family: sans-serif; margin: 0; }
.lis-content { list-style: none; padding: 0; margin: 0; }
.lis-content li { padding: 10px; border-bottom: 1px solid #eee; cursor: pointer; }
</style>
</head>
<body>

<ul class="lis-content">
    <!-- 条目1: class="lis-inside-content current-playing", 状态=待考试 -->
    <li class="lis-inside-content current-playing">
        <h2 class="another-text">
            <i id="top_play"></i>
            <span class="cw-index">1.</span><span class="cw-title-text">高度不确定新发传染病应对管理的策略和护理措施</span>
            <span class="cw-lecturer">李惠聪 / 首都医科大学附属北京佑安医院</span>
        </h2>
        <div class="cw-state">待考试</div>
    </li>

    <!-- 条目2: class="lis-inside-content", 状态=待考试 -->
    <li class="lis-inside-content">
        <h2 class="must-text">
            <span class="cw-index">2.</span><span class="cw-title-text">百日咳再现与护理对策</span>
            <span class="cw-lecturer">李惠聪 / 首都医科大学附属北京佑安医院</span>
        </h2>
        <div class="cw-state">待考试</div>
    </li>

    <!-- 条目3: class="lis-inside-content", 状态=待考试 -->
    <li class="lis-inside-content">
        <h2 class="must-text">
            <span class="cw-index">3.</span><span class="cw-title-text">腺病毒感染的护理</span>
            <span class="cw-lecturer">李惠聪 / 首都医科大学附属北京佑安医院</span>
        </h2>
        <div class="cw-state">待考试</div>
    </li>

    <!-- 条目4: class="lis-inside-content", 状态=待考试 -->
    <li class="lis-inside-content">
        <h2 class="must-text">
            <span class="cw-index">4.</span><span class="cw-title-text">蚊媒传染病监测与防治</span>
            <span class="cw-lecturer">吴赤红 / 北京大学第一医院</span>
        </h2>
        <div class="cw-state">待考试</div>
    </li>

    <!-- 条目5: class="lis-inside-content", 状态=学习中, 有1%进度 -->
    <li class="lis-inside-content">
        <h2 class="must-text">
            <span class="cw-index">5.</span><span class="cw-title-text">猴痘的防治进展</span>
            <span class="cw-lecturer">张佳莹 / 首都医科大学附属北京佑安医院</span>
        </h2>
        <div class="cw-state">学习中 1%</div>
    </li>
</ul>

</body>
</html>
"""


async def run_test():
    print("=" * 60)
    print("华医网真实 DOM 结构测试（基于日志）")
    print("=" * 60)

    playwright = await async_playwright().start()
    browser = await playwright.chromium.launch(headless=True)
    page = await browser.new_page()
    await page.set_content(TEST_HTML)

    controller = BrowserController()
    controller.page = page
    controller._connected = True
    monitor = PageMonitor(controller)

    courses = await monitor.get_course_list()

    print(f"\n获取到 {len(courses)} 个课件:")
    for c in courses:
        print(f"  [{c.index+1}] '{c.title}' — {c.status}")

    # 数量验证
    assert len(courses) == 5, f"期望 5 个课件，实际 {len(courses)}"

    # 标题验证（基于 .cw-title-text）
    expected_titles = [
        "高度不确定新发传染病应对管理的策略和护理措施",
        "百日咳再现与护理对策",
        "腺病毒感染的护理",
        "蚊媒传染病监测与防治",
        "猴痘的防治进展"
    ]
    for i, (course, expected) in enumerate(zip(courses, expected_titles)):
        assert course.title == expected, f"第{i+1}个标题错误: 期望 '{expected}', 实际 '{course.title}'"

    # 状态验证（基于 .cw-state 和 fullText）
    assert courses[0].status == "待考试", f"第1个状态错误: {courses[0].status}"
    assert courses[1].status == "待考试", f"第2个状态错误: {courses[1].status}"
    assert courses[2].status == "待考试", f"第3个状态错误: {courses[2].status}"
    assert courses[3].status == "待考试", f"第4个状态错误: {courses[3].status}"
    assert courses[4].status == "学习中", f"第5个状态错误（应为学习中，实际 {courses[4].status}）"

    print("\n[通过] 全部断言通过！")
    print("  ✓ 标题正确提取（.cw-title-text 优先）")
    print("  ✓ 状态正确识别（explicit_status 优先，不被 className 覆盖）")

    await browser.close()
    await playwright.stop()
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(run_test())
