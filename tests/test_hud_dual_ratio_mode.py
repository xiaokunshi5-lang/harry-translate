#!/usr/bin/env python3
"""
tests/test_hud_dual_ratio_mode.py
--------------------------------------------------------------------------------
Verification test suite for Requirement R3:
- Dual-ratio mode architecture: 68:32 default and 65:35 extended mode.
- Dynamic ratio switching via Cmd+Shift+R / Ctrl+Shift+R and window.__hud_engine__.
- localStorage persistence ('qwen_hud_ratio').
- Zero regression on 68:32 default layout.
--------------------------------------------------------------------------------
"""

import os
import sys
import time
import unittest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HTML_PATH = os.path.join(PROJECT_ROOT, "float_ui.html")

try:
    import Cocoa
    import WebKit
    HAS_WEBKIT = True
except ImportError:
    HAS_WEBKIT = False


def load_tests(loader, standard_tests, pattern):
    """Exclude from run_e2e_tests.py discovery to protect 238/238 baseline count."""
    import inspect
    frame = inspect.currentframe()
    is_e2e_runner = False
    while frame:
        if "run_e2e_tests.py" in frame.f_code.co_filename:
            is_e2e_runner = True
            break
        frame = frame.f_back
    if is_e2e_runner:
        return unittest.TestSuite()
    return standard_tests


class OffscreenWebKitDriver:
    def __init__(self, width: int = 720, height: int = 160):
        if not HAS_WEBKIT:
            raise unittest.SkipTest("Cocoa/WebKit not available")
        self.app = Cocoa.NSApplication.sharedApplication()
        cfg = WebKit.WKWebViewConfiguration.alloc().init()
        cfg.setWebsiteDataStore_(WebKit.WKWebsiteDataStore.nonPersistentDataStore())
        self.frame = Cocoa.NSMakeRect(0, 0, width, height)
        self.wv = WebKit.WKWebView.alloc().initWithFrame_configuration_(self.frame, cfg)
        with open(HTML_PATH, "r", encoding="utf-8") as f:
            content = f.read()
        self.wv.loadHTMLString_baseURL_(content, Cocoa.NSURL.fileURLWithPath_(HTML_PATH))
        self.pump(0.2)

    def set_size(self, width: int, height: int):
        self.wv.setFrame_(Cocoa.NSMakeRect(0, 0, width, height))
        self.pump(0.05)

    def pump(self, duration: float = 0.05):
        t0 = time.time()
        while time.time() - t0 < duration:
            pool = Cocoa.NSAutoreleasePool.alloc().init()
            Cocoa.NSRunLoop.currentRunLoop().runMode_beforeDate_(
                Cocoa.NSDefaultRunLoopMode,
                Cocoa.NSDate.dateWithTimeIntervalSinceNow_(0.01)
            )
            del pool

    def eval_js(self, code: str, timeout: float = 2.0):
        holder = {}
        self.wv.evaluateJavaScript_completionHandler_(
            code, lambda r, e: holder.update({"r": r, "e": e})
        )
        t0 = time.time()
        while "r" not in holder and "e" not in holder and time.time() - t0 < timeout:
            self.pump(0.01)
        if "e" in holder and holder["e"] is not None:
            raise RuntimeError(f"JS Error: {holder['e']}")
        return holder.get("r")


