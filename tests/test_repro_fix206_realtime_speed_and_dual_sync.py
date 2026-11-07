"""
【复现与回归测试套件】FIX-206: 会议级极速同传、Prompt 瘦身、长句主动切分、轮次状态机重构与双窗对称镜像
覆盖需求: R1 / R2 / R3 / R4 / R5
关联期望对齐卡: EXP-206-conference-realtime-speed-and-dual-sync.md

四大核心根因与验收套件:
1. TestCloudPromptAndAsyncAudioUplink (R1):
   - test_hotwords_cloud_sync_limit_48: 自动同步至云端 session.translation.corpus.phrases 限制 <= 48，本地 18,449 词全量保留。
   - test_config_frame_utf8_payload_under_2_5kb: 配置帧序列化采用 ensure_ascii=False，UTF-8 payload 体积严格 < 2500 字节 (2.5 KB)。
   - test_async_audio_uplink_queue_non_blocking: 音频上行解耦为有界无锁队列 (_tx_queue <= 64) 与独立后台线程，零阻塞 PyAudio 采样。

2. TestLongSentenceStreamingCommitAndGentleAGC (R2):
   - test_adaptive_far_field_agc_parameters: 验证远场温和 AGC 黄金参数 (noise_floor=240.0, max_gain=3.2, target_rms=1200.0, soft_knee=280.0)。
   - test_cloud_vad_turn_detection_parameters: 验证云端 VAD 判停参数 (threshold=0.45, prefix_padding_ms=180, silence_duration_ms=240)。
   - test_active_clause_commit_on_energy_dip_or_hard_limit: 连续语音满 2.4s 遇低谷 (RMS < 380) 或满 3.8s 硬上限时主动触发 commit。

3. TestStreamingTurnStateMachineAntiDrop (R3):
   - test_speech_started_pending_when_translation_in_flight: 译文流式生成中收到 speech_started 绝不提前清空或跳句，标记 pending 守护上下文。
   - test_response_text_delta_clean_turnover: 前一轮 finalize 后收到 response.text.delta 自动自增 sentence_id 并重置 target_text，开启新句意群流。

4. TestDualWindowSymmetricMirrorBridgeAndUI (R4):
   - test_symmetric_mirror_broadcast_payload_swap: channel_en 中译英广播至 /ws/en 同时向 /ws/zh 广播对调镜像帧 (target=source, source=target)。
   - test_channel_session_isolation_zero_mutation: 镜像广播严格发生在 WebSocket 广播层，严禁污染对端 ChannelSession 内部属性 (AC-13 门禁)。
   - test_same_language_echo_suppression: 抑制同语种逆向通道产生的无译文空回声帧，防止覆盖镜像双语字幕。
   - test_startup_subscription_race_grace_period: 消除双悬浮窗启动初期连接时差造成的首端音频丢失，同时维持单通道 50% 节流。
   - test_float_ui_zero_blank_source_streaming: float_ui.html 移除 !targetText 抹空 activeLine 缺陷，译文到达前即刻流式显示 sourceText。
"""

import array
import asyncio
import base64
import json
import os
import queue
import sys
import threading
import time
import unittest
from unittest.mock import MagicMock, patch

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import server
from core.audio_pipeline import AdaptiveFarFieldAGC
from engines.qwen_translators import QwenLiveTranslate38Engine


