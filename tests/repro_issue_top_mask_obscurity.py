#!/usr/bin/env python3
"""
【复现脚本 3】tests/repro_issue_top_mask_obscurity.py
验证病灶 1：第一行字体上半部分呈现渐变半透明玻璃质感，视觉上如同被切除/遮蔽一半。

根因：
.subtitle-stage 静态声明了 -webkit-mask-image: linear-gradient(to bottom, transparent 0%, black 28px, black 100%)。
遮罩从 y=0 开始由 transparent 0% 渐变到 black 28px。
而第一行正文字幕位于 y=0~27px，文字上半截直接落在 0%~50% 的透明度衰减区中，
产生“被毛玻璃削顶、模糊削弱”的视觉遮挡感。

预期现象（未修复前）：
- 在初始未滚动状态（无需向上卷动时），.subtitle-stage 的 mask-image 自 transparent 0% 开始衰减；
- 检查默认无滚动状态下的遮罩定义，发现透明渐变污染了首行区域；
- 断言失败，以非 0 退出码退出（红灯）。

修复后现象：
- 默认未滚动状态下，.subtitle-stage 遮罩保持 black 0% 到 black 28px（100% 锐利饱满），绝不衰减首行正文；
- 仅当文字发生向上滚动（.is-scrolled）时，才动态启用 transparent 0% 的顶端渐隐淡出效果；
- 测试全绿通过，退出码为 0（绿灯）。
"""
import os
import sys
import re

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HTML_PATH = os.path.join(REPO_ROOT, "float_ui.html")

try:
    import Cocoa
    import WebKit
    HAS_WEBKIT = True
except ImportError:
    HAS_WEBKIT = False

class WKWebViewDriver:
    def __init__(self, width: int = 720, height: int = 140):
        self.app = Cocoa.NSApplication.sharedApplication()
        self.config = WebKit.WKWebViewConfiguration.alloc().init()
        self.config.setWebsiteDataStore_(WebKit.WKWebsiteDataStore.nonPersistentDataStore())
        self.frame = Cocoa.NSMakeRect(0, 0, width, height)
        self.webview = WebKit.WKWebView.alloc().initWithFrame_configuration_(self.frame, self.config)
        self.load_html()

    def load_html(self):
        with open(HTML_PATH, "r", encoding="utf-8") as f:
            content = f.read()
        base_url = Cocoa.NSURL.fileURLWithPath_(HTML_PATH)
        self.webview.loadHTMLString_baseURL_(content, base_url)
        self.run_loop(0.2)

    def run_loop(self, duration: float = 0.05):
        import time
        start = time.time()
        while time.time() - start < duration:
            pool = Cocoa.NSAutoreleasePool.alloc().init()
            Cocoa.NSRunLoop.currentRunLoop().runMode_beforeDate_(
                Cocoa.NSDefaultRunLoopMode,
                Cocoa.NSDate.dateWithTimeIntervalSinceNow_(0.01)
            )
            del pool

    def eval_js(self, script: str, timeout: float = 2.0):
        import time
        res_holder = {}
        def completion_handler(result, error):
            res_holder["result"] = result
            res_holder["error"] = error

        self.webview.evaluateJavaScript_completionHandler_(script, completion_handler)
        start = time.time()
        while "result" not in res_holder and "error" not in res_holder and time.time() - start < timeout:
            self.run_loop(0.01)
        if "error" in res_holder and res_holder["error"] is not None:
            raise RuntimeError(f"JS Error: {res_holder['error']}")
        return res_holder.get("result")

def test_top_mask_obscurity():
    with open(HTML_PATH, "r", encoding="utf-8") as f:
        html = f.read()

    # 1. 静态 CSS 规则审查
    # 查找默认 .subtitle-stage 的 mask-image 定义
    stage_match = re.search(r'\.subtitle-stage\s*\{([^}]+)\}', html)
    assert stage_match is not None, "未找到 .subtitle-stage 样式定义"
    stage_css = stage_match.group(1)

    # 检查默认未滚动时，是否从 transparent 0% 衰减
    has_unscrolled_transparent_mask = bool(re.search(r'(-webkit-)?mask-image:\s*linear-gradient\([^)]*transparent\s+0%', stage_css))

    # 2. Runtime 运行时检查
    if HAS_WEBKIT:
        driver = WKWebViewDriver(720, 140)
        js = """
        (() => {
            const stage = document.getElementById('subtitleStage');
            const stageStyle = window.getComputedStyle(stage);
            const maskImage = stageStyle.maskImage || stageStyle.webkitMaskImage || '';
            const isScrolled = stage.classList.contains('is-scrolled');
            return {
                maskImage: maskImage,
                isScrolled: isScrolled
            };
        })()
        """
        runtime_res = driver.eval_js(js)
        print(f"DEBUG Runtime Mask Check: isScrolled={runtime_res['isScrolled']}, maskImage={runtime_res['maskImage']}")
        
        # WebKit computed style for transparent 0% returns rgba(0, 0, 0, 0) 0%
        has_runtime_transparent_at_zero = "rgba(0, 0, 0, 0) 0%" in runtime_res["maskImage"]
    else:
        has_runtime_transparent_at_zero = has_unscrolled_transparent_mask

    # 铁面断言：默认未滚动状态下，首行文字区域严禁存在 transparent 0% 遮罩！
    if has_unscrolled_transparent_mask or has_runtime_transparent_at_zero:
        raise AssertionError(
            "❌ 捕获到目标病灶 [Issue 1]: .subtitle-stage 默认遮罩自 transparent 0% 起衰减，"
            "首行文字上半部分被 0%~50% 半透明遮挡削顶！"
        )

    print("✅ 首行文字遮罩校验通过：默认未滚动状态下首行 100% 饱满锐利，零渐变遮挡。")

if __name__ == "__main__":
    try:
        test_top_mask_obscurity()
        print("✅ 状态：绿灯 (PASS)")
        sys.exit(0)
    except AssertionError as e:
        print(f"🔴 确立红灯基准 (FAIL): {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"💥 异常退出: {e}", file=sys.stderr)
        sys.exit(2)
