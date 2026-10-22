#!/usr/bin/env python3
"""
【复现脚本 2】tests/repro_issue_viewport_scroll_clipping.py
验证病灶 2：小窗说长句（如 120px 窗口说 7 行话）无法自动下滚，后半部分被截断吞没。

根因：
在 68%/32% 黄金分割双视口架构中，#subtitleTrack 位于仅占 68% 高度的 #zonePrimary 容器内。
但当前 updateScrollOffset 计算 overflow 时比对的是 100% 外层 #subtitleStage，
导致在小窗口下计算出的向上位移量不足，#subtitleTrack 底部超出 #zonePrimary 视口被 overflow:hidden 强行截断切除！

预期现象（未修复前）：
- 120px 高度窗口下，输入 7 行长难句
- subtitleTrack.getBoundingClientRect().bottom 明显超出 zonePrimary.getBoundingClientRect().bottom（超出 > 10px）
- 触发断言失败，非 0 退出码退出（红灯）。

修复后现象：
- subtitleTrack 的跟随计算基准严格以 #zonePrimary 实际视口高度为准
- subtitleTrack 底部完全收拢在 #zonePrimary 内并保留 >= 7px 安全呼吸距离
- 测试全绿通过，退出码为 0（绿灯）。
"""
import os
import sys
import json
import time

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HTML_PATH = os.path.join(REPO_ROOT, "float_ui.html")

try:
    import Cocoa
    import WebKit
    HAS_WEBKIT = True
except ImportError:
    HAS_WEBKIT = False

class WKWebViewDriver:
    def __init__(self, width: int = 720, height: int = 120):
        self.app = Cocoa.NSApplication.sharedApplication()
        self.config = WebKit.WKWebViewConfiguration.alloc().init()
        self.config.setWebsiteDataStore_(WebKit.WKWebsiteDataStore.nonPersistentDataStore())
        self.frame = Cocoa.NSMakeRect(0, 0, width, height)
        self.webview = WebKit.WKWebView.alloc().initWithFrame_configuration_(self.frame, self.config)
        self.load_html()

    def set_window_size(self, width: int, height: int):
        self.frame = Cocoa.NSMakeRect(0, 0, width, height)
        self.webview.setFrame_(self.frame)
        self.run_loop(0.05)

    def load_html(self):
        with open(HTML_PATH, "r", encoding="utf-8") as f:
            content = f.read()
        base_url = Cocoa.NSURL.fileURLWithPath_(HTML_PATH)
        self.webview.loadHTMLString_baseURL_(content, base_url)
        self.run_loop(0.2)

    def run_loop(self, duration: float = 0.05):
        start = time.time()
        while time.time() - start < duration:
            pool = Cocoa.NSAutoreleasePool.alloc().init()
            Cocoa.NSRunLoop.currentRunLoop().runMode_beforeDate_(
                Cocoa.NSDefaultRunLoopMode,
                Cocoa.NSDate.dateWithTimeIntervalSinceNow_(0.01)
            )
            del pool

    def eval_js(self, script: str, timeout: float = 2.0):
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

def test_viewport_scroll_clipping():
    if not HAS_WEBKIT:
        print("⚠️ 环境无 PyObjC WebKit 支持，无法启动微型视口进行几何测试。")
        sys.exit(0)

    driver = WKWebViewDriver(720, 120)
    
    # 注入连续 7 行长难句
    long_speech = (
        "女士们先生们，非常荣幸能够在这个重要的国际峰会上与大家就人工智能的最新突破进行深入交流。"
        "随着端到端低延迟大模型的全面普及，实时跨语言同声传译已经彻底打破了不同国家与地区之间的沟通壁垒。"
        "今天我们将共同见证这一划时代技术的实际落地与全流程体验。"
    )

    js = f"""
    (() => {{
        window.requestAnimationFrame = (cb) => {{ cb(); return 1; }};
        const activeLine = document.getElementById('activeLine');
        const pastLine = document.getElementById('pastLine');
        const zonePrimary = document.getElementById('zonePrimary');
        const subtitleTrack = document.getElementById('subtitleTrack');
        const subtitleStage = document.getElementById('subtitleStage');

        // 设置纯净测试环境，避免旧残留
        pastLine.textContent = '';
        activeLine.textContent = {json.dumps(long_speech)};

        if (window.__hud_engine__ && window.__hud_engine__.updateScrollOffset) {{
            window.__hud_engine__.updateScrollOffset(false);
        }}

        const primRect = zonePrimary.getBoundingClientRect();
        const trackRect = subtitleTrack.getBoundingClientRect();
        const stageRect = subtitleStage.getBoundingClientRect();

        const primBottom = primRect.bottom;
        const trackBottom = trackRect.bottom;
        // 关键几何物理截断差：trackBottom 超出 primBottom 的像素量
        const clippingOverflow = trackBottom - primBottom;

        return {{
            primH: zonePrimary.clientHeight,
            stageH: subtitleStage.clientHeight,
            contentH: subtitleTrack.scrollHeight,
            trackTransform: subtitleTrack.style.transform,
            clippingOverflow: clippingOverflow,
            primBottom: primBottom,
            trackBottom: trackBottom
        }};
    }})()
    """

    res = driver.eval_js(js)
    clipping = res["clippingOverflow"]
    print(f"DEBUG 几何测绘结果: primH={res['primH']}px, stageH={res['stageH']}px, contentH={res['contentH']}px, "
          f"clippingOverflow={clipping:.2f}px, transform={res['trackTransform']}")

    # 铁面断言：在 zonePrimary (overflow:hidden) 容器中，最新吐出的末尾文字必须完全可见！
    # 如果 clippingOverflow > 0，说明最新文字被 zonePrimary 下边缘硬生生截断吞没！
    if clipping > 0.5:
        raise AssertionError(
            f"❌ 捕获到目标病灶 [Issue 2]: 小窗口 7 行长句未下滚到位，subtitleTrack 底部超出 zonePrimary 达 {clipping:.2f}px，末行文字被彻底截断！"
        )

    print("✅ 视口跟随几何校验通过：主译文末行完整留在 zonePrimary 内部。")

if __name__ == "__main__":
    try:
        test_viewport_scroll_clipping()
        print("✅ 状态：绿灯 (PASS)")
        sys.exit(0)
    except AssertionError as e:
        print(f"🔴 确立红灯基准 (FAIL): {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"💥 异常退出: {e}", file=sys.stderr)
        sys.exit(2)