class TestCloudPromptAndAsyncAudioUplink(unittest.TestCase):
    """
    R1: 砍除云端 Prompt 膨胀与音频上行异步解耦
    - sync_hotwords 词条数下调为 limit=48（本地 18,449 词继续由 Aho-Corasick 纠错）
    - send_config / live_update_session 采用 ensure_ascii=False，体积 < 2.5 KB
    - send_audio_chunk 引入有界无锁队列与独立发送线程，零阻塞 PyAudio 采样
    """

    def setUp(self):
        server.channel_en.reset_stats()
        server.channel_zh.reset_stats()

    def test_hotwords_cloud_sync_limit_48(self):
        """
        Verify sync_hotwords limits cloud corpus phrases to <= 48,
        while local Aho-Corasick dictionary retains all 18,449 words.
        """
        # 1. 验证本地词库保留全量 18,449 词与 15 个词包
        bank_packs = getattr(server.glossary_mgr, "_bank_packs", {})
        self.assertEqual(
            len(bank_packs),
            15,
            f"Expected 15 bank packs loaded in GlossaryManager, got {len(bank_packs)}"
        )
        total_bank_terms = sum(
            len(p.get("asr_fixes", {}))
            + len(p.get("terms_zh_to_en", {}))
            + len(p.get("terms_en_to_zh", {}))
            for p in bank_packs.values()
        )
        self.assertGreaterEqual(
            total_bank_terms,
            18449,
            f"Local dictionary must retain all >= 18449 terms, got {total_bank_terms}"
        )

        # 2. 验证云端同步限制在 <= 48 词以内
        channel = server.channel_en
        channel.sync_hotwords()

        last_config = getattr(channel.qwen_engine, "last_sent_config", None)
        self.assertIsNotNone(
            last_config,
            "channel.qwen_engine.last_sent_config must be recorded after sync_hotwords"
        )
        phrases = (
            last_config.get("session", {})
            .get("translation", {})
            .get("corpus", {})
            .get("phrases", {})
        )
        self.assertGreater(
            len(phrases),
            0,
            "Cloud corpus phrases should not be empty after sync_hotwords"
        )
        self.assertLessEqual(
            len(phrases),
            48,
            f"Cloud corpus phrases must be <= 48 (got {len(phrases)}), down from 900 to prevent prompt bloat"
        )

    def test_config_frame_utf8_payload_under_2_5kb(self):
        """
        Verify config frame serialized with ensure_ascii=False has payload size < 2500 bytes (2.5 KB).
        """
        engine = QwenLiveTranslate38Engine(target_lang="en", mock_mode=False)
        fake_ws = MagicMock()
        fake_sock = MagicMock()
        fake_sock.connected = True
        fake_ws.sock = fake_sock
        engine.ws_client = fake_ws

        # 同步生成精简词条（<= 48 条）
        server.channel_en.sync_hotwords()
        last_config = getattr(server.channel_en.qwen_engine, "last_sent_config", {})
        corpus_phrases = (
            last_config.get("session", {})
            .get("translation", {})
            .get("corpus", {})
            .get("phrases", {})
        )

        # 模拟包含中文专业术语的词库
        if not corpus_phrases:
            corpus_phrases = {
                "人工智能": "Artificial Intelligence",
                "大语言模型": "Large Language Model",
                "同声传译": "Simultaneous Interpretation",
            }

        engine.live_update_session(target_lang="en", corpus_phrases=corpus_phrases)

        self.assertTrue(fake_ws.send.called, "ws_client.send must be called with serialized config")
        sent_str = fake_ws.send.call_args[0][0]

        # 验证必须采用 ensure_ascii=False：中文绝不被转义成 \\uXXXX 形式
        self.assertNotIn(
            "\\u",
            sent_str,
            "Config frame must use ensure_ascii=False (no \\uXXXX escape sequences) to save 60% bandwidth"
        )

        # 验证 UTF-8 编码体积严格 < 2500 字节 (2.5 KB)
        payload_bytes = sent_str.encode("utf-8")
        self.assertLess(
            len(payload_bytes),
            2500,
            f"Serialized config payload must be < 2500 bytes (2.5 KB), got {len(payload_bytes)} bytes"
        )

    def test_async_audio_uplink_queue_non_blocking(self):
        """
        Verify send_audio_chunk pushes to bounded queue without blocking the caller thread.
        """
        engine = QwenLiveTranslate38Engine(target_lang="en", mock_mode=False)
        fake_ws = MagicMock()
        fake_sock = MagicMock()
        fake_sock.connected = True
        fake_ws.sock = fake_sock
        engine.ws_client = fake_ws
        engine.is_ready.set()

        # 1. 验证存在有界队列属性 (queue.Queue(maxsize=64))
        self.assertTrue(
            hasattr(engine, "_tx_queue"),
            "Engine must have _tx_queue for asynchronous decoupled audio transmission"
        )
        self.assertIsInstance(
            engine._tx_queue,
            queue.Queue,
            "_tx_queue must be an instance of queue.Queue"
        )
        self.assertLessEqual(
            engine._tx_queue.maxsize,
            64,
            "_tx_queue must be bounded with maxsize <= 64 to prevent unbounded memory growth"
        )

        # 2. 模拟网络端阻塞 50ms，验证主线程入队耗时严格 < 10ms，零阻塞 PyAudio
        def blocking_send(msg):
            time.sleep(0.05)

        fake_ws.send.side_effect = blocking_send
        dummy_pcm = b"\x00\x00" * 800  # 50ms PCM frame

        t0 = time.perf_counter()
        engine.send_audio_chunk(dummy_pcm)
        duration_ms = (time.perf_counter() - t0) * 1000.0

        self.assertLess(
            duration_ms,
            10.0,
            f"send_audio_chunk must return in < 10ms without blocking caller thread, took {duration_ms:.2f}ms"
        )


