#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tests/test_adversarial_viewport_layout.py
--------------------------------------------------------------------------------
Adversarial Stress Test Suite for Viewport & Layout (R1 AC-17, AC-18; R3 AC-20)
Empirical verification on macOS native WKWebView layout engine:
1. 25-Dimension Matrix: Widths (200, 300, 720, 1920, 2560) x Heights (50, 80, 120, 200, 600)
2. Long Streaming Sentences: 3, 5, 8, 15, 20 lines
3. Sticky-Bottom Scroll Offset: overflow = contentH - (stageH - BOTTOM_SAFE_MARGIN)
   Verifying bottom clearance >= 8px and zero clipping.
4. CSS & Styling Guarantees:
   - strict overflow: hidden on .subtitle-stage
   - zero native scrollbars
   - mask-image: linear-gradient top fadeout
   - lateral padding: 10px 28px 12px 28px
--------------------------------------------------------------------------------
"""

import os
import sys
import time
import json
import unittest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HTML_PATH = os.path.join(PROJECT_ROOT, "float_ui.html")

try:
    import Cocoa
    import WebKit
    HAS_WEBKIT = True
except ImportError:
    HAS_WEBKIT = False


class WKWebViewDriver:
    """Helper to run off-screen WKWebView and evaluate JS synchronously."""
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
        while "result" not in res_holder and time.time() - start < timeout:
            Cocoa.NSRunLoop.currentRunLoop().runMode_beforeDate_(
                Cocoa.NSDefaultRunLoopMode,
                Cocoa.NSDate.dateWithTimeIntervalSinceNow_(0.01)
            )
        if "result" not in res_holder:
            raise TimeoutError(f"JS evaluation timed out after {timeout}s: {script[:60]}")
        if res_holder.get("error") is not None:
            raise RuntimeError(f"JS Error: {res_holder['error']}")
        return res_holder["result"]


class TestAdversarialViewportLayout(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not HAS_WEBKIT:
            raise unittest.SkipTest("WebKit/Cocoa not available in Python environment")
        cls.driver = WKWebViewDriver(width=720, height=120)

    @classmethod
    def tearDownClass(cls):
        if hasattr(cls, 'driver') and cls.driver:
            cls.driver.webview = None
            cls.driver = None
        import gc
        gc.collect()

    def test_01_css_rules_and_scrollbar_absence(self):
        """Verify strict overflow: hidden, zero native scrollbars, mask-image, and padding guard."""
        js_check = """
        (() => {
            const stage = document.querySelector('.subtitle-stage');
            const container = document.getElementById('hud-container');
            const stageStyle = window.getComputedStyle(stage);
            const containerStyle = window.getComputedStyle(container);
            const bodyStyle = window.getComputedStyle(document.body);
            const htmlStyle = window.getComputedStyle(document.documentElement);

            const maskImage = stageStyle.maskImage || stageStyle.webkitMaskImage || '';
            const stageOverflow = stageStyle.overflow;
            const containerOverflow = containerStyle.overflow;
            const bodyOverflow = bodyStyle.overflow;
            const htmlOverflow = htmlStyle.overflow;

            return {
                stageOverflow,
                containerOverflow,
                bodyOverflow,
                htmlOverflow,
                maskImage,
                containerPadding: containerStyle.padding,
                paddingLeft: containerStyle.paddingLeft,
                paddingRight: containerStyle.paddingRight,
                paddingTop: containerStyle.paddingTop,
                paddingBottom: containerStyle.paddingBottom,
            };
        })()
        """
        data = self.driver.eval_js(js_check)

        # 1. Overflow hidden
        self.assertEqual(data["stageOverflow"], "hidden", "stage must be overflow: hidden")
        self.assertEqual(data["containerOverflow"], "hidden", "container must be overflow: hidden")
        self.assertEqual(data["bodyOverflow"], "hidden", "body must be overflow: hidden")
        self.assertEqual(data["htmlOverflow"], "hidden", "html must be overflow: hidden")

        # 2. Mask image linear-gradient
        self.assertTrue(
            "linear-gradient" in data["maskImage"].lower(),
            f"mask-image must contain linear-gradient, got: {data['maskImage']}"
        )
        self.assertTrue(
            "28px" in data["maskImage"].lower(),
            f"mask-image must have 28px transition, got: {data['maskImage']}"
        )

        # 3. Lateral padding 28px
        self.assertEqual(data["paddingLeft"], "28px", f"paddingLeft must be 28px, got {data['paddingLeft']}")
        self.assertEqual(data["paddingRight"], "28px", f"paddingRight must be 28px, got {data['paddingRight']}")
        self.assertEqual(data["paddingTop"], "10px", f"paddingTop must be 10px, got {data['paddingTop']}")
        self.assertEqual(data["paddingBottom"], "12px", f"paddingBottom must be 12px, got {data['paddingBottom']}")

    def test_02_lateral_padding_guard_prevents_text_touching_capsule(self):
        """Verify lateral 28px padding margin guard prevents text from touching capsule edges."""
        widths = [200, 300, 720, 1920, 2560]
        for w in widths:
            self.driver.set_window_size(w, 140)
            js = f"""
            (() => {{
                const container = document.getElementById('hud-container');
                const activeLine = document.getElementById('activeLine');
                const pastLine = document.getElementById('pastLine');

                activeLine.textContent = 'Adversarial long text to check edge margins ' + 'word '.repeat(30);
                pastLine.textContent = 'Source speech text ' + '源发言 '.repeat(20);

                window.__hud_engine__.updateScrollOffset(false);

                const cRect = container.getBoundingClientRect();
                const aRect = activeLine.getBoundingClientRect();
                const pRect = pastLine.getBoundingClientRect();

                const leftDistA = aRect.left - cRect.left;
                const rightDistA = cRect.right - aRect.right;
                const leftDistP = pRect.left - cRect.left;
                const rightDistP = cRect.right - pRect.right;

                return {{
                    width: {w},
                    leftDistA,
                    rightDistA,
                    leftDistP,
                    rightDistP,
                }};
            }})()
            """
            res = self.driver.eval_js(js)
            # The padding is 28px + 1px border = ~29px from border box
            self.assertGreaterEqual(
                res["leftDistA"], 27.5,
                f"ActiveLine left distance {res['leftDistA']}px is less than 28px guard at width {w}"
            )
            self.assertGreaterEqual(
                res["rightDistA"], 27.5,
                f"ActiveLine right distance {res['rightDistA']}px is less than 28px guard at width {w}"
            )
            self.assertGreaterEqual(
                res["leftDistP"], 27.5,
                f"PastLine left distance {res['leftDistP']}px is less than 28px guard at width {w}"
            )
            self.assertGreaterEqual(
                res["rightDistP"], 27.5,
                f"PastLine right distance {res['rightDistP']}px is less than 28px guard at width {w}"
            )

    def test_03_multi_line_streaming_and_sticky_bottom_scroll(self):
        """Test long streaming sentences (3, 5, 8, 15, 20 lines) to verify sticky-bottom scroll offset."""
        line_counts = [3, 5, 8, 15, 20]
        window_heights = [120, 140, 200, 300]

        for h in window_heights:
            self.driver.set_window_size(720, h)
            for target_lines in line_counts:
                cjk_sentence = "这是一段非常严谨的流式同声传译测试长句，用于测试视口跟随与底部呼吸留白。" * target_lines

                js = f"""
                (() => {{
                    const stage = document.querySelector('.subtitle-stage');
                    const track = document.querySelector('.subtitle-track');
                    const activeLine = document.getElementById('activeLine');
                    const pastLine = document.getElementById('pastLine');

                    pastLine.textContent = 'Previous finalized sentence / 辅助原语言';
                    activeLine.textContent = {json.dumps(cjk_sentence)};

                    window.__hud_engine__.updateScrollOffset(false);

                    const stageRect = stage.getBoundingClientRect();
                    const trackRect = track.getBoundingClientRect();
                    const activeRect = activeLine.getBoundingClientRect();

                    const stageH = stage.clientHeight;
                    const contentH = track.scrollHeight;
                    const expectedOverflow = Math.max(0, contentH - (stageH - 8));

                    const transform = track.style.transform;
                    const match = transform.match(/translateY\\((-?\\d+(\\.\\d+)?)px\\)/);
                    const actualTranslateY = match ? parseFloat(match[1]) : 0;

                    const trackBottomInStage = contentH + actualTranslateY;
                    const bottomClearance = stageH - trackBottomInStage;

                    return {{
                        targetLines: {target_lines},
                        stageH,
                        contentH,
                        expectedOverflow,
                        actualTranslateY,
                        bottomClearance,
                        trackBottom: trackRect.bottom,
                        stageBottom: stageRect.bottom,
                    }};
                }})()
                """
                res = self.driver.eval_js(js)

                # Verify sticky scroll offset formula
                expected_y = -res["expectedOverflow"]
                self.assertAlmostEqual(
                    res["actualTranslateY"], expected_y, delta=1.0,
                    msg=f"H={h}, Lines={target_lines}: Expected translateY {expected_y}, got {res['actualTranslateY']}"
                )

                # Verify bottom clearance is ALWAYS >= 8px
                if res["stageH"] > 8:
                    self.assertGreaterEqual(
                        res["bottomClearance"], 7.5,
                        f"H={h}, Lines={target_lines}: Bottom clearance {res['bottomClearance']}px < 8px"
                    )
                    self.assertLessEqual(
                        res["trackBottom"], res["stageBottom"] - 7.5,
                        f"H={h}, Lines={target_lines}: Track bottom exceeds stage bottom safety margin"
                    )

    def test_04_stress_test_25_dimension_combinations(self):
        """
        Stress test 25 window dimension combinations:
        Widths: 200, 300, 720, 1920, 2560
        Heights: 50, 80, 120, 200, 600
        Reports exact telemetry and identifies boundary condition behavior.
        """
        widths = [200, 300, 720, 1920, 2560]
        heights = [50, 80, 120, 200, 600]

        telemetry = []

        js = """
        (() => {
            const container = document.getElementById('hud-container');
            const header = document.getElementById('hud-header');
            const stage = document.querySelector('.subtitle-stage');
            const track = document.querySelector('.subtitle-track');
            const activeLine = document.getElementById('activeLine');
            const pastLine = document.getElementById('pastLine');

            activeLine.textContent = '同传高光字幕流式吐字测试。长句视口跟随。';
            pastLine.textContent = '原语音输入内容完整保留。';

            window.__hud_engine__.updateScrollOffset(false);

            const stageH = stage.clientHeight;
            const contentH = track.scrollHeight;
            const headerH = header.clientHeight;
            const containerH = container.clientHeight;

            const transform = track.style.transform;
            const match = transform.match(/translateY\\((-?\\d+(\\.\\d+)?)px\\)/);
            const actualTranslateY = match ? parseFloat(match[1]) : 0;

            const trackBottomInStage = contentH + actualTranslateY;
            const bottomClearance = stageH - trackBottomInStage;

            return {
                stageH,
                contentH,
                headerH,
                containerH,
                actualTranslateY,
                bottomClearance
            };
        })()
        """

        crushed_configs = []
        viable_configs = []

        for w in widths:
            for h in heights:
                self.driver.set_window_size(w, h)
                res = self.driver.eval_js(js)
                res["w"] = w
                res["h"] = h
                telemetry.append(res)

                if res["stageH"] <= 0:
                    crushed_configs.append((w, h, res["headerH"]))
                else:
                    viable_configs.append((w, h))
                    # For all viable configs, verify bottom clearance is >= 7.9px
                    self.assertGreaterEqual(
                        res["bottomClearance"], 7.9,
                        f"W={w}, H={h}: Bottom clearance {res['bottomClearance']}px < 8px"
                    )

        # Confirm that standard/large dimensions (H >= 120) are 100% viable across all widths
        for w in widths:
            for h in [120, 200, 600]:
                self.assertIn((w, h), viable_configs, f"Config W={w}, H={h} should be viable")

        # Confirm that at W=720, 1920, 2560, H=80 is viable
        for w in [300, 720, 1920, 2560]:
            self.assertIn((w, 80), viable_configs, f"Config W={w}, H=80 should be viable")

        # Confirm that below contract height (H=50), configs are in crushed_configs
        for w in widths:
            self.assertIn((w, 50), [(c[0], c[1]) for c in crushed_configs])


    def tearDown(self):
        try:
            self.driver.eval_js("(() => { document.getElementById('activeLine').textContent = ''; document.getElementById('pastLine').textContent = ''; })()")
        except Exception:
            pass
        import gc
        gc.collect()

if __name__ == "__main__":
    unittest.main()
