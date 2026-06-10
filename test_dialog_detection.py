"""
弹窗识别功能测试脚本
验证 detect_dialog 在各种场景下的识别准确性和稳定性
"""
import asyncio
from playwright.async_api import async_playwright
from core.browser_controller import BrowserController
from core.page_monitor import PageMonitor, DialogInfo


TEST_HTML = """
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
body { font-family: sans-serif; padding: 20px; }
.dialog, .modal, .popup, .custom-tip { border: 1px solid #ccc; padding: 20px; margin: 10px 0; background: #fff; }
button, .btn { padding: 8px 16px; margin: 5px; cursor: pointer; }
.hidden { display: none !important; }
.small-tip { font-size: 12px; padding: 2px; width: 40px; height: 20px; }
#fixed-float {
    position: fixed;
    top: 100px; left: 100px;
    width: 300px; height: 150px;
    background: white; border: 2px solid red;
    z-index: 9999;
}
#no-class-dialog {
    width: 400px; height: 200px;
    background: #f0f0f0; border: 1px solid #333;
    padding: 20px;
}
</style>
</head>
<body>
<h1>弹窗识别测试页面</h1>

<!-- 场景1: 标准温馨提示弹窗 -->
<div class="dialog" id="scene1">
    <h3>温馨提示</h3>
    <p>请完成当前视频学习</p>
    <button>好的,知道了</button>
</div>

<!-- 场景2: 标题为"提示"，按钮为"确定" -->
<div class="modal" id="scene2">
    <h3>提示</h3>
    <p>网络出现异常，请重试</p>
    <button class="btn">确定</button>
</div>

<!-- 场景3: 无标准class，通过结构识别 -->
<div id="no-class-dialog">
    <span>温馨提示</span>
    <p>您已连续学习30分钟，请注意休息</p>
    <a href="javascript:void(0)">知道了</a>
</div>

<!-- 场景4: 固定定位浮层 -->
<div id="fixed-float">
    <strong>系统通知</strong>
    <p>新课件已解锁</p>
    <button>关闭</button>
</div>

<!-- 场景5: 不可见弹窗（应不识别） -->
<div class="popup hidden" id="scene5">
    <h3>温馨提示</h3>
    <button>好的,知道了</button>
</div>

<!-- 场景6: 尺寸过小（应不识别） -->
<div class="small-tip" id="scene6">
    <span>提示</span>
    <button>OK</button>
</div>

<!-- 场景7: 无匹配按钮（应不识别） -->
<div class="dialog" id="scene7">
    <h3>温馨提示</h3>
    <button>取消</button>
</div>

</body>
</html>
"""