class TestLongSentenceStreamingCommitAndGentleAGC(unittest.TestCase):
    """
    R2: 100 字长句主动意群流式切分与温和 AGC
    - AdaptiveFarFieldAGC 调整为 noise_floor=240.0, max_gain=3.2, target_rms=1200.0, soft_knee=280.0
    - turn_detection 调整为 threshold=0.45, prefix_padding_ms=180, silence_duration_ms=240
    - send_audio_chunk 统计连续语音时长，满 2.4s 遇微能量低谷 (RMS < 380) 或满 3.8s 硬上限主动 commit
    """

    def test_adaptive_far_field_agc_parameters(self):
        """
        Verify AdaptiveFarFieldAGC parameters (noise_floor=240.0, max_gain=3.2, target_rms=1200.0, soft_knee=280.0).
        """
        agc = AdaptiveFarFieldAGC()
        self.assertEqual(
            agc.noise_floor,
            240.0,
            f"noise_floor must be tuned to 240.0 to prevent amplifying breathing noise, got {agc.noise_floor}"
        )
        self.assertEqual(
            agc.max_gain,
            3.2,
            f"max_gain must be tuned to 3.2, got {agc.max_gain}"
        )
        self.assertEqual(
            agc.target_rms,
            1200.0,
            f"target_rms must be tuned to 1200.0, got {agc.target_rms}"
        )
        self.assertEqual(
            agc.soft_knee,
            280.0,
            f"soft_knee must be tuned to 280.0, got {agc.soft_knee}"
        )
        # 核心物理约束：soft_knee 必须严格大于 noise_floor，防止增益计算出现负数
        self.assertGreater(
            agc.soft_knee,
            agc.noise_floor,
            "soft_knee must be strictly greater than noise_floor (280.0 > 240.0)"
        )

    def test_cloud_vad_turn_detection_parameters(self):
        """
        Verify turn_detection uses threshold=0.45, prefix_padding_ms=180, silence_duration_ms=240.
        """
        engine = QwenLiveTranslate38Engine(target_lang="en", mock_mode=True)
        engine.live_update_session(target_lang="en")

        last_config = getattr(engine, "last_sent_config", None)
        self.assertIsNotNone(last_config, "last_sent_config must be recorded on engine")
        turn_detection = (
            last_config.get("session", {})
            .get("turn_detection", {})
        )
        self.assertEqual(
            turn_detection.get("type"),
            "server_vad",
            f"turn_detection type must be server_vad, got {turn_detection.get('type')}"
        )
        self.assertEqual(
            turn_detection.get("threshold"),
            0.45,
            f"turn_detection threshold must be 0.45, got {turn_detection.get('threshold')}"
        )
        self.assertEqual(
            turn_detection.get("prefix_padding_ms"),
            180,
            f"turn_detection prefix_padding_ms must be 180, got {turn_detection.get('prefix_padding_ms')}"
        )
        self.assertEqual(
            turn_detection.get("silence_duration_ms"),
            240,
            f"turn_detection silence_duration_ms must be 240, got {turn_detection.get('silence_duration_ms')}"
        )

    def test_active_clause_commit_on_energy_dip_or_hard_limit(self):
        """
        Feed audio stream and verify {"type": "input_audio_buffer.commit"} is generated
        when speech duration >= 2.4s and RMS < 380, OR when continuous speech hits 3.8s hard cap.
        Explicitly verifies BOTH production 50ms chunks (1600 bytes) and 100ms chunks (3200 bytes).
        """
        engine = QwenLiveTranslate38Engine(target_lang="en", mock_mode=False)
        fake_ws = MagicMock()
        fake_sock = MagicMock()
        fake_sock.connected = True
        fake_ws.sock = fake_sock
        engine.ws_client = fake_ws
        engine.is_ready.set()

        configs = [
            {
                "desc": "production 50ms chunks (800 samples = 1600 bytes)",
                "samples": 800,
                "dip_chunks": 48,   # 48 * 0.05s = 2.4s
                "hard_chunks_sub_limit": 75, # 75 * 0.05s = 3.75s (< 3.79s)
                "hard_chunks": 76,  # 76 * 0.05s = 3.80s (>= 3.79s)
            },
            {
                "desc": "100ms chunks (1600 samples = 3200 bytes)",
                "samples": 1600,
                "dip_chunks": 24,   # 24 * 0.10s = 2.4s
                "hard_chunks_sub_limit": 37, # 37 * 0.10s = 3.70s (< 3.79s)
                "hard_chunks": 38,  # 38 * 0.10s = 3.80s (>= 3.79s)
            },
        ]

        def extract_sent_types():
            types = []
            for call in fake_ws.send.call_args_list:
                arg = call[0][0]
                try:
                    p = json.loads(arg)
                    types.append(p.get("type"))
                except Exception:
                    pass
            return types

        for cfg in configs:
            with self.subTest(chunk_config=cfg["desc"]):
                high_energy_chunk = array.array("h", [1200] * cfg["samples"]).tobytes()
                low_energy_chunk = array.array("h", [150] * cfg["samples"]).tobytes()

                # 场景 A: 满 2.4 秒遇到微能量低谷主动触发 Soft Commit
                fake_ws.send.reset_mock()
                with engine.lock:
                    engine._uncommitted_speech_chunks = 0
                    engine._continuous_speech_sec = 0.0

                for _ in range(cfg["dip_chunks"]):
                    engine.send_audio_chunk(high_energy_chunk)

                time.sleep(0.02)
                sent_types_before = extract_sent_types()
                self.assertNotIn(
                    "input_audio_buffer.commit",
                    sent_types_before,
                    f"[{cfg['desc']}] Should not commit before energy dip or hard cap is reached"
                )

                # 喂入 1 块低能量微停顿音频 (RMS < 380)
                engine.send_audio_chunk(low_energy_chunk)
                time.sleep(0.02)

                sent_types_after = extract_sent_types()
                self.assertIn(
                    "input_audio_buffer.commit",
                    sent_types_after,
                    f"[{cfg['desc']}] Must send input_audio_buffer.commit when speech >= 2.4s encounters energy dip (RMS < 380)"
                )

                # 场景 B: 连续 3.8 秒无换气停顿强制触发 Hard Commit
                fake_ws.send.reset_mock()
                with engine.lock:
                    engine._uncommitted_speech_chunks = 0
                    engine._continuous_speech_sec = 0.0

                # 喂入未达 3.8s 的音频，确保不发生过早提交 (例如 50ms 在 1.9s / 38 块时不早触)
                for _ in range(cfg["hard_chunks_sub_limit"]):
                    engine.send_audio_chunk(high_energy_chunk)

                time.sleep(0.02)
                sent_types_sub = extract_sent_types()
                self.assertNotIn(
                    "input_audio_buffer.commit",
                    sent_types_sub,
                    f"[{cfg['desc']}] Must not prematurely commit before 3.8s hard cap"
                )

                # 喂入达到 3.8s 的最后音频
                for _ in range(cfg["hard_chunks"] - cfg["hard_chunks_sub_limit"]):
                    engine.send_audio_chunk(high_energy_chunk)

                time.sleep(0.02)
                sent_types_hard = extract_sent_types()
                self.assertIn(
                    "input_audio_buffer.commit",
                    sent_types_hard,
                    f"[{cfg['desc']}] Must force input_audio_buffer.commit when continuous speech hits 3.8s hard cap"
                )


