#!/usr/bin/env python3
"""
【复现与回归测试】tests/repro_issue_twoline_output_clip.py
缺陷 1：小窗口 (stage height <= 75px, 如 720x120 或 400x120) 下，
翻译输出 2 行时，因过大的滚动位移及顶部渐变遮罩，导致第一行被削顶 / 遮挡。

需求 R1：
- 紧凑视口下应用紧凑排版 (font-size: 15px; line-height: 1.25)。
- 自适应滚动阈值，2 行内容完整展示，不触发过早滚动或 28px 顶部渐隐遮罩。
- 首行具有零透明度削顶遮挡 (zero top-half opacity obscurement)，双行 100% 完整可见。
"""

import os
import sys
import time

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HTML_PATH = os.path.join(REPO_ROOT, "float_ui.html")

try:
    import Cocoa
    import WebKit
    HAS_WEBKIT = True
except ImportError:
    HAS_WEBKIT = False


class HeadlessWKDriver:
    def __init__(self, width: int = 720, height: int = 120):
        if not HAS_WEBKIT:
            raise RuntimeError("Cocoa/WebKit not available")
        self.app = Cocoa.NSApplication.sharedApplication()
        cfg = WebKit.WKWebViewConfiguration.alloc().init()
        cfg.setWebsiteDataStore_(WebKit.WKWebsiteDataStore.nonPersistentDataStore())
        self.frame = Cocoa.NSMakeRect(0, 0, width, height)
        self.webview = WebKit.WKWebView.alloc().initWithFrame_configuration_(self.frame, cfg)
        with open(HTML_PATH, "r", encoding="utf-8") as f:
            content = f.read()
        self.webview.loadHTMLString_baseURL_(content, Cocoa.NSURL.fileURLWithPath_(HTML_PATH))
        self.pump(0.2)

    def set_size(self, width: int, height: int):
        self.webview.setFrame_(Cocoa.NSMakeRect(0, 0, width, height))
        self.pump(0.05)

    def pump(self, duration: float = 0.05):
        start = time.time()
        while time.time() - start < duration:
            pool = Cocoa.NSAutoreleasePool.alloc().init()
            Cocoa.NSRunLoop.currentRunLoop().runMode_beforeDate_(
                Cocoa.NSDefaultRunLoopMode,
                Cocoa.NSDate.dateWithTimeIntervalSinceNow_(0.01)
            )
            del pool

    def eval_js(self, script: str, timeout: float = 2.0):
        holder = {}
        self.webview.evaluateJavaScript_completionHandler_(
            script, lambda r, e: holder.update({"r": r, "e": e})
        )
        start = time.time()
        while "r" not in holder and "e" not in holder and time.time() - start < timeout:
            self.pump(0.01)
        if "e" in holder and holder["e"] is not None:
            raise RuntimeError(f"WebKit JS Error: {holder['e']}")
        return holder.get("r")