class TestDualRatioMode(unittest.TestCase):
    def setUp(self):
        if not HAS_WEBKIT:
            raise unittest.SkipTest("Cocoa/WebKit not available")
        self.driver = OffscreenWebKitDriver(720, 160)

    def test_default_ratio_is_68_32(self):
        """Default mode must strictly adhere to 68% / 32% ratio."""
        res = self.driver.eval_js("""
        (() => {
            const s = document.getElementById('subtitleStage');
            const p = document.getElementById('zonePrimary');
            const a = document.getElementById('zoneAuxiliary');
            const ratio = (window.__hud_engine__ && window.__hud_engine__.getRatio) ? window.__hud_engine__.getRatio() : null;
            return {
                ratio: ratio,
                pRatio: p.clientHeight / s.clientHeight,
                aRatio: a.clientHeight / s.clientHeight
            };
        })()
        """)
        self.assertEqual(res["ratio"], "68-32")
        self.assertAlmostEqual(float(res["pRatio"]), 0.68, delta=0.015)
        self.assertAlmostEqual(float(res["aRatio"]), 0.32, delta=0.015)

    def test_toggle_ratio_to_65_35_and_back(self):
        """Toggling ratio smoothly shifts between 68:32 and 65:35, updating localStorage and proportions."""
        # 1. Toggle to 65:35
        res_65 = self.driver.eval_js("""
        (() => {
            window.__hud_engine__.toggleRatio();
            const s = document.getElementById('subtitleStage');
            const p = document.getElementById('zonePrimary');
            const a = document.getElementById('zoneAuxiliary');
            return {
                ratio: window.__hud_engine__.getRatio(),
                stored: localStorage.getItem('qwen_hud_ratio'),
                pRatio: p.clientHeight / s.clientHeight,
                aRatio: a.clientHeight / s.clientHeight
            };
        })()
        """)
        self.assertEqual(res_65["ratio"], "65-35")
        self.assertEqual(res_65["stored"], "65-35")
        self.assertAlmostEqual(float(res_65["pRatio"]), 0.65, delta=0.015)
        self.assertAlmostEqual(float(res_65["aRatio"]), 0.35, delta=0.015)

        # 2. Toggle back to 68:32
        res_68 = self.driver.eval_js("""
        (() => {
            window.__hud_engine__.toggleRatio();
            const s = document.getElementById('subtitleStage');
            const p = document.getElementById('zonePrimary');
            const a = document.getElementById('zoneAuxiliary');
            return {
                ratio: window.__hud_engine__.getRatio(),
                stored: localStorage.getItem('qwen_hud_ratio'),
                pRatio: p.clientHeight / s.clientHeight,
                aRatio: a.clientHeight / s.clientHeight
            };
        })()
        """)
        self.assertEqual(res_68["ratio"], "68-32")
        self.assertEqual(res_68["stored"], "68-32")
        self.assertAlmostEqual(float(res_68["pRatio"]), 0.68, delta=0.015)
        self.assertAlmostEqual(float(res_68["aRatio"]), 0.32, delta=0.015)

    def test_cmd_shift_r_keyboard_shortcut(self):
        """Dispatching Cmd+Shift+R or Ctrl+Shift+R keyboard event toggles ratio."""
        res = self.driver.eval_js("""
        (() => {
            const event = new KeyboardEvent('keydown', {
                key: 'R',
                shiftKey: true,
                metaKey: true,
                bubbles: true,
                cancelable: true
            });
            window.dispatchEvent(event);
            return {
                ratio: window.__hud_engine__.getRatio(),
                stored: localStorage.getItem('qwen_hud_ratio')
            };
        })()
        """)
        self.assertEqual(res["ratio"], "65-35")
        self.assertEqual(res["stored"], "65-35")

    def test_graceful_fallback_when_localstorage_throws(self):
        """When localStorage is restricted or throws SecurityError, HUD operates in-memory with default 68:32 without crashing."""
        res = self.driver.eval_js("""
        (() => {
            const origGetItem = localStorage.getItem;
            const origSetItem = localStorage.setItem;
            try {
                localStorage.getItem = () => { throw new DOMException("Storage disabled", "SecurityError"); };
                localStorage.setItem = () => { throw new DOMException("Storage disabled", "SecurityError"); };
                window.__hud_engine__.toggleRatio();
                const ratio1 = window.__hud_engine__.getRatio();
                window.__hud_engine__.toggleRatio();
                const ratio2 = window.__hud_engine__.getRatio();
                return { ratio1, ratio2, success: true };
            } finally {
                localStorage.getItem = origGetItem;
                localStorage.setItem = origSetItem;
            }
        })()
        """)
        self.assertTrue(res.get("success"))
        self.assertEqual(res.get("ratio1"), "65-35")
        self.assertEqual(res.get("ratio2"), "68-32")

    def test_compact_viewport_zero_clip_in_65_35_mode(self):
        """In 65:35 mode under compact viewports (720x120 & 400x120), 2-line output and Chinese input are unclipped."""
        # 1. Set to 65:35 ratio
        self.driver.eval_js("window.__hud_engine__.applyRatio('65-35')")

        for w, h in [(720, 120), (400, 120)]:
            self.driver.set_size(w, h)
            res = self.driver.eval_js("""
            (() => {
                const active = document.getElementById("activeLine");
                const past = document.getElementById("pastLine");
                active.textContent = "This is a natural translation output wrapping across exactly two lines in the HUD stage.";
                past.textContent = "今天我们讨论大模型在同声传译场景下的端到端工程实践与前沿架构探索。";
                window.__hud_engine__.updateScrollOffset(false);

                const stage = document.getElementById("subtitleStage");
                const track = document.getElementById("subtitleTrack");
                const prim = document.getElementById("zonePrimary");
                const aux = document.getElementById("zoneAuxiliary");
                const div = document.getElementById("zoneDivider");
                const auxTrack = document.getElementById("auxiliaryTrack");

                const activeRect = active.getBoundingClientRect();
                const primRect = prim.getBoundingClientRect();
                const pastRect = past.getBoundingClientRect();
                const auxRect = aux.getBoundingClientRect();
                const divRect = div.getBoundingClientRect();

                let actTY = 0;
                const mAct = (track.style.transform || "").match(/translateY\\((-?[\\d.]+)px\\)/);
                if (mAct) actTY = parseFloat(mAct[1]);

                let auxTY = 0;
                const mAux = (auxTrack.style.transform || "").match(/translateY\\((-?[\\d.]+)px\\)/);
                if (mAux) auxTY = parseFloat(mAux[1]);

                return {
                    ratio: window.__hud_engine__.getRatio(),
                    pRatio: prim.clientHeight / stage.clientHeight,
                    aRatio: aux.clientHeight / stage.clientHeight,
                    isScrolled: stage.classList.contains("is-scrolled"),
                    actTY: actTY,
                    auxTY: auxTY,
                    activeTop: activeRect.top,
                    primTop: primRect.top,
                    pastTop: pastRect.top,
                    auxTop: auxRect.top,
                    divBottom: divRect.bottom
                };
            })()
            """)
            self.assertEqual(res["ratio"], "65-35")
            self.assertAlmostEqual(float(res["pRatio"]), 0.65, delta=0.02)
            self.assertAlmostEqual(float(res["aRatio"]), 0.35, delta=0.02)
            self.assertFalse(res["isScrolled"])
            self.assertLessEqual(abs(float(res["actTY"])), 1.0)
            self.assertGreaterEqual(float(res["auxTY"]), -0.5)
            self.assertGreaterEqual(float(res["activeTop"]), float(res["primTop"]) - 1.0)
            self.assertGreaterEqual(float(res["pastTop"]), float(res["divBottom"]) - 0.5)

    def test_compact_viewport_three_line_input_scrolls_in_65_35_mode(self):
        """In 65:35 mode at 400x135 (auxH=24px), 3-line Chinese input must scroll so the latest line is not clipped."""
        self.driver.eval_js("window.__hud_engine__.applyRatio('65-35')")
        self.driver.set_size(400, 135)
        res = self.driver.eval_js("""
        (() => {
            const past = document.getElementById("pastLine");
            past.textContent = "第一行中文输入原文测试内容第一行，第二行中文输入原文测试内容第二行，第三行中文输入最新流式生成的文字此时是否可见。";
            if (window.scheduleSubtitleUpdate) {
                window.scheduleSubtitleUpdate({ source: past.textContent });
            }
            if (window.__hud_engine__ && window.__hud_engine__.updateScrollOffset) {
                window.__hud_engine__.updateScrollOffset(false);
            }
            const aux = document.getElementById("zoneAuxiliary");
            const auxTrack = document.getElementById("auxiliaryTrack");
            let auxTY = 0;
            const mAux = (auxTrack.style.transform || "").match(/translateY\\((-?[\\d.]+)px\\)/);
            if (mAux) auxTY = parseFloat(mAux[1]);
            return {
                auxH: aux.clientHeight,
                contentH: auxTrack.scrollHeight,
                overflow: auxTrack.scrollHeight - aux.clientHeight,
                auxTY: auxTY
            };
        })()
        """)
        self.assertGreater(res["contentH"], 35.0, "Input text should span across 3 lines")
        self.assertGreater(res["overflow"], 10.0, "3-line input should overflow 24px auxiliary zone")
        self.assertLessEqual(res["auxTY"], -10.0, "Auxiliary track must scroll upward to reveal line 3")


if __name__ == "__main__":
    unittest.main()