class TestStreamingTurnStateMachineAntiDrop(unittest.TestCase):
    """
    R3: 重构流式轮次状态机
    - speech_started 到达时若当前句译文仍在云端流式生成中，绝不清空 source/target 或强行跳 sentence_id，标记 pending
    - response.text.delta 到达时若上一轮已 finalize，自动自增 sentence_id 并重置 target_text，开启新句意群流
    """

    def test_speech_started_pending_when_translation_in_flight(self):
        """
        When speech_started arrives during active translation, verify source_text/target_text
        are not prematurely wiped and sentence_id does not jump ahead prematurely.
        """
        engine = QwenLiveTranslate38Engine(target_lang="en", mock_mode=True)

        # 句 1: 正在流式生成中，收到 ASR 原文与部分 MT 译文
        engine.sentence_id = 1
        engine.source_text = "中国经济发展进入新阶段"
        engine.target_text = "China's economic development has entered a new stage"
        engine.is_sentence_finalized = False
        engine.has_active_response = True

        # 注入 speech_started 事件（发言人换气或开始下一意群）
        speech_started_event = {"type": "input_audio_buffer.speech_started"}
        engine._on_ws_message(None, json.dumps(speech_started_event))

        # 断言：当前句译文在途时，绝不提前跳句或清空文本
        self.assertEqual(
            engine.sentence_id,
            1,
            f"sentence_id must remain 1 while translation is in-flight, got {engine.sentence_id}"
        )
        self.assertEqual(
            engine.source_text,
            "中国经济发展进入新阶段",
            "source_text must not be wiped when speech_started arrives during active translation"
        )
        self.assertEqual(
            engine.target_text,
            "China's economic development has entered a new stage",
            "target_text must not be wiped when speech_started arrives during active translation"
        )
        self.assertFalse(
            engine.is_sentence_finalized,
            "is_sentence_finalized must not be prematurely set before response.done"
        )
        self.assertTrue(
            getattr(engine, "_pending_speech_turn", False),
            "_pending_speech_turn flag must be set to defer new turn initialization until response.done"
        )

        # 迟到的句 1 response.done 到达
        response_done_event = {
            "type": "response.done",
            "response": {"usage": {"input_tokens": 12, "output_tokens": 15}},
        }
        engine._on_ws_message(None, json.dumps(response_done_event))

        # 封口后状态标记为 finalized，并重置 pending 标志
        self.assertTrue(
            engine.is_sentence_finalized,
            "Sentence 1 must be finalized upon response.done"
        )
        self.assertFalse(
            getattr(engine, "_pending_speech_turn", False),
            "_pending_speech_turn flag must be reset after response.done"
        )

    def test_response_text_delta_clean_turnover(self):
        """
        Verify that upon response.text.delta following a finalized turn,
        sentence_id increments cleanly and opens a new clause stream without concatenating into the old sentence.
        """
        engine = QwenLiveTranslate38Engine(target_lang="en", mock_mode=True)

        # 句 1 已定稿封口
        engine.sentence_id = 1
        engine.source_text = "这是第一个完整句子。"
        engine.target_text = "This is the first complete sentence."
        engine.is_sentence_finalized = True

        # 下一意群或下一句的 response.text.delta 到达
        new_delta_event = {
            "type": "response.text.delta",
            "delta": "This is a new clause.",
        }
        engine._on_ws_message(None, json.dumps(new_delta_event))

        # 断言：自动自增 sentence_id，重置 target_text，绝不与旧句拼接
        self.assertEqual(
            engine.sentence_id,
            2,
            f"sentence_id must auto-increment to 2 on new response.text.delta after finalization, got {engine.sentence_id}"
        )
        self.assertEqual(
            engine.target_text,
            "This is a new clause.",
            f"target_text must contain only the new clause without concatenating old sentence, got '{engine.target_text}'"
        )
        self.assertFalse(
            engine.is_sentence_finalized,
            "is_sentence_finalized must be False for active streaming clause"
        )
        self.assertNotIn(
            "This is the first complete sentence.",
            engine.target_text,
            "Old finalized sentence text must NOT leak into the new sentence target_text"
        )


