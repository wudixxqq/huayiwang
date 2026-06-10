"""
课件列表功能测试脚本
验证 get_course_list 在各种场景下的解析准确性
"""
import asyncio
from playwright.async_api import async_playwright
from core.browser_controller import BrowserController
from core.page_monitor import PageMonitor


TEST_HTML = """
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
body { font-family: sans-serif; padding: 20px; }
.course-list { border: 1px solid #ddd; width: 300px; }
.course-list li { padding: 10px; border-bottom: 1px solid #eee; }
.course-list .done { color: green; }
.course-list .active { color: blue; font-weight: bold; }
.course-list .locked { color: gray; }
.video-player { border: 1px solid #ccc; padding: 10px; margin-top: 20px; }
.sidebar { width: 200px; float: right; }
.sidebar li { padding: 5px; }
</style>
</head>
<body>

<!-- 模拟侧边栏导航（干扰项） -->
<ul class="sidebar nav-list">
    <li>首页</li>
    <li>课程中心</li>
    <li>个人中心</li>
    <li>帮助</li>
</ul>

<!-- 真正的课件列表 -->
<ul class="course-list">
    <li class="done">
        <span class="title">第一章 基础知识</span>
        <span class="status">已完成</span>
    </li>
    <li class="active">
        <span class="title">第二章 进阶理论</span>
        <span class="status">学习中</span>
    </li>
    <li class="locked">
        <span class="title">第三章 实践操作</span>
        <span class="status">未学习</span>
    </li>
    <li>
        <span class="title">第四章 案例分析</span>
        <span class="status">待考试</span>
    </li>
</ul>

<!-- 视频播放器区域（含干扰内容） -->
<div class="video-player">
    <video controls></video>
    <p>由保利威提供视频服务</p>
</div>

</body>
</html>
"""

TEST_HTML_NO_STATUS = """
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
.lesson-list li { padding: 10px; border: 1px solid #ddd; margin: 5px 0; }
</style>
</head>
<body>
<ul class="lesson-list">
    <li class="finished">第一节 课程导论 <em>已看完</em></li>
    <li class="current">第二节 核心概念 <em>正在播放</em></li>
    <li class="disabled">第三节 进阶内容 <em>锁定</em></li>
</ul>
</body>
</html>
"""

TEST_HTML_MIXED_TEXT = """
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
.catalog-list li { padding: 10px; }
</style>
</head>
<body>
<ul class="catalog-list">
    <li>第1章 绪论 - 已完成</li>
    <li>第2章 方法论 - 学习中</li>
    <li>第3章 应用实践 - 未开始</li>
    <li>第4章 总结与考试 - 待考试</li>
</ul>
</body>
</html>
"""


async def test_scenario(page, monitor, name, expected_count, expected_titles, expected_statuses):
    dialog = await monitor.detect_dialog()
    courses = await monitor.get_course_list()

    print(f"\n--- {name} ---")
    print(f"获取到 {len(courses)} 个课件:")
    for c in courses:
        print(f"  [{c.index+1}] {c.title} — {c.status}")

    assert len(courses) == expected_count, f"{name}: 期望 {expected_count} 个课件，实际 {len(courses)}"
    for i, (exp_title, exp_status) in enumerate(zip(expected_titles, expected_statuses)):
        assert exp_title in courses[i].title, f"{name}: 第{i+1}个标题不匹配，期望包含 '{exp_title}'，实际 '{courses[i].title}'"
        assert courses[i].status == exp_status, f"{name}: 第{i+1}个状态不匹配，期望 '{exp_status}'，实际 '{courses[i].status}'"
    print(f"[通过] {name}")


async def run_tests():
    print("=" * 60)
    print("开始课件列表功能测试")
    print("=" * 60)

    playwright = await async_playwright().start()
    browser = await playwright.chromium.launch(headless=True)
    page = await browser.new_page()

    controller = BrowserController()
    controller.page = page
    controller._connected = True
    monitor = PageMonitor(controller)

    # ---- 场景1：标准课件列表（含状态元素） ----
    await page.set_content(TEST_HTML)
    await test_scenario(
        page, monitor, "场景1-标准课件列表",
        expected_count=4,
        expected_titles=["第一章", "第二章", "第三章", "第四章"],
        expected_statuses=["待考试", "学习中", "未学习", "待考试"]
    )

    # ---- 场景2：无独立状态元素，从class和文本推断 ----
    await page.set_content(TEST_HTML_NO_STATUS)
    await test_scenario(
        page, monitor, "场景2-无状态元素",
        expected_count=3,
        expected_titles=["第一节", "第二节", "第三节"],
        expected_statuses=["待考试", "学习中", "未学习"]
    )

    # ---- 场景3：状态混在条目文本中 ----
    await page.set_content(TEST_HTML_MIXED_TEXT)
    await test_scenario(
        page, monitor, "场景3-文本混合状态",
        expected_count=4,
        expected_titles=["第1章", "第2章", "第3章", "第4章"],
        expected_statuses=["待考试", "学习中", "未学习", "待考试"]
    )

    # ---- 场景4：包含保利威版权提示的页面 ----
    await page.set_content(TEST_HTML)
    # 模拟只显示播放器区域（干扰项）
    await page.evaluate('document.querySelector(".course-list").style.display = "none";')
    courses = await monitor.get_course_list()
    # 此时应该找不到有效的课件列表容器，或者返回空
    print(f"\n--- 场景4-隐藏课件列表 ---")
    print(f"获取到 {len(courses)} 个课件")
    for c in courses:
        print(f"  [{c.index+1}] {c.title} — {c.status}")
    # 如果找到了视频区域的条目，标题不应包含"保利威"
    for c in courses:
        assert "保利威" not in c.title, f"场景4: 错误地包含了版权提示: {c.title}"
    print(f"[通过] 场景4-版权提示被正确过滤")

    await browser.close()
    await playwright.stop()

    print("\n" + "=" * 60)
    print("全部课件列表测试场景通过！修复验证成功。")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(run_tests())
