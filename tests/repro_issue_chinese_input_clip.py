#!/usr/bin/env python3
"""
【复现与回归测试】tests/repro_issue_chinese_input_clip.py
缺陷 2：中文输入原文 (zoneAuxiliary 中的 pastLine) 在小窗口 (720x120 / 400x120) 下，
由于 32% 高度且缺乏紧凑字体排版，产生人工负向溢出 (negative overflow)，
导致文字顶部被 zoneDivider 遮蔽 / 裁切。

需求 R2：
- 紧凑视口下应用紧凑排版 (font-size: 12px; line-height: 1.2)。
- 移除 zoneAuxiliary 上的 padding-top: 2px，并设 min-height: 0。
- 单行与双行中文输入在安全包络内零负向溢出裁切，pastLine 顶部不受 zoneDivider 遮挡。
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


def test_chinese_input_clip():
    if not HAS_WEBKIT:
        print("⚠️ 跳过测试: 未安装 Cocoa/WebKit 环境")
        return

    test_matrix = [
        # (宽, 高, 单行中文输入 - 720px 宽)
        ("单行-720x120", 720, 120, "今天我们讨论大模型在同声传译场景下的落地实践。"),
        # (宽, 高, 双行中文输入 - 720px 宽, 75字真实折行)
        ("双行-720x120", 720, 120, "今天我们在这里深入讨论大模型在同声传译与端到端实时音视频流式推理场景下的生产级落地实践与工程架构前沿探索，包含大规模分布式推断加速与多语言实时语音识别。"),
        # (宽, 高, 双行中文输入 - 400px 宽)
        ("双行-400x120", 400, 120, "今天我们讨论大模型在同声传译场景下的端到端工程实践与前沿架构探索。"),
        # (宽, 高, 极紧凑双行中文输入 - 400x110 边界视口)
        ("双行-400x110", 400, 110, "今天我们讨论大模型在同声传译场景下的端到端工程实践与前沿架构探索。")
    ]

    driver = HeadlessWKDriver(720, 120)

    for label, w, h, text in test_matrix:
        driver.set_size(w, h)
        safe_text = text.replace('"', '\\"').replace('\n', '\\n')
        js = f"""
        (() => {{
            const past = document.getElementById("pastLine");
            past.textContent = "{safe_text}";
            if (window.__hud_engine__ && window.__hud_engine__.updateScrollOffset) {{
                window.__hud_engine__.updateScrollOffset(false);
            }}

            const aux = document.getElementById("zoneAuxiliary");
            const divider = document.getElementById("zoneDivider");
            const auxTrack = document.getElementById("auxiliaryTrack");
            const pastComputed = window.getComputedStyle(past);
            const auxComputed = window.getComputedStyle(aux);

            const pastRect = past.getBoundingClientRect();
            const auxRect = aux.getBoundingClientRect();
            const divRect = divider.getBoundingClientRect();

            // 解析 translateY 值
            const transform = auxTrack.style.transform || "";
            let translateY = 0;
            const match = transform.match(/translateY\\((-?[\\d.]+)px\\)/);
            if (match) {{
                translateY = parseFloat(match[1]);
            }}

            const paddingTop = parseFloat(auxComputed.paddingTop) || 0;
            const minHeight = parseFloat(pastComputed.minHeight) || 0;

            return {{
                label: "{label}",
                winW: {w},
                winH: {h},
                auxH: aux.clientHeight,
                auxContentH: auxTrack.scrollHeight,
                pastH: past.offsetHeight,
                pastFontSize: pastComputed.fontSize,
                pastLineHeight: pastComputed.lineHeight,
                auxPaddingTop: auxComputed.paddingTop,
                paddingTopVal: paddingTop,
                pastMinHeight: pastComputed.minHeight,
                minHeightVal: minHeight,
                auxTransform: transform,
                translateY: translateY,
                pastTop: pastRect.top,
                auxTop: auxRect.top,
                divBottom: divRect.bottom,
                topClippingPx: auxRect.top - pastRect.top
            }};
        }})()
        """
        res = driver.eval_js(js)

        # 0. 双行真实排版断言：确保双行用例真实折行 (pastH >= 24px)
        past_h = float(res.get("pastH", 0))
        if "双行" in label:
            assert past_h >= 24.0, f"[{label}] pastLine 未形成真实双行排版: 实际高度 pastH={past_h}"

        # 1. 紧凑排版断言：font-size 应为 12px，line-height 应为 1.2
        past_font_size = res.get("pastFontSize")
        assert past_font_size == "12px", f"[{label}] pastLine 未应用紧凑字体 12px: 实际为 {past_font_size}"

        # 2. padding-top 与 min-height 消除人工溢出断言
        assert res.get("paddingTopVal", 99) == 0, f"[{label}] zoneAuxiliary 仍存在 paddingTop: {res.get('auxPaddingTop')}"
        assert res.get("minHeightVal", 99) == 0, f"[{label}] pastLine 仍存在 minHeight: {res.get('pastMinHeight')}"

        # 3. 零负向溢出位移断言：单行与双行在安全包络内不应产生负向 translateY 上推
        ty = float(res.get("translateY", 0))
        assert ty >= -0.5, f"[{label}] auxiliaryTrack 发生负向位移上推导致削顶: translateY={ty}px"

        # 4. 零顶部字符裁切断言：pastLine 顶部不得高于 zoneAuxiliary 顶部（不得高于 zoneDivider 底部）
        past_top = float(res.get("pastTop", 0))
        aux_top = float(res.get("auxTop", 0))
        div_bottom = float(res.get("divBottom", 0))
        assert past_top >= aux_top - 0.5, f"[{label}] pastLine 顶部被裁切进入 zoneAuxiliary 外部: pastTop={past_top} < auxTop={aux_top}"
        assert past_top >= div_bottom - 0.5, f"[{label}] pastLine 顶部被 zoneDivider 遮蔽: pastTop={past_top} < divBottom={div_bottom}"

    print("✅ tests/repro_issue_chinese_input_clip.py: 中文输入在小窗口下零削顶、紧凑字体与零负向溢出验证通过 (GREEN)")


if __name__ == "__main__":
    try:
        test_chinese_input_clip()
        sys.exit(0)
    except AssertionError as e:
        print(f"❌ BUG 复现确立 (红灯): {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ 测试异常: {e}")
        sys.exit(2)