class TestDualWindowSymmetricMirrorBridgeAndUI(unittest.TestCase):
    """
    R4: 双悬浮窗双语对称广播桥与前端零空白兜底
    - server.py:_on_engine_emit 双语对称镜像广播 (channel_en 镜像至 /ws/zh, channel_zh 镜像至 /ws/en)
    - 严格保持通道对象隔离，绝不修改对端 ChannelSession Python 属性 (保持 tests/audit_gate.py:742-754 绿灯)
    - 抑制同语种逆向通道产生的无译文空回声帧
    - is_channel_subscribed 消除启动初期连接竞态
    - float_ui.html 移除 !targetText 抹空 activeLine 缺陷，0.2 秒即刻出字零黑屏
    """

    def setUp(self):
        server.channel_en.reset_stats()
        server.channel_zh.reset_stats()
        server.connected_clients["en"].clear()
        server.connected_clients["zh"].clear()

        # 启动测试事件循环并赋给 server.main_loop
        self.loop = asyncio.new_event_loop()
        self.loop_thread = threading.Thread(target=self.loop.run_forever, daemon=True)
        self.loop_thread.start()
        server.main_loop = self.loop

    def tearDown(self):
        time.sleep(0.05)
        if self.loop.is_running():
            self.loop.call_soon_threadsafe(self.loop.stop)
            self.loop_thread.join(timeout=1.0)
        self.loop.close()
        server.main_loop = None
        server.channel_en.reset_stats()
        server.channel_zh.reset_stats()
        server.connected_clients["en"].clear()
        server.connected_clients["zh"].clear()

    def test_symmetric_mirror_broadcast_payload_swap(self):
        """
        Verify that channel_en emitting zh->en broadcasts to /ws/en
        and broadcasts mirrored frame (target=source, source=target) to /ws/zh.
        """
        broadcast_calls = []

        async def fake_broadcast(channel, payload):
            broadcast_calls.append((channel, payload))

        # 测试 A: channel_en (中译英) 产生翻译
        with patch("server.broadcast_to_channel", side_effect=fake_broadcast):
            server.channel_en.dispatch(
                sentence_id=101,
                source="欢迎各位来宾",
                target="Welcome all distinguished guests",
                is_final=True,
                latency_ms=80,
                ttft_ms=30,
            )
            time.sleep(0.05)

        # 验证广播至 /ws/en
        en_calls = [p for ch, p in broadcast_calls if ch == "en"]
        self.assertGreater(len(en_calls), 0, "Must broadcast to /ws/en")
        en_payload = en_calls[0]
        self.assertEqual(en_payload.get("source"), "欢迎各位来宾")
        self.assertEqual(en_payload.get("target"), "Welcome all distinguished guests")

        # 验证对称镜像广播至 /ws/zh
        zh_calls = [p for ch, p in broadcast_calls if ch == "zh"]
        self.assertGreater(
            len(zh_calls),
            0,
            "Must broadcast mirrored frame to /ws/zh for symmetric dual-window display"
        )
        zh_payload = zh_calls[0]
        # 中文窗口中：原中文作为 target (大字体主显)，英文译文作为 source (副字体对照)
        self.assertEqual(
            zh_payload.get("target"),
            "欢迎各位来宾",
            "Mirrored frame on /ws/zh must have original Chinese as target (primary HUD display)"
        )
        self.assertEqual(
            zh_payload.get("source"),
            "Welcome all distinguished guests",
            "Mirrored frame on /ws/zh must have English translation as source (secondary subtitle display)"
        )
        self.assertEqual(zh_payload.get("is_final"), True)

        # 测试 B: channel_zh (英译中) 产生翻译对称镜像至 /ws/en
        broadcast_calls.clear()
        with patch("server.broadcast_to_channel", side_effect=fake_broadcast):
            server.channel_zh.dispatch(
                sentence_id=201,
                source="Thank you very much",
                target="非常感谢大家",
                is_final=True,
                latency_ms=90,
                ttft_ms=35,
            )
            time.sleep(0.05)

        zh_direct = [p for ch, p in broadcast_calls if ch == "zh"]
        self.assertGreater(len(zh_direct), 0, "Must broadcast to /ws/zh")
        self.assertEqual(zh_direct[0].get("target"), "非常感谢大家")
        self.assertEqual(zh_direct[0].get("source"), "Thank you very much")

        en_mirror = [p for ch, p in broadcast_calls if ch == "en"]
        self.assertGreater(len(en_mirror), 0, "Must broadcast mirrored frame to /ws/en")
        self.assertEqual(
            en_mirror[0].get("target"),
            "Thank you very much",
            "Mirrored frame on /ws/en must have English original as target (primary HUD display)"
        )
        self.assertEqual(
            en_mirror[0].get("source"),
            "非常感谢大家",
            "Mirrored frame on /ws/en must have Chinese translation as source (secondary subtitle display)"
        )

    def test_channel_session_isolation_zero_mutation(self):
        """
        Verify strictly NO mutation of peer ChannelSession Python attributes
        (preserving AC-13 in tests/audit_gate.py:742-754).
        """
        server.channel_en.reset_stats()
        server.channel_zh.reset_stats()

        # Channel EN 发生事件
        server.channel_en.simulate_event("中文提问", "English question", is_final=True, sentence_id=501)

        # Channel EN 属性更新
        self.assertEqual(server.channel_en.sentence_id, 501)
        self.assertEqual(server.channel_en.source_text, "中文提问")
        self.assertEqual(server.channel_en.target_text, "English question")

        # 严格隔离检验：Channel ZH 实例属性绝不被污染
        self.assertEqual(server.channel_zh.sentence_id, 0, "Channel B contaminated by Channel A!")
        self.assertEqual(server.channel_zh.source_text, "", "Channel B source contaminated!")
        self.assertEqual(server.channel_zh.target_text, "", "Channel B target contaminated!")

        # Channel ZH 发生事件
        server.channel_zh.simulate_event("English answer", "中文回答", is_final=True, sentence_id=601)

        # Channel ZH 属性更新
        self.assertEqual(server.channel_zh.sentence_id, 601)
        self.assertEqual(server.channel_zh.source_text, "English answer")
        self.assertEqual(server.channel_zh.target_text, "中文回答")

        # 严格隔离检验：Channel EN 保持不变
        self.assertEqual(server.channel_en.sentence_id, 501)
        self.assertEqual(server.channel_en.source_text, "中文提问")

    def test_same_language_echo_suppression(self):
        """
        Verify untranslated reverse-channel echo frames are suppressed.
        When speaker speaks Chinese, channel_zh (en->zh) hears Chinese due to mic multiplexing
        and emits un-translated frame (target=""). This empty frame must be suppressed from broadcast.
        """
        broadcast_calls = []

        async def fake_broadcast(channel, payload):
            broadcast_calls.append((channel, payload))

        with patch("server.broadcast_to_channel", side_effect=fake_broadcast):
            # 模拟 channel_zh 收到单麦克风复用推入的中文语音，未能翻译导致 target 为空
            server.channel_zh.dispatch(
                sentence_id=1,
                source="欢迎各位来宾参加会议",
                target="",
                is_final=False,
            )
            time.sleep(0.05)

        # 必须抑制同语种逆向空回声帧的广播，防止冲掉对称镜像字幕
        self.assertEqual(
            len(broadcast_calls),
            0,
            f"Untranslated reverse-channel echo frame must be suppressed from broadcast, but got {len(broadcast_calls)} calls"
        )

    def test_startup_subscription_race_grace_period(self):
        """
        Verify startup connection grace period in is_channel_subscribed.
        When dual floating windows launch, win_en connects first. During the startup window,
        is_channel_subscribed('zh') must return True rather than dropping audio immediately.
        """
        mock_ws_en = MagicMock()
        server.connected_clients["en"].clear()
        server.connected_clients["zh"].clear()

        # 模拟真实客户端连接到达 /ws/en
        server.connected_clients["en"].add(mock_ws_en)
        if hasattr(server, "_client_first_connected_at"):
            server._client_first_connected_at = time.time()

        # 1. 验证在启动平滑窗口期内 (5.0s)，zh 通道防漏音保护开启，返回 True
        self.assertTrue(
            server.is_channel_subscribed("zh"),
            "is_channel_subscribed('zh') must return True during startup grace period to prevent dropping audio for win_zh"
        )

        # 2. 模拟平滑窗口期过期后 (例如经过 10 秒)，若 zh 仍未连接，按原逻辑节流返回 False
        if hasattr(server, "_client_first_connected_at"):
            server._client_first_connected_at = time.time() - 10.0
            self.assertFalse(
                server.is_channel_subscribed("zh"),
                "is_channel_subscribed('zh') must return False after grace period when only 'en' is connected (50% cost saving)"
            )

    def test_float_ui_zero_blank_source_streaming(self):
        """
        Verify float_ui.html does not clear #activeLine when target text is empty during streaming.
        """
        float_ui_path = os.path.join(PROJECT_ROOT, "float_ui.html")
        self.assertTrue(os.path.exists(float_ui_path), "float_ui.html must exist")

        with open(float_ui_path, "r", encoding="utf-8") as f:
            html_content = f.read()

        # 1. 验证彻底移除导致黑屏的 activeLine.textContent = '' 清空逻辑
        self.assertNotIn(
            "if (sourceText && !targetText && !sentenceHasTranslation) {\n                    activeLine.textContent = '';",
            html_content,
            "float_ui.html must NOT wipe activeLine.textContent to '' when targetText is empty during streaming"
        )

        # 2. 验证前端遵循安全规范：严禁引入 innerText，必须全量使用 textContent (AC-14)
        self.assertNotIn(
            ".innerText",
            html_content,
            "float_ui.html must strictly avoid .innerText (use .textContent only for DOM safety and AC-14 compliance)"
        )


if __name__ == "__main__":
    unittest.main()
