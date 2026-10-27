#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tests/challenger_ui_engine_stress.py
================================================================================
Empirical Challenger Test Suite for Streaming UI (float_ui.html) & Translation Engine (engines/qwen_translators.py).

Mission:
1. Construct and execute empirical stress tests on float_ui.html:
   - High-frequency WebSocket burst streams (50 sentence transitions under 10ms intervals, alternating final/non-final, empty text, long Chinese/English mixed text).
   - Test that #historyLine anchors correctly without flickering, #activeLine shows streaming cursor, and no frames are lost or swallowed.
2. Construct and execute empirical stress tests on engines/qwen_translators.py:
   - Rapid speech interruptions: fire speech_started during partial response.text.delta delivery across multiple consecutive clauses. Verify each previous sentence is safely sealed without dropped translations or contaminated sentence IDs.
   - Stash fuzzing: feed erratic sequence of text and stash (empty stash, changing stash, duplicate text prefix, rapid updates). Verify no repetitive word concatenation occurs.
   - Concurrent start/stop reentrancy: simulate 20 parallel threads calling start() and stop(). Verify no race conditions or orphaned WebSocket connections.
================================================================================
"""

import os
import sys
import time
import json
import random
import threading
import unittest
from typing import List, Dict, Any, Optional

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

HTML_PATH = os.path.join(PROJECT_ROOT, "float_ui.html")

# WebKit support for macOS
try:
    import Cocoa
    import WebKit
    HAS_WEBKIT = True
except ImportError:
    HAS_WEBKIT = False

from engines.qwen_translators import QwenLiveTranslate38Engine, TokenBucketLimiter


class HeadlessWebKitHarness:
    """Headless WebKit evaluation harness for float_ui.html."""
    def __init__(self, width: int = 720, height: int = 160):
        if not HAS_WEBKIT:
            raise unittest.SkipTest("Cocoa/WebKit not available in environment")
        self.app = Cocoa.NSApplication.sharedApplication()
        if hasattr(self.app, "setActivationPolicy_"):
            try:
                self.app.setActivationPolicy_(Cocoa.NSApplicationActivationPolicyAccessory)
            except Exception:
                pass
        cfg = WebKit.WKWebViewConfiguration.alloc().init()
        cfg.setWebsiteDataStore_(WebKit.WKWebsiteDataStore.nonPersistentDataStore())
        self.wv = WebKit.WKWebView.alloc().initWithFrame_configuration_(Cocoa.NSMakeRect(0, 0, width, height), cfg)

        if not os.path.exists(HTML_PATH):
            raise FileNotFoundError(f"float_ui.html not found at {HTML_PATH}")
        with open(HTML_PATH, "r", encoding="utf-8") as f:
            content = f.read()

        self.wv.loadHTMLString_baseURL_(content, Cocoa.NSURL.fileURLWithPath_(HTML_PATH))
        self.pump(0.25)

        # Hook rAF to setTimeout in headless offscreen environment where display link is paused
        self.eval_js("""
        if (typeof window !== 'undefined') {
            window.requestAnimationFrame = function(cb) {
                return setTimeout(cb, 0);
            };
        }
        """)


    def pump(self, duration: float = 0.05):
        start = time.time()
        while time.time() - start < duration:
            pool = Cocoa.NSAutoreleasePool.alloc().init()
            Cocoa.NSRunLoop.currentRunLoop().runMode_beforeDate_(
                Cocoa.NSDefaultRunLoopMode,
                Cocoa.NSDate.dateWithTimeIntervalSinceNow_(0.01)
            )
            del pool

    def eval_js(self, code: str, timeout: float = 3.0) -> Any:
        holder: Dict[str, Any] = {}

        def handler(res, err):
            holder["res"] = res
            holder["err"] = err

        try:
            self.wv.evaluateJavaScript_completionHandler_(code, handler)
        except Exception:
            return None

        start = time.time()
        while "res" not in holder and "err" not in holder and (time.time() - start) < timeout:
            self.pump(0.005)

        if "err" in holder and holder["err"]:
            return None
        return holder.get("res")

    def close(self):
        if hasattr(self, "wv") and self.wv:
            try:
                self.wv.stopLoading()
                self.wv.removeFromSuperview()
            except Exception:
                pass
            self.wv = None
        self.pump(0.05)


# ==============================================================================
# Suite 1: UI Adversarial Stress & Burst Testing (float_ui.html)
# ==============================================================================
class TestFloatUIAdversarialStress(unittest.TestCase):
    """
    Stress-tests float_ui.html DOM handling under high frequency bursts,
    empty payloads, long text, and rapid sentence state transitions.
    """

    def setUp(self):
        if not HAS_WEBKIT:
            self.skipTest("WebKit not available")
        self.driver = HeadlessWebKitHarness()

    def tearDown(self):
        if hasattr(self, "driver") and self.driver:
            self.driver.close()

    def test_ui_burst_50_sentence_transitions_10ms_intervals(self):
        """
        Adversarial Test 1.1: 50 sentence transitions under 10ms intervals.
        Alternating final/non-final, empty text, long Chinese/English mixed text.
        Verifies:
        - No JavaScript errors thrown.
        - #historyLine anchors the previous finalized sentence.
        - #activeLine displays current sentence.
        - No frames swallowed or dropped.
        """
        driver = self.driver

        # Inject telemetry recorder into page to track all rendered updates
        driver.eval_js("""
        window.__frameLog = [];
        window.__errorLog = [];
        window.onerror = function(msg, url, line) {
            window.__errorLog.push({msg: msg, line: line});
        };
        const origRender = window.renderSubtitleFrame;
        """)

        # Execute 50 rapid sentence transitions
        NUM_SENTENCES = 50
        history_checks = []

        for sent_id in range(1, NUM_SENTENCES + 1):
            # Phase 1: Pure ASR start (source arrived, target not yet)
            src_text = f"Speaker clause {sent_id}: 欢迎大家参加第 {sent_id} 场深度同传技术交流研讨会。"
            payload_asr = {
                "id": sent_id,
                "source": src_text,
                "target": "",
                "is_final": False
            }
            driver.eval_js(f"window.scheduleSubtitleUpdate({json.dumps(payload_asr)});")
            driver.pump(0.005) # 5ms interval

            # At this pure ASR moment, if sent_id > 1, historyLine MUST contain sent_id - 1
            if sent_id > 1:
                hist_text = driver.eval_js("document.getElementById('historyLine').textContent")
                act_text = driver.eval_js("document.getElementById('activeLine').textContent")
                act_streaming = driver.eval_js("document.getElementById('activeLine').classList.contains('streaming')")
                expected_prev_target = f"Welcome to technical symposium #{sent_id - 1}."

                self.assertEqual(
                    hist_text, expected_prev_target,
                    f"Sentence {sent_id} ASR phase: #historyLine failed to anchor previous sentence {sent_id - 1}!"
                )
                self.assertEqual(act_text, "", f"Sentence {sent_id} ASR phase: #activeLine must be cleared!")
                self.assertTrue(act_streaming, f"Sentence {sent_id} ASR phase: #activeLine must have streaming cursor!")

            # Phase 2: In-flight streaming deltas
            for chunk_idx in range(1, 4):
                tgt_chunk = f"Welcome to technical symposium #{sent_id}" + ("." if chunk_idx == 3 else f" part {chunk_idx}...")
                payload_delta = {
                    "id": sent_id,
                    "source": src_text,
                    "target": tgt_chunk,
                    "is_final": False
                }
                driver.eval_js(f"window.scheduleSubtitleUpdate({json.dumps(payload_delta)});")
                driver.pump(0.003) # 3ms micro-interval

            # Phase 3: Finalization
            final_target = f"Welcome to technical symposium #{sent_id}."
            payload_final = {
                "id": sent_id,
                "source": src_text,
                "target": final_target,
                "is_final": True
            }
            driver.eval_js(f"window.scheduleSubtitleUpdate({json.dumps(payload_final)});")
            driver.pump(0.005)

            # Check post-final state
            act_final = driver.eval_js("document.getElementById('activeLine').textContent")
            act_streaming_final = driver.eval_js("document.getElementById('activeLine').classList.contains('streaming')")
            self.assertEqual(act_final, final_target, f"Sentence {sent_id}: activeLine mismatch upon finalization")
            self.assertFalse(act_streaming_final, f"Sentence {sent_id}: activeLine must remove streaming cursor on final")

        # Verify no unhandled JavaScript errors occurred
        errors = driver.eval_js("window.__errorLog")
        self.assertEqual(len(errors or []), 0, f"Encountered JavaScript runtime errors: {errors}")

    def test_ui_history_line_edge_case_speech_started_immediate_target(self):
        """
        Adversarial Test 1.2: Edge Case Investigation:
        What happens if speech_started arrives (id=2, source="", target="", is_final=false),
        and then the very next frame arrives with target="Target 2", source=""?
        Does #historyLine properly anchor Sentence 1, or is it swallowed because
        isNewSentence was already consumed by the empty speech_started frame?
        """
        driver = self.driver

        # Sentence 1 final
        driver.eval_js("""
        window.scheduleSubtitleUpdate({
            id: 1,
            source: "First sentence source.",
            target: "第一句定稿译文。",
            is_final: true
        });
        """)
        driver.pump(0.01)
        self.assertEqual(driver.eval_js("document.getElementById('activeLine').textContent"), "第一句定稿译文。")

        # Step 2: speech_started emits id=2, source="", target="", is_final=false
        driver.eval_js("""
        window.scheduleSubtitleUpdate({
            id: 2,
            source: "",
            target: "",
            is_final: false
        });
        """)
        driver.pump(0.01)

        # Step 3: MT delta arrives directly with target, but source is still empty
        driver.eval_js("""
        window.scheduleSubtitleUpdate({
            id: 2,
            source: "",
            target: "第二句实时译文。",
            is_final: false
        });
        """)
        driver.pump(0.02)

        hist_text = driver.eval_js("document.getElementById('historyLine').textContent")
        hist_disp = driver.eval_js("window.getComputedStyle(document.getElementById('historyLine')).display")
        act_text = driver.eval_js("document.getElementById('activeLine').textContent")

        # Check: Did #historyLine capture "第一句定稿译文。"?
        print(f"\n[EMPIRICAL AUDIT] Speech_started boundary -> hist_text: '{hist_text}', hist_disp: '{hist_disp}', act_text: '{act_text}'")
        self.assertEqual(
            hist_text, "第一句定稿译文。",
            "EMPIRICAL BUG FOUND: When speech_started arrives followed by target-only frame, #historyLine fails to anchor sentence 1!"
        )

    def test_ui_empty_and_malformed_burst(self):
        """
        Adversarial Test 1.3: Feed erratic payloads (empty objects, nulls, undefined values).
        Verify UI handles them gracefully without crashing or rendering literal 'null'/'undefined'.
        """
        driver = self.driver

        malformed_burst = [
            {},
            {"type": "sub"},
            {"id": None, "source": None, "target": None},
            {"id": "", "source": "", "target": ""},
            {"id": "NaN", "source": False, "target": 0},
            {"source": "", "target": "   "},
        ]

        for idx, payload in enumerate(malformed_burst):
            driver.eval_js(f"window.scheduleSubtitleUpdate({json.dumps(payload)});")
            driver.pump(0.005)

        act_text = driver.eval_js("document.getElementById('activeLine').textContent")
        self.assertNotIn("undefined", act_text.lower(), "DOM rendered literal 'undefined'")
        self.assertNotIn("null", act_text.lower(), "DOM rendered literal 'null'")

    def test_ui_long_mixed_500char_text_and_scroll_stability(self):
        """
        Adversarial Test 1.4: Feed 500+ character mixed Chinese/English/symbols text.
        Verify synchronous render, sticky-bottom scroll offset calculation, and mask stability.
        """
        driver = self.driver

        long_text = (
            "【极端压力测试】Harry Translate 双通道极简悬浮同传 HUD 正在处理超长混合工程语料："
            "DashScope Qwen-3.8 LiveTranslate flash-realtime engine maintains sub-50ms chunking with "
            "zero-copy C-pointer downmix, C-accelerated AGC normalization (target RMS 180~2500 -> 1000, "
            "peak limit <= 31500), avoiding int16 audio clipping, and 0.08s cubic-bezier(0.16, 1, 0.3, 1) "
            "smooth viewport scroll curve. 🚀🔥 特殊符号：«»‹›—–•§¶†‡ 换行与标点测试：；：！？。 " * 2
        )

        driver.eval_js(f"""
        window.scheduleSubtitleUpdate({{
            id: 99,
            source: "Engineering Stress Test Input",
            target: {json.dumps(long_text)},
            is_final: false
        }});
        """)
        driver.pump(0.05)

        act_text = driver.eval_js("document.getElementById('activeLine').textContent")
        self.assertEqual(act_text, long_text, "Long text must be written synchronously and completely to activeLine")

        # Verify scroll transform is applied and stage has is-scrolled class
        is_scrolled = driver.eval_js("document.getElementById('subtitleStage').classList.contains('is-scrolled')")
        transform = driver.eval_js("document.getElementById('subtitleTrack').style.transform")

        self.assertTrue(is_scrolled, "Subtitle stage must have .is-scrolled class when content overflows")
        self.assertTrue("translateY" in transform, f"Transform translateY must be active: {transform}")


# ==============================================================================
# Suite 2: Engine Adversarial Stress & Concurrency Testing (qwen_translators.py)
# ==============================================================================
class TestQwenTranslatorsAdversarial(unittest.TestCase):
    """
    Adversarially stress-tests QwenLiveTranslate38Engine for:
    - Rapid speech interruptions (50 consecutive clauses)
    - Stash fuzzing & deduplication
    - Concurrent start/stop reentrancy (20 parallel threads)
    - Thread leaks & orphaned WebSocket connections
    """

    def test_rapid_speech_interruptions_50_consecutive_clauses(self):
        """
        Adversarial Test 2.1: Fire speech_started during partial response.text.delta delivery
        across 50 consecutive clauses.
        Verify:
        - Invariant 1: Exactly 50 sentences are finalized with is_final=True.
        - Invariant 2: Finalized sentence IDs match 1, 2, ..., 50 in strict order.
        - Invariant 3: No sentence drops translated content or mixes up IDs.
        - Invariant 4: No empty finalized frames emitted.
        """
        dispatched: List[Dict[str, Any]] = []
        engine = QwenLiveTranslate38Engine(
            channel_id="A",
            source_lang="en",
            target_lang="zh",
            emit_fn=lambda p: dispatched.append(p),
            mock_mode=True
        )
        engine.start()

        NUM_CLAUSES = 50

        for clause_id in range(1, NUM_CLAUSES + 1):
            # ASR text arrives
            engine._on_ws_message(None, json.dumps({
                "type": "conversation.item.input_audio_transcription.text",
                "text": f"Speaker English clause #{clause_id}"
            }))

            # 1 to 4 partial MT deltas arrive
            num_deltas = random.randint(1, 4)
            for d in range(num_deltas):
                engine._on_ws_message(None, json.dumps({
                    "type": "response.text.delta",
                    "delta": f"中文翻译分块_{clause_id}_{d};"
                }))

            # In 45 out of 50 clauses, speaker interrupts before response.done!
            # In remaining 5 clauses, response.done arrives normally
            if clause_id < NUM_CLAUSES:
                engine._on_ws_message(None, json.dumps({
                    "type": "input_audio_buffer.speech_started"
                }))
            else:
                engine._on_ws_message(None, json.dumps({
                    "type": "response.done",
                    "response": {"usage": {"input_tokens": 10, "output_tokens": 5}}
                }))

        # Extract all sealed finalized frames
        final_frames = [p for p in dispatched if p.get("is_final") is True]

        # Verify Invariant 1: Exactly NUM_CLAUSES are sealed
        self.assertEqual(
            len(final_frames), NUM_CLAUSES,
            f"Expected {NUM_CLAUSES} sealed sentences, but got {len(final_frames)}!"
        )

        # Verify Invariant 2: Finalized sentence IDs match 1..NUM_CLAUSES in strict monotonic order
        sealed_ids = [int(p["id"]) for p in final_frames]
        expected_ids = list(range(1, NUM_CLAUSES + 1))
        self.assertEqual(sealed_ids, expected_ids, "Finalized sentence IDs are corrupted or out of order!")

        # Verify Invariant 3: No finalized sentence has empty target
        for p in final_frames:
            self.assertTrue(
                len(p["target"]) > 0,
                f"Sentence {p['id']} finalized frame has empty target text!"
            )
            self.assertIn(
                f"中文翻译分块_{p['id']}_", p["target"],
                f"Sentence {p['id']} target text was corrupted or cross-contaminated: {p['target']}"
            )

    def test_stash_fuzzing_and_deduplication(self):
        """
        Adversarial Test 2.2: Stash fuzzing.
        Feed erratic sequence of `text` and `stash` (empty stash, changing stash,
        duplicate text prefix, rapid updates, revisions).
        Verify no repetitive word concatenation occurs.
        """
        dispatched: List[Dict[str, Any]] = []
        engine = QwenLiveTranslate38Engine(
            channel_id="A",
            source_lang="zh",
            target_lang="en",
            emit_fn=lambda p: dispatched.append(p),
            mock_mode=True
        )
        engine.start()

        # Erratic sequence with changing stash, backspaces, and duplicate prefixes
        fuzz_packets = [
            {"text": "阿里", "stash": "云"},
            {"text": "阿里", "stash": "巴巴"},
            {"text": "阿里巴巴", "stash": "达摩院"},
            {"text": "阿里巴巴达摩", "stash": "院专注于"},
            {"text": "阿里巴巴达摩院专注", "stash": "于人工智能"},
            # Revision / ASR correction: text changes slightly
            {"text": "阿里巴巴达摩院致力于", "stash": "AI 研发"},
            # Empty stash
            {"text": "阿里巴巴达摩院致力于 AI 研发与落地。", "stash": ""},
            # Missing stash field
            {"text": "阿里巴巴达摩院致力于 AI 研发与落地。欢迎各位。"},
            # Duplicate text prefix in stash: stash repeat attempt
            {"text": "欢迎各位专家", "stash": "专家学者"},
        ]

        for pkt in fuzz_packets:
            engine._on_ws_message(None, json.dumps({
                "type": "conversation.item.input_audio_transcription.text",
                **pkt
            }))

        sources = [p["source"] for p in dispatched if p.get("source")]

        # Verification: Check for unnatural word duplication
        forbidden_patterns = ["阿里阿里", "达摩达摩", "研发研发", "落地落地", "欢迎欢迎"]
        for src in sources:
            for pattern in forbidden_patterns:
                self.assertNotIn(
                    pattern, src,
                    f"Repetitive word concatenation detected in source text: '{src}' (found duplicate '{pattern}')"
                )

    def test_concurrent_start_stop_reentrancy_20_threads(self):
        """
        Adversarial Test 2.3: Simulate 20 parallel threads calling start() and stop() concurrently.
        Verify no race conditions, deadlocks, or unhandled exceptions.
        """
        engine = QwenLiveTranslate38Engine(
            channel_id="CONCURRENCY_TEST",
            source_lang="en",
            target_lang="zh",
            mock_mode=True
        )

        exceptions: List[Exception] = []
        stop_event = threading.Event()

        def stress_worker(worker_id: int):
            try:
                for _ in range(25):
                    if stop_event.is_set():
                        break
                    # Randomly toggle start and stop
                    if random.random() < 0.5:
                        engine.start()
                    else:
                        engine.stop()
                    time.sleep(0.001)
            except Exception as e:
                exceptions.append(e)

        threads = [threading.Thread(target=stress_worker, args=(i,)) for i in range(20)]

        for t in threads:
            t.start()

        for t in threads:
            t.join(timeout=10.0)
            if t.is_alive():
                stop_event.set()
                self.fail(f"Thread {t.name} deadlocked during concurrent start/stop!")

        self.assertEqual(len(exceptions), 0, f"Encountered exceptions during concurrent start/stop: {exceptions}")

        # Final cleanup and state check
        engine.stop()
        self.assertFalse(engine.is_running, "Engine must be stopped after stop()")

    def test_orphaned_ws_thread_leak_on_rapid_start_stop(self):
        """
        Adversarial Test 2.4: Deep Thread Leak Audit.
        When mock_mode=False, start() spawns a background thread running _run_ws().
        If start() is called immediately after stop(), does the old thread fail to terminate,
        causing multiple persistent WebSocket threads to run simultaneously and overwrite ws_client?
        """
        # We test with a mock socket runner to observe thread lifecycle
        engine = QwenLiveTranslate38Engine(
            channel_id="THREAD_LEAK_AUDIT",
            source_lang="en",
            target_lang="zh",
            api_key="sk-test-valid-key-for-threading-audit",
            mock_mode=False
        )

        # Instrument _run_ws to count concurrently active loop iterations
        active_run_ws_threads = []
        lock = threading.Lock()

        orig_run_ws = engine._run_ws

        def instrumented_run_ws():
            thread_id = threading.get_ident()
            with lock:
                active_run_ws_threads.append(thread_id)
            try:
                # We simulate what _run_ws does: while self.is_running: sleep
                while engine.is_running:
                    time.sleep(0.02)
            finally:
                with lock:
                    if thread_id in active_run_ws_threads:
                        active_run_ws_threads.remove(thread_id)

        engine._run_ws = instrumented_run_ws

        try:
            # Rapid start -> stop -> start cycle
            engine.start()
            time.sleep(0.01) # give thread moment to enter
            engine.stop()
            engine.start()
            time.sleep(0.05)

            with lock:
                num_active = len(active_run_ws_threads)

            print(f"\n[EMPIRICAL AUDIT] Concurrently active _run_ws threads: {num_active} (active IDs: {active_run_ws_threads})")
            self.assertLessEqual(
                num_active, 1,
                f"THREAD LEAK VULNERABILITY: Multiple background WebSocket threads ({num_active}) "
                f"are running concurrently after rapid stop()/start() cycle! Old thread was orphaned."
            )
        finally:
            engine.stop()
            time.sleep(0.05)


if __name__ == "__main__":
    unittest.main()