async def run_tests():
    print("=" * 60)
    print("开始弹窗识别功能测试")
    print("=" * 60)

    playwright = await async_playwright().start()
    browser = await playwright.chromium.launch(headless=True)
    page = await browser.new_page()
    await page.set_content(TEST_HTML)

    # 构造 BrowserController 的 mock，只提供 page
    controller = BrowserController()
    controller.page = page
    controller._connected = True

    monitor = PageMonitor(controller)

    # ---- 测试场景1：标准温馨提示弹窗 ----
    await page.evaluate('document.getElementById("scene1").style.display = "block";')
    await page.evaluate('document.getElementById("scene2").style.display = "none";')
    await page.evaluate('document.getElementById("no-class-dialog").style.display = "none";')
    await page.evaluate('document.getElementById("fixed-float").style.display = "none";')
    await page.evaluate('document.getElementById("scene7").style.display = "none";')

    dialog = await monitor.detect_dialog()
    assert dialog.visible, "场景1失败：未识别标准温馨提示弹窗"
    assert "好的,知道了" in dialog.button_text, f"场景1失败：按钮文本不匹配: {dialog.button_text}"
    print(f"[通过] 场景1 - 标准温馨提示弹窗: 按钮='{dialog.button_text}' 坐标=({dialog.rect['x']:.1f}, {dialog.rect['y']:.1f})")

    # ---- 测试场景2：标题"提示" + 按钮"确定" ----
    await page.evaluate('document.getElementById("scene1").style.display = "none";')
    await page.evaluate('document.getElementById("scene2").style.display = "block";')

    dialog = await monitor.detect_dialog()
    assert dialog.visible, "场景2失败：未识别'提示'弹窗"
    assert "确定" in dialog.button_text, f"场景2失败：按钮文本不匹配: {dialog.button_text}"
    print(f"[通过] 场景2 - '提示'+'确定'弹窗: 按钮='{dialog.button_text}'")

    # ---- 测试场景3：无标准class弹窗（反向查找） ----
    await page.evaluate('document.getElementById("scene2").style.display = "none";')
    await page.evaluate('document.getElementById("no-class-dialog").style.display = "block";')

    dialog = await monitor.detect_dialog()
    assert dialog.visible, "场景3失败：未识别无标准class弹窗"
    assert "知道了" in dialog.button_text, f"场景3失败：按钮文本不匹配: {dialog.button_text}"
    print(f"[通过] 场景3 - 无标准class弹窗: 按钮='{dialog.button_text}'")

    # ---- 测试场景4：固定定位浮层 ----
    await page.evaluate('document.getElementById("no-class-dialog").style.display = "none";')
    await page.evaluate('document.getElementById("fixed-float").style.display = "block";')

    dialog = await monitor.detect_dialog()
    assert dialog.visible, "场景4失败：未识别固定定位浮层"
    assert "关闭" in dialog.button_text, f"场景4失败：按钮文本不匹配: {dialog.button_text}"
    print(f"[通过] 场景4 - 固定定位浮层: 按钮='{dialog.button_text}'")

    # ---- 测试场景5：不可见弹窗（应不识别） ----
    await page.evaluate('document.getElementById("fixed-float").style.display = "none";')
    await page.evaluate('document.getElementById("scene5").classList.remove("hidden");')
    # 等一下让样式生效，然后再加回去使其保持隐藏状态进行测试
    await page.evaluate('document.getElementById("scene5").classList.add("hidden");')

    dialog = await monitor.detect_dialog()
    assert not dialog.visible, "场景5失败：错误地识别了不可见弹窗"
    print(f"[通过] 场景5 - 不可见弹窗被正确忽略")

    # ---- 测试场景6：尺寸过小（应不识别） ----
    await page.evaluate('document.getElementById("scene6").style.display = "block";')
    dialog = await monitor.detect_dialog()
    # scene6 尺寸 40x20，小于 minWidth=50/minHeight=30，应不识别
    # 但如果同时有其他可见弹窗，可能会识别到其他。确保当前只有scene6可见
    assert not dialog.visible, "场景6失败：错误地识别了过小的弹窗"
    print(f"[通过] 场景6 - 过小弹窗被正确忽略")

    # ---- 测试场景7：无匹配按钮（应不识别） ----
    await page.evaluate('document.getElementById("scene6").style.display = "none";')
    await page.evaluate('document.getElementById("scene7").style.display = "block";')

    dialog = await monitor.detect_dialog()
    assert not dialog.visible, "场景7失败：错误地识别了无匹配按钮的弹窗"
    print(f"[通过] 场景7 - 无匹配按钮弹窗被正确忽略")

    # ---- 测试场景8：多弹窗并存，应识别到其中一个 ----
    await page.evaluate('document.getElementById("scene7").style.display = "none";')
    await page.evaluate('document.getElementById("scene1").style.display = "block";')
    await page.evaluate('document.getElementById("scene2").style.display = "block";')

    dialog = await monitor.detect_dialog()
    assert dialog.visible, "场景8失败：多弹窗并存时未识别到任何弹窗"
    assert dialog.button_text in ["好的,知道了", "确定"], f"场景8失败：识别到的按钮异常: {dialog.button_text}"
    print(f"[通过] 场景8 - 多弹窗并存: 识别到按钮='{dialog.button_text}'")

    await browser.close()
    await playwright.stop()

    print("=" * 60)
    print("全部 8 个测试场景通过！弹窗识别功能修复验证成功。")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(run_tests())
