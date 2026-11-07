#!/usr/bin/env python3
"""
【复现测试】FIX-203:
- R11: QwenLiveTranslate38Engine 计算并输出真实首字延迟 ttft_ms (保留原有 latency_ms)
- R12: Token 计费单价支持环境变量 INPUT_TOKEN_PRICE_PER_M / OUTPUT_TOKEN_PRICE_PER_M 配置
- R13: AhoCorasickAutomaton.replace_all 具备 ASCII 英文单词边界保护，且不破坏中英混排替换与 <0.05ms SLA
"""
import json
import os
import sys
import time
import unittest

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from core.glossary_manager import AhoCorasickAutomaton
from engines import qwen_translators
from engines.qwen_translators import QwenLiveTranslate38Engine


class TestReproFix203(unittest.TestCase):
    def test_r13_ascii_word_boundary_prevents_mid_word_corruption(self):
        """R13: 短英文术语如 AI / PR 不得误伤 rain / spring / OpenAI，但在独立成词或中英混排时必须正常替换。"""
        auto = AhoCorasickAutomaton()
        auto.add_word("AI", "人工智能")
        auto.add_word("PR", "公关")
        auto.build()

        # 1. 英文单词内部子串：严禁误替换
        self.assertEqual(
            auto.replace_all("With the spring rain in Spain, OpenAI released a model."),
            "With the spring rain in Spain, OpenAI released a model.",
        )

        # 2. 独立英文单词（前后为空格或标点）：必须正常替换
        self.assertEqual(
            auto.replace_all("We use AI and PR in this project."),
            "We use 人工智能 and 公关 in this project.",
        )

        # 3. 中英无缝混排（前后为中文字符）：必须正常替换
        self.assertEqual(
            auto.replace_all("这场AI发布会由PR部门负责。"),
            "这场人工智能发布会由公关部门负责。",
        )

    def test_r13_replace_all_latency_sla(self):
        """R13: 加入边界检查后，replace_all 单句耗时仍须远低于 0.05ms SLA。"""
        auto = AhoCorasickAutomaton()
        for i in range(500):
            auto.add_word(f"TERM{i}", f"术语{i}")
        auto.add_word("AI", "人工智能")
        auto.build()

        sentence = "In the spring rain, we discussed AI governance and TERM42 architecture."
        t0 = time.perf_counter_ns()
        for _ in range(1000):
            auto.replace_all(sentence)
        avg_ms = (time.perf_counter_ns() - t0) / 1000 / 1_000_000.0
        self.assertLess(avg_ms, 0.05, f"replace_all 平均耗时 {avg_ms:.4f}ms 超过 0.05ms SLA")

    def test_r12_configurable_token_pricing_constants(self):
        """R12: 暴露可配置的 INPUT_TOKEN_PRICE_PER_M 与 OUTPUT_TOKEN_PRICE_PER_M，默认值等价于 40 / 100。"""
        self.assertTrue(
            hasattr(qwen_translators, "INPUT_TOKEN_PRICE_PER_M"),
            "engines.qwen_translators 缺少 INPUT_TOKEN_PRICE_PER_M 常量",
        )
        self.assertTrue(
            hasattr(qwen_translators, "OUTPUT_TOKEN_PRICE_PER_M"),
            "engines.qwen_translators 缺少 OUTPUT_TOKEN_PRICE_PER_M 常量",
        )
        self.assertAlmostEqual(qwen_translators.INPUT_TOKEN_UNIT_PRICE, 0.00004, places=10)
        self.assertAlmostEqual(qwen_translators.OUTPUT_TOKEN_UNIT_PRICE, 0.0001, places=10)

    def test_r11_ttft_ms_tracked_from_speech_started_to_first_delta(self):
        """R11: 从 speech_started 到首个 response.text.delta 自动计算 ttft_ms，且保留原有 latency_ms。"""
        emitted = []
        eng = QwenLiveTranslate38Engine(mock_mode=True, emit_fn=lambda p: emitted.append(p))

        eng._on_ws_message(None, json.dumps({"type": "input_audio_buffer.speech_started"}))
        time.sleep(0.015)
        eng._on_ws_message(None, json.dumps({"type": "response.text.delta", "delta": "Hello"}))

        self.assertTrue(len(emitted) >= 1)
        last_payload = emitted[-1]
        self.assertIn("ttft_ms", last_payload, "输出 payload 缺少 ttft_ms 字段")
        self.assertGreaterEqual(last_payload["ttft_ms"], 10, "ttft_ms 应反映真实的首次增量延迟 (>=10ms)")
        self.assertIn("latency_ms", last_payload, "必须原样保留 latency_ms 字段")

    def test_r11_ttft_preserved_on_sentence_seal_and_multi_turn_reset(self):
        """R11 边界: 当句子被下一句 speech_started 提前封口(seal)时，封口包必须保留真实 ttft_ms，且下一句必须重置计算自身 ttft_ms。"""
        emitted = []
        eng = QwenLiveTranslate38Engine(mock_mode=True, emit_fn=lambda p: emitted.append(p))

        # Sentence 1: speech starts, delta arrives after 15ms
        eng._on_ws_message(None, json.dumps({"type": "input_audio_buffer.speech_started"}))
        time.sleep(0.015)
        eng._on_ws_message(None, json.dumps({"type": "response.text.delta", "delta": "First phrase"}))

        # Sentence 2 starts before response.done arrives for Sentence 1 -> seals Sentence 1
        eng._on_ws_message(None, json.dumps({"type": "input_audio_buffer.speech_started"}))

        # Look for sealed final payload of Sentence 1 (id="1", is_final=True)
        sealed_finals = [p for p in emitted if p.get("id") == "1" and p.get("is_final") is True]
        self.assertEqual(len(sealed_finals), 1, "未找到句子 1 的封口 final 包")
        self.assertGreaterEqual(
            sealed_finals[0]["ttft_ms"],
            10,
            f"封口 final 包的 ttft_ms ({sealed_finals[0]['ttft_ms']}) 严禁被归零",
        )

        # Sentence 2 delta arrives after 25ms
        time.sleep(0.025)
        eng._on_ws_message(None, json.dumps({"type": "response.text.delta", "delta": "Second phrase"}))
        sent2_deltas = [p for p in emitted if p.get("id") == "2" and p.get("target") == "Second phrase"]
        self.assertEqual(len(sent2_deltas), 1)
        self.assertGreaterEqual(
            sent2_deltas[0]["ttft_ms"],
            20,
            f"句子 2 的 ttft_ms ({sent2_deltas[0]['ttft_ms']}) 必须独立测量且 >=20ms",
        )

    def test_r11_ttft_fallback_to_last_audio_push_time_when_speech_started_absent(self):
        """R11 边界: 上游未发送 speech_started 时，若有音频推送 last_audio_push_time，应作为基准计算 ttft_ms 而非归零。"""
        emitted = []
        eng = QwenLiveTranslate38Engine(mock_mode=True, emit_fn=lambda p: emitted.append(p))
        eng.is_ready.set()

        # Audio frame pushed
        eng.send_audio_chunk(b"\x00" * 1600)
        time.sleep(0.02)
        eng._on_ws_message(None, json.dumps({"type": "response.text.delta", "delta": "Direct fallback"}))

        self.assertTrue(len(emitted) >= 1)
        last_payload = emitted[-1]
        self.assertGreaterEqual(
            last_payload["ttft_ms"],
            15,
            f"缺少 speech_started 时应基于音频推流时间估算真实 ttft_ms (实际={last_payload['ttft_ms']})",
        )

    def test_r11_ttft_calculated_on_direct_response_text_done(self):
        """R11 边界: 当模型直接通过 response.text.done 返回全量文本（无 intermediate delta）时，也应正确记录 ttft_ms。"""
        emitted = []
        eng = QwenLiveTranslate38Engine(mock_mode=True, emit_fn=lambda p: emitted.append(p))

        eng._on_ws_message(None, json.dumps({"type": "input_audio_buffer.speech_started"}))
        time.sleep(0.02)
        eng._on_ws_message(None, json.dumps({"type": "response.text.done", "text": "Batch result"}))

        self.assertTrue(len(emitted) >= 1)
        last_payload = emitted[-1]
        self.assertGreaterEqual(
            last_payload["ttft_ms"],
            15,
            f"通过 response.text.done 到达的首批文本应计入 ttft_ms (实际={last_payload['ttft_ms']})",
        )

    def test_r13_empty_pattern_graceful_handling(self):
        """R13 健壮性: AC 自动机输出空 pattern 时不应抛出 IndexError。"""
        auto = AhoCorasickAutomaton()
        auto.root.outputs = [("", "empty")]
        auto.build()
        result = auto.replace_all("Test empty pattern text")
        self.assertEqual(result, "Test empty pattern text")

    def test_r12_dynamic_token_pricing_env_updates(self):
        """R12 动态化: get_token_unit_prices() 支持运行时环境变量动态更新，且模块级常量保持初始值兼容。"""
        orig_in = os.environ.get("INPUT_TOKEN_PRICE_PER_M")
        orig_out = os.environ.get("OUTPUT_TOKEN_PRICE_PER_M")
        try:
            os.environ["INPUT_TOKEN_PRICE_PER_M"] = "20.0"
            os.environ["OUTPUT_TOKEN_PRICE_PER_M"] = "50.0"
            in_u, out_u = qwen_translators.get_token_unit_prices()
            self.assertAlmostEqual(in_u, 0.00002, places=10)
            self.assertAlmostEqual(out_u, 0.00005, places=10)
            # Module constants remain accessible
            self.assertAlmostEqual(qwen_translators.INPUT_TOKEN_UNIT_PRICE, 0.00004, places=10)
        finally:
            if orig_in is not None:
                os.environ["INPUT_TOKEN_PRICE_PER_M"] = orig_in
            else:
                os.environ.pop("INPUT_TOKEN_PRICE_PER_M", None)
            if orig_out is not None:
                os.environ["OUTPUT_TOKEN_PRICE_PER_M"] = orig_out
            else:
                os.environ.pop("OUTPUT_TOKEN_PRICE_PER_M", None)

    def test_engine_and_channel_simulation_ttft_parity(self):
        """仿真一致性: Gummy, Qwen 与 ChannelSession.emit_mock_sub 均对齐支持 ttft_ms 字段透传。"""
        from engines.qwen_translators import GummyZeroCopyEngine
        import server

        # Gummy simulate_event
        gummy = GummyZeroCopyEngine(mock_mode=True)
        p_gummy = gummy.simulate_event("hello", "你好", is_final=True, latency_ms=45, ttft_ms=18)
        self.assertIn("ttft_ms", p_gummy)
        self.assertEqual(p_gummy["ttft_ms"], 18)

        # Qwen simulate_event
        qwen = QwenLiveTranslate38Engine(mock_mode=True)
        p_qwen = qwen.simulate_event("world", "世界", is_final=True, latency_ms=40, ttft_ms=22)
        self.assertIn("ttft_ms", p_qwen)
        self.assertEqual(p_qwen["ttft_ms"], 22)

        # ChannelSession simulate_event
        ch = server.ChannelSession(name="en", channel_id="A", label="En", source_lang="zh", target_lang="en")
        p_ch = ch.simulate_event("test", "测试", is_final=True, latency_ms=30, ttft_ms=25)
        self.assertIn("ttft_ms", p_ch)
        self.assertEqual(p_ch["ttft_ms"], 25)


if __name__ == "__main__":
    unittest.main()
