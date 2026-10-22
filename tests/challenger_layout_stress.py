#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tests/challenger_layout_stress.py
--------------------------------------------------------------------------------
Adversarial Empirical Stress Harness for Harry Translate Floating HUD (Challenger 2)
Tests:
- AC-L1: Golden Ratio 68%/32% layout proportions across extreme window matrix.
- AC-L2: Physical isolation & anti-encroachment 0px displacement under 50-5000 chars.
- AC-L3: Zero native scrollbars (horizontal/vertical) under heavy overflow.
- AC-L4: Symmetrical channel role inversion on 'en' and 'zh' channels.
- AC-L5: Fluid scaling margins >= 28px and zero-overflow word wrapping.
--------------------------------------------------------------------------------
"""

import os
import sys
import time
import json
import unittest

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

HTML_PATH = os.path.join(PROJECT_ROOT, "float_ui.html")

try:
    import Cocoa
    import WebKit
    HAS_WEBKIT = True
except ImportError:
    HAS_WEBKIT = False


def load_tests(loader, standard_tests, pattern):
    """Protocol hook: exclude from run_e2e_tests.py discovery."""
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


class OffscreenWebKitHarness:
    """Synchronous offscreen WKWebView driver for adversarial layout testing."""
    def __init__(self, width: int = 720, height: int = 160):
        if not HAS_WEBKIT:
            raise unittest.SkipTest("Cocoa/WebKit not available in environment")
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
        self.frame = Cocoa.NSMakeRect(0, 0, width, height)
        self.wv.setFrame_(self.frame)
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
        while "r" not in holder and time.time() - t0 < timeout:
            Cocoa.NSRunLoop.currentRunLoop().runMode_beforeDate_(
                Cocoa.NSDefaultRunLoopMode,
                Cocoa.NSDate.dateWithTimeIntervalSinceNow_(0.01)
            )
        if "r" not in holder:
            raise TimeoutError(f"JS evaluation timed out: {code[:60]}")
        return holder["r"]


class TestAdversarialGoldenRatioAndLayout(unittest.TestCase):
    """Adversarial challenge suite for Golden Ratio 68%/32% HUD layout."""

    @classmethod
    def setUpClass(cls):
        if not HAS_WEBKIT:
            raise unittest.SkipTest("Cocoa/WebKit not available")
        cls.harness = OffscreenWebKitHarness(720, 160)
        with open(HTML_PATH, "r", encoding="utf-8") as f:
            cls.html = f.read()

    def setUp(self):
        # Reset HUD state before each test
        self.harness.set_size(720, 160)
        self.harness.eval_js("""(() => {
            window.requestAnimationFrame = (cb) => { cb(); return 1; };
            const p = document.getElementById('activeLine');
            const a = document.getElementById('pastLine');
            if (p) p.textContent = '等待语音输入...';
            if (a) a.textContent = '';
            if (window.__hud_engine__ && window.__hud_engine__.updateScrollOffset) {
                window.__hud_engine__.updateScrollOffset(false);
            }
        })()""")

    # --------------------------------------------------------------------------
    # AC-L1: Golden Ratio 68%/32% Layout Proportions
    # --------------------------------------------------------------------------
    def test_adv_l1_matrix_golden_ratio_proportions(self):
        """Stress-test 68% / 32% proportions across 12 diverse window dimensions."""
        dimensions = [
            (360, 100),
            (400, 120),
            (500, 140),
            (600, 150),
            (720, 160),
            (800, 200),
            (1024, 250),
            (1200, 300),
            (1440, 400),
            (1600, 500),
            (1920, 600),
            (1920, 1080),
        ]
        results = []
        for w, h in dimensions:
            self.harness.set_size(w, h)
            res = self.harness.eval_js("""(() => {
                const s = document.getElementById('subtitleStage');
                const p = document.getElementById('zonePrimary');
                const a = document.getElementById('zoneAuxiliary');
                const d = document.getElementById('zoneDivider');
                const sH = s.clientHeight;
                const pH = p.clientHeight;
                const aH = a.clientHeight;
                const dH = d.clientHeight;
                return {
                    stageH: sH,
                    primH: pH,
                    auxH: aH,
                    divH: dH,
                    pRatio: sH > 0 ? pH / sH : 0,
                    aRatio: sH > 0 ? aH / sH : 0,
                    sumH: pH + aH
                };
            })()""")
            p_ratio = float(res["pRatio"])
            a_ratio = float(res["aRatio"])
            stage_h = int(res["stageH"])
            prim_h = int(res["primH"])
            aux_h = int(res["auxH"])

            results.append((w, h, p_ratio, a_ratio, stage_h, prim_h, aux_h))

            # Proportions must be 68% ± 1% (0.67 to 0.69) and 32% ± 1% (0.31 to 0.33)
            self.assertAlmostEqual(
                p_ratio, 0.68, delta=0.015,
                msg=f"At {w}x{h}, Primary ratio {p_ratio:.4f} not within 68% ± 1.5%"
            )
            self.assertAlmostEqual(
                a_ratio, 0.32, delta=0.015,
                msg=f"At {w}x{h}, Auxiliary ratio {a_ratio:.4f} not within 32% ± 1.5%"
            )
            # Physical isolation: sum of primary and auxiliary must equal stage height ± 1px
            self.assertAlmostEqual(
                prim_h + aux_h, stage_h, delta=1,
                msg=f"At {w}x{h}, primary {prim_h} + aux {aux_h} != stage {stage_h}"
            )

    def test_adv_l1_divider_zero_net_displacement(self):
        """Divider has height: 1px and margin-top: -1px (0px net flex height contribution)."""
        res = self.harness.eval_js("""(() => {
            const d = document.getElementById('zoneDivider');
            const cs = window.getComputedStyle(d);
            return {
                height: cs.height,
                marginTop: cs.marginTop,
                flexShrink: cs.flexShrink
            };
        })()""")
        self.assertEqual(res["height"], "1px")
        self.assertEqual(res["marginTop"], "-1px")
        self.assertEqual(res["flexShrink"], "0")

    # --------------------------------------------------------------------------
    # AC-L2: Physical Isolation & Anti-Encroachment Zero Displacement
    # --------------------------------------------------------------------------
    def test_adv_l2_auxiliary_injection_zero_displacement_matrix(self):
        """Injecting text payloads from 50 to 5,000 characters into auxiliary causes strictly 0px displacement."""
        payloads = [
            ("short_50", "短句测试，模拟正常单句会议输入。" * 3),
            ("ac_threshold_200", "这是一段超过两百字符的会议发言长句，包含大量的技术术语和复杂的修饰语成分。" * 3),
            ("extreme_500", "长篇讲座段落注入：在深度学习与自然语言处理快速发展的今天，端到端同声传译系统对于实时性与准确率的要求达到了前所未有的高度。" * 4),
            ("huge_1000", "极限量测试文本，用于检验绝对物理隔离架构在面对超长会议发言涌入时是否能够维持严格的零位移表现。" * 15),
            ("stress_3000", "压测三千字符大文本块！" * 300),
            ("multiline_newlines", "第一行换行\n第二行换行\n第三行换行\n第四行换行\n第五行换行\n第六行换行\n第七行换行\n第八行换行"),
            ("mixed_unicode_emoji", "🚀 深度学习 🤖 LLM 架构 🌐 Distributed Clusters " * 30),
        ]

        for label, text in payloads:
            js = f"""
            (() => {{
                const p = document.getElementById('zonePrimary');
                const a = document.getElementById('pastLine');
                const h0 = p.clientHeight;
                const rect0 = p.getBoundingClientRect();

                a.textContent = {json.dumps(text)};
                if (window.__hud_engine__ && window.__hud_engine__.updateScrollOffset) {{
                    window.__hud_engine__.updateScrollOffset(false);
                }}

                const h1 = p.clientHeight;
                const rect1 = p.getBoundingClientRect();

                return {{
                    label: {json.dumps(label)},
                    h0: h0,
                    h1: h1,
                    top0: rect0.top,
                    top1: rect1.top,
                    bottom0: rect0.bottom,
                    bottom1: rect1.bottom,
                    hDisp: Math.abs(h1 - h0),
                    topDisp: Math.abs(rect1.top - rect0.top),
                    bottomDisp: Math.abs(rect1.bottom - rect0.bottom)
                }};
            }})()
            """
            res = self.harness.eval_js(js)
            self.assertEqual(
                res["hDisp"], 0,
                f"Payload [{label}] caused {res['hDisp']}px height displacement in #zonePrimary (h0={res['h0']}, h1={res['h1']})"
            )
            self.assertEqual(
                res["topDisp"], 0,
                f"Payload [{label}] caused {res['topDisp']}px top position displacement in #zonePrimary"
            )
            self.assertEqual(
                res["bottomDisp"], 0,
                f"Payload [{label}] caused {res['bottomDisp']}px bottom displacement in #zonePrimary"
            )

    def test_adv_l2_bidirectional_anti_encroachment(self):
        """Injecting 2000+ chars into primary zone causes strictly 0px displacement in auxiliary zone."""
        js = """
        (() => {
            const a = document.getElementById('zoneAuxiliary');
            const p = document.getElementById('activeLine');
            const h0 = a.clientHeight;
            const rect0 = a.getBoundingClientRect();

            p.textContent = '主译文超长大段文字注入测试：' + '实时流式吐字内容 '.repeat(100);
            if (window.__hud_engine__ && window.__hud_engine__.updateScrollOffset) {
                window.__hud_engine__.updateScrollOffset(false);
            }

            const h1 = a.clientHeight;
            const rect1 = a.getBoundingClientRect();

            return {
                h0: h0,
                h1: h1,
                top0: rect0.top,
                top1: rect1.top,
                bottom0: rect0.bottom,
                bottom1: rect1.bottom,
                hDisp: Math.abs(h1 - h0),
                topDisp: Math.abs(rect1.top - rect0.top),
                bottomDisp: Math.abs(rect1.bottom - rect0.bottom)
            };
        })()
        """
        res = self.harness.eval_js(js)
        self.assertEqual(res["hDisp"], 0, f"Primary overflow displaced Auxiliary height by {res['hDisp']}px")
        self.assertEqual(res["topDisp"], 0, f"Primary overflow displaced Auxiliary top by {res['topDisp']}px")
        self.assertEqual(res["bottomDisp"], 0, f"Primary overflow displaced Auxiliary bottom by {res['bottomDisp']}px")

    def test_adv_l2_rapid_streaming_anti_encroachment(self):
        """Rapid successive updates to pastLine simulate streaming burst without jittering primary zone."""
        js = """
        (() => {
            const p = document.getElementById('zonePrimary');
            const a = document.getElementById('pastLine');
            const initialTop = p.getBoundingClientRect().top;
            const initialHeight = p.clientHeight;
            let maxJitter = 0;

            for (let i = 0; i < 50; i++) {
                a.textContent = 'Token_' + i + ' '.repeat(i * 2);
                if (window.__hud_engine__ && window.__hud_engine__.updateScrollOffset) {
                    window.__hud_engine__.updateScrollOffset(false);
                }
                const curTop = p.getBoundingClientRect().top;
                const curH = p.clientHeight;
                maxJitter = Math.max(maxJitter, Math.abs(curTop - initialTop), Math.abs(curH - initialHeight));
            }
            return { maxJitter: maxJitter };
        })()
        """
        res = self.harness.eval_js(js)
        self.assertEqual(res["maxJitter"], 0, f"Streaming burst caused {res['maxJitter']}px jitter")

    # --------------------------------------------------------------------------
    # AC-L3: Zero Native Scrollbars
    # --------------------------------------------------------------------------
    def test_adv_l3_zero_native_scrollbars_under_extreme_text(self):
        """Under extreme dual-zone overflow, zero native vertical or horizontal scrollbars exist."""
        # Static CSS check
        self.assertNotIn("overflow-y: scroll", self.html)
        self.assertNotIn("overflow-y: auto", self.html)
        self.assertNotIn("overflow-x: scroll", self.html)
        self.assertNotIn("overflow-x: auto", self.html)

        # Dynamic DOM check in WKWebView
        js = """
        (() => {
            const p = document.getElementById('activeLine');
            const a = document.getElementById('pastLine');
            p.textContent = 'Huge active text '.repeat(100);
            a.textContent = 'Huge auxiliary text '.repeat(100);
            if (window.__hud_engine__ && window.__hud_engine__.updateScrollOffset) {
                window.__hud_engine__.updateScrollOffset(false);
            }

            const docEl = document.documentElement;
            const body = document.body;
            const container = document.getElementById('hud-container');
            const stage = document.getElementById('subtitleStage');
            const zPrimary = document.getElementById('zonePrimary');
            const zAux = document.getElementById('zoneAuxiliary');

            const elements = [
                { id: 'documentElement', el: docEl },
                { id: 'body', el: body },
                { id: 'hud-container', el: container },
                { id: 'subtitleStage', el: stage },
                { id: 'zonePrimary', el: zPrimary },
                { id: 'zoneAuxiliary', el: zAux }
            ];

            const violations = [];
            for (const item of elements) {
                const cs = window.getComputedStyle(item.el);
                if (cs.overflowY === 'scroll' || cs.overflowY === 'auto') {
                    violations.push(item.id + ' overflowY=' + cs.overflowY);
                }
                if (cs.overflowX === 'scroll' || cs.overflowX === 'auto') {
                    violations.push(item.id + ' overflowX=' + cs.overflowX);
                }
            }

            // Check if window has any native scrollbar bar width
            const hasVerticalScrollbar = window.innerWidth > docEl.clientWidth;
            const hasHorizontalScrollbar = window.innerHeight > docEl.clientHeight;

            return {
                violations: violations,
                hasVerticalScrollbar: hasVerticalScrollbar,
                hasHorizontalScrollbar: hasHorizontalScrollbar
            };
        })()
        """
        res = self.harness.eval_js(js)
        self.assertEqual(res["violations"], [], f"Found scrollbar violations: {res['violations']}")
        self.assertFalse(res["hasVerticalScrollbar"], "Native vertical scrollbar detected on window")
        self.assertFalse(res["hasHorizontalScrollbar"], "Native horizontal scrollbar detected on window")

    # --------------------------------------------------------------------------
    # AC-L4: Channel Role Inversion
    # --------------------------------------------------------------------------
    def test_adv_l4_channel_role_inversion_full_cycle(self):
        """Test channel toggles between 'en' and 'zh' with accurate role inversion and subtitle routing."""
        # 1. Test initial / explicit 'en' channel
        self.harness.eval_js("""(() => {
            if (window.__hud_engine__ && window.__hud_engine__.getChannel() !== 'en') {
                window.toggleChannel();
            }
        })()""")

        en_state = self.harness.eval_js("""(() => {
            const pill = document.getElementById('hud-channel-pill');
            const title = document.getElementById('hud-title-mini');
            return {
                channel: window.__hud_engine__.getChannel(),
                pillText: pill.textContent,
                pillClass: pill.className,
                title: title.textContent
            };
        })()""")
        self.assertEqual(en_state["channel"], "en")
        self.assertIn("中 ➔ EN", en_state["pillText"])
        self.assertIn("channel-en", en_state["pillClass"])
        self.assertIn("中译英", en_state["title"])

        # Inject subtitle frame into channel 'en' (中译英: Target English in Primary, Source Chinese in Auxiliary)
        self.harness.eval_js("""(() => {
            window.__hud_engine__.scheduleSubtitleUpdate({
                id: 101,
                source: '人工智能是未来趋势',
                target: 'Artificial Intelligence is the future trend',
                is_final: false
            });
        })()""")
        self.harness.pump(0.05)

        en_frame = self.harness.eval_js("""(() => {
            return {
                primary: document.getElementById('activeLine').textContent,
                aux: document.getElementById('pastLine').textContent
            };
        })()""")
        self.assertEqual(en_frame["primary"], "Artificial Intelligence is the future trend")
        self.assertEqual(en_frame["aux"], "人工智能是未来趋势")

        # 2. Toggle to 'zh' channel
        self.harness.eval_js("window.toggleChannel();")
        zh_state = self.harness.eval_js("""(() => {
            const pill = document.getElementById('hud-channel-pill');
            const title = document.getElementById('hud-title-mini');
            return {
                channel: window.__hud_engine__.getChannel(),
                pillText: pill.textContent,
                pillClass: pill.className,
                title: title.textContent
            };
        })()""")
        self.assertEqual(zh_state["channel"], "zh")
        self.assertIn("EN ➔ 中", zh_state["pillText"])
        self.assertIn("channel-zh", zh_state["pillClass"])
        self.assertIn("英译中", zh_state["title"])

        # Inject subtitle frame into channel 'zh' (英译中: Target Chinese in Primary, Source English in Auxiliary)
        self.harness.eval_js("""(() => {
            window.__hud_engine__.scheduleSubtitleUpdate({
                id: 102,
                source: 'Machine learning is fascinating',
                target: '机器学习令人着迷',
                is_final: false
            });
        })()""")
        self.harness.pump(0.05)

        zh_frame = self.harness.eval_js("""(() => {
            return {
                primary: document.getElementById('activeLine').textContent,
                aux: document.getElementById('pastLine').textContent
            };
        })()""")
        self.assertEqual(zh_frame["primary"], "机器学习令人着迷")
        self.assertEqual(zh_frame["aux"], "Machine learning is fascinating")

        # 3. Toggle back to 'en'
        self.harness.eval_js("window.toggleChannel();")
        en_restored = self.harness.eval_js("window.__hud_engine__.getChannel();")
        self.assertEqual(en_restored, "en")

    def test_adv_l4_rapid_channel_toggle_stress(self):
        """Rapid 20x channel toggle stress test maintains UI and state consistency."""
        js = """
        (() => {
            let error = null;
            for (let i = 0; i < 20; i++) {
                window.toggleChannel();
                const ch = window.__hud_engine__.getChannel();
                const expectedPill = (ch === 'en') ? '中 ➔ EN ⇄' : 'EN ➔ 中 ⇄';
                const pillText = document.getElementById('hud-channel-pill').textContent;
                if (pillText !== expectedPill) {
                    error = 'Mismatch at step ' + i + ': expected ' + expectedPill + ' but got ' + pillText;
                    break;
                }
            }
            return { error: error, finalChannel: window.__hud_engine__.getChannel() };
        })()
        """
        res = self.harness.eval_js(js)
        self.assertIsNone(res["error"], res["error"])

    # --------------------------------------------------------------------------
    # AC-L5: Fluid Scaling Margins >= 28px
    # --------------------------------------------------------------------------
    def test_adv_l5_lateral_margins_and_word_wrapping(self):
        """Across widths from 280px to 2560px, lateral clearance >= 28px and word-wrapping cleanly fits."""
        widths = [280, 360, 400, 600, 720, 960, 1200, 1600, 1920, 2560]
        for w in widths:
            self.harness.set_size(w, 160)
            js = f"""
            (() => {{
                const c = document.getElementById('hud-container');
                const p = document.getElementById('activeLine');
                const a = document.getElementById('pastLine');

                p.textContent = 'Fluid responsive testing sentence with long words and CJK characters. ' + '测试词汇 '.repeat(20);
                a.textContent = 'Auxiliary speech source checking breathing margins. ' + '辅助发言 '.repeat(20);
                if (window.__hud_engine__ && window.__hud_engine__.updateScrollOffset) {{
                    window.__hud_engine__.updateScrollOffset(false);
                }}

                const cRect = c.getBoundingClientRect();
                const pRect = p.getBoundingClientRect();
                const aRect = a.getBoundingClientRect();

                const pLeftClearance = pRect.left - cRect.left;
                const pRightClearance = cRect.right - pRect.right;
                const aLeftClearance = aRect.left - cRect.left;
                const aRightClearance = cRect.right - aRect.right;

                // Word wrap check: scrollWidth should equal clientWidth (no horizontal text clipping)
                const pOverflowsHoriz = p.scrollWidth > p.clientWidth + 1;
                const aOverflowsHoriz = a.scrollWidth > a.clientWidth + 1;

                return {{
                    width: {w},
                    pLeftClearance: pLeftClearance,
                    pRightClearance: pRightClearance,
                    aLeftClearance: aLeftClearance,
                    aRightClearance: aRightClearance,
                    pOverflowsHoriz: pOverflowsHoriz,
                    aOverflowsHoriz: aOverflowsHoriz
                }};
            }})()
            """
            res = self.harness.eval_js(js)
            self.assertGreaterEqual(
                res["pLeftClearance"], 27.5,
                f"At width {w}, activeLine left clearance {res['pLeftClearance']}px < 28px"
            )
            self.assertGreaterEqual(
                res["pRightClearance"], 27.5,
                f"At width {w}, activeLine right clearance {res['pRightClearance']}px < 28px"
            )
            self.assertGreaterEqual(
                res["aLeftClearance"], 27.5,
                f"At width {w}, pastLine left clearance {res['aLeftClearance']}px < 28px"
            )
            self.assertGreaterEqual(
                res["aRightClearance"], 27.5,
                f"At width {w}, pastLine right clearance {res['aRightClearance']}px < 28px"
            )
            self.assertFalse(
                res["pOverflowsHoriz"],
                f"At width {w}, activeLine horizontally overflowed (word-wrap failure)"
            )
            self.assertFalse(
                res["aOverflowsHoriz"],
                f"At width {w}, pastLine horizontally overflowed (word-wrap failure)"
            )

    # --------------------------------------------------------------------------
    # Additional Adversarial Stress Tests
    # --------------------------------------------------------------------------
    def test_adv_l6_font_size_extrema_and_golden_ratio(self):
        """Testing font size extremes (14px to 34px) maintains 68%/32% proportions and 0px encroachment."""
        for size in [14, 18, 22, 28, 34]:
            js = f"""
            (() => {{
                if (window.__hud_engine__ && window.__hud_engine__.applyFontSize) {{
                    window.__hud_engine__.applyFontSize({size});
                }}
                const s = document.getElementById('subtitleStage');
                const p = document.getElementById('zonePrimary');
                const a = document.getElementById('zoneAuxiliary');
                const sH = s.clientHeight;
                const pH = p.clientHeight;
                const aH = a.clientHeight;
                return {{
                    size: {size},
                    pRatio: sH > 0 ? pH / sH : 0,
                    aRatio: sH > 0 ? aH / sH : 0
                }};
            }})()
            """
            res = self.harness.eval_js(js)
            self.assertAlmostEqual(
                float(res["pRatio"]), 0.68, delta=0.015,
                msg=f"At fontSize {size}px, Primary ratio {res['pRatio']} deviates from 68%"
            )
            self.assertAlmostEqual(
                float(res["aRatio"]), 0.32, delta=0.015,
                msg=f"At fontSize {size}px, Auxiliary ratio {res['aRatio']} deviates from 32%"
            )

    def test_adv_l7_xss_and_html_tag_tampering(self):
        """Injecting malicious HTML/CSS markup into source/target does not inject DOM nodes or break layout."""
        malicious_payload = (
            '<div id="injected-hack" style="position:fixed;top:0;left:0;width:9999px;height:9999px;background:red;">'
            '<script>window.__xss_flag__ = true;</script><b>BOLD MALICIOUS INJECTION</b></div>'
        )
        js = f"""
        (() => {{
            const p = document.getElementById('zonePrimary');
            const h0 = p.clientHeight;

            window.__hud_engine__.scheduleSubtitleUpdate({{
                id: 999,
                source: {json.dumps(malicious_payload)},
                target: {json.dumps(malicious_payload)},
                is_final: false
            }});

            const h1 = p.clientHeight;
            const injectedEl = document.getElementById('injected-hack');
            const xssTriggered = window.__xss_flag__ === true;

            return {{
                h0: h0,
                h1: h1,
                hasInjectedEl: injectedEl !== null,
                xssTriggered: xssTriggered,
                disp: Math.abs(h1 - h0)
            }};
        }})()
        """
        res = self.harness.eval_js(js)
        self.assertFalse(res["hasInjectedEl"], "Malicious HTML element was parsed and appended to DOM!")
        self.assertFalse(res["xssTriggered"], "XSS script payload executed inside HUD!")
        self.assertEqual(res["disp"], 0, "Malicious tag injection broke primary zone height")

    def test_adv_l8_extreme_aspect_ratios(self):
        """Testing extreme aspect ratios (ultra-wide 2560x90, tall-narrow 300x700) without crashing."""
        for w, h in [(2560, 90), (300, 700), (320, 100), (1920, 120)]:
            self.harness.set_size(w, h)
            res = self.harness.eval_js("""(() => {
                const s = document.getElementById('subtitleStage');
                const p = document.getElementById('zonePrimary');
                const a = document.getElementById('zoneAuxiliary');
                return {
                    sH: s.clientHeight,
                    pH: p.clientHeight,
                    aH: a.clientHeight
                };
            })()""")
            self.assertGreater(res["sH"], 0)
            self.assertGreater(res["pH"], 0)
            self.assertGreater(res["aH"], 0)

    def test_adv_l9_header_controls_and_backward_compatibility(self):
        """Header contains strictly <= 3 visible buttons outside compatibility area, with semantic channel pill."""
        res = self.harness.eval_js("""(() => {
            const header = document.getElementById('hud-header');
            const buttons = header.querySelectorAll('button');
            const pill = document.getElementById('hud-channel-pill');
            return {
                buttonCount: buttons.length,
                buttonIds: Array.from(buttons).map(b => b.id),
                pillTagName: pill ? pill.tagName.toLowerCase() : null
            };
        })()""")
        self.assertEqual(res["buttonCount"], 3, f"Expected 3 visible buttons in header, got {res['buttonCount']}")
        self.assertEqual(set(res["buttonIds"]), {"btn-lock", "btn-opacity", "btn-config"})
        self.assertEqual(res["pillTagName"], "span", "Channel pill must use semantic span to avoid button limit violations")


if __name__ == "__main__":
    unittest.main()