def test_twoline_output_clip():
    if not HAS_WEBKIT:
        print("⚠️ 跳过测试: 未安装 Cocoa/WebKit 环境")
        return

    test_matrix = [
        # (宽, 高, 真实自适应双行译文 - 720px 宽)
        (720, 120, "This is a comprehensive translation output that naturally wraps across exactly two lines in a seven hundred and twenty pixel wide desktop HUD window."),
        # (宽, 高, 真实自适应双行译文 - 400px 宽)
        (400, 120, "This is a natural translation output wrapping into two lines."),
        # (宽, 高, 矮视口边界真实自适应双行译文 - 720x110 边界)
        (720, 110, "This is a comprehensive translation output that naturally wraps across exactly two lines in a seven hundred and twenty pixel wide desktop HUD window."),
        # (宽, 高, 矮视口边界真实自适应双行译文 - 400x110 边界)
        (400, 110, "This is a natural translation output wrapping into two lines.")
    ]

    driver = HeadlessWKDriver(720, 120)

    for w, h, text in test_matrix:
        driver.set_size(w, h)
        safe_text = text.replace('"', '\\"').replace('\n', '\\n')
        js = f"""
        (() => {{
            const active = document.getElementById("activeLine");
            active.textContent = "{safe_text}";
            if (window.scheduleSubtitleUpdate) {{
                window.scheduleSubtitleUpdate({{ target: active.textContent, is_final: false }});
            }}
            if (window.__hud_engine__ && window.__hud_engine__.updateScrollOffset) {{
                window.__hud_engine__.updateScrollOffset(false);
            }}

            const stage = document.getElementById("subtitleStage");
            const track = document.getElementById("subtitleTrack");
            const prim = document.getElementById("zonePrimary");
            const activeComputed = window.getComputedStyle(active);
            const stageComputed = window.getComputedStyle(stage);

            const activeRect = active.getBoundingClientRect();
            const primRect = prim.getBoundingClientRect();

            // 解析 translateY 值
            const transform = track.style.transform || "";
            let translateY = 0;
            const match = transform.match(/translateY\\((-?[\\d.]+)px\\)/);
            if (match) {{
                translateY = parseFloat(match[1]);
            }}

            const mask = stageComputed.maskImage || stageComputed.webkitMaskImage || "";
            const isScrolled = stage.classList.contains("is-scrolled");

            return {{
                winW: {w},
                winH: {h},
                stageH: stage.clientHeight,
                primH: prim.clientHeight,
                activeH: active.offsetHeight,
                fontSize: activeComputed.fontSize,
                lineHeight: activeComputed.lineHeight,
                transform: transform,
                translateY: translateY,
                isScrolled: isScrolled,
                mask: mask,
                activeTop: activeRect.top,
                primTop: primRect.top,
                activeBottom: activeRect.bottom,
                primBottom: primRect.bottom
            }};
        }})()
        """
        res = driver.eval_js(js)

        # 0. 双行真实排版断言：确保在当前宽度下确实形成了真实双行排版 (activeH >= 28px)
        active_h = float(res.get("activeH", 0))
        assert active_h >= 28.0, f"[{w}x{h}] activeLine 未形成真实双行排版: 实际高度 activeH={active_h}"

        # 1. 紧凑排版断言：font-size 应为 15px，line-height 应为 1.25 (约 18.75px)
        font_size = res.get("fontSize")
        assert font_size == "15px", f"[{w}x{h}] activeLine 未应用紧凑字体 15px: 实际为 {font_size}"

        # 2. 零过早滚动断言：2 行内容在紧凑视口下应当零滚动或 translateY == 0px
        ty = abs(float(res.get("translateY", 0)))
        assert ty <= 1.0, f"[{w}x{h}] 2 行译文发生过早向上卷动: translateY={res.get('translateY')} (允许误差 <= 1.0px)"

        # 3. 零顶部削顶遮罩断言：未超出视口时不应附加 .is-scrolled 导致首行落入渐隐遮罩
        assert not res.get("isScrolled"), f"[{w}x{h}] 2 行译文意外触发 .is-scrolled 顶部渐变遮罩"
        mask = res.get("mask", "")
        assert "rgba(0, 0, 0, 0)" not in mask and "transparent" not in mask, f"[{w}x{h}] 顶部遮罩存在透明度衰减，首行被削顶: {mask}"

        # 4. 视口包络断言：首行顶端未越出主视口上方
        active_top = float(res.get("activeTop", 0))
        prim_top = float(res.get("primTop", 0))
        assert active_top >= prim_top - 1.0, f"[{w}x{h}] activeLine 顶部被裁切: activeTop={active_top} < primTop={prim_top}"

    print("✅ tests/repro_issue_twoline_output_clip.py: 2行译文在小窗口下零削顶、紧凑字体与零过早滚动验证通过 (GREEN)")


if __name__ == "__main__":
    try:
        test_twoline_output_clip()
        sys.exit(0)
    except AssertionError as e:
        print(f"❌ BUG 复现确立 (红灯): {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ 测试异常: {e}")
        sys.exit(2)
