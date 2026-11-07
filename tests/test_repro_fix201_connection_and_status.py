"""
【复现测试】FIX-201: 连接链路与故障可见性 (R2 / R14 / R5 / R6 / R8 / PERF)
- 修复前预期: 抛出 AssertionError / AttributeError，退出码 != 0 (3/3 稳定红灯)
- 修复后预期: 断言全部通过，退出码 == 0 (3/3 稳定绿灯)，终身保留于 tests/ 回归套件
"""

import json
import os
import sys
import threading
import time
import unittest
from unittest.mock import patch

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)
import glob as _glob
for _sp in _glob.glob(os.path.join(ROOT_DIR, ".venv", "lib", "python*", "site-packages")):
    if _sp not in sys.path:
        sys.path.insert(0, _sp)

import core.audio_pipeline as audio_pipeline
from core.audio_pipeline import FastAudioCaptureManager, FastAudioCaptureWorker
import engines.qwen_translators as qwen_translators
from engines.qwen_translators import GummyZeroCopyEngine, QwenLiveTranslate38Engine
import server


class _FakeStream:
    def __init__(self, should_fail: bool = False, pcm_frame: bytes = b"\x01\x00" * 800):
        self.should_fail = should_fail
        self.pcm_frame = pcm_frame
        self.closed = False

    def read(self, num_frames: int, exception_on_overflow: bool = False) -> bytes:
        if self.should_fail:
            raise OSError("Unplugged audio device")
        time.sleep(0.005)
        return self.pcm_frame

    def stop_stream(self) -> None:
        pass

    def close(self) -> None:
        self.closed = True


class _FakePyAudio:
    def __init__(self, devices_map: dict, default_index: int = 0, fail_indices: set = None):
        self.devices_map = dict(devices_map)
        self.default_index = default_index
        self.fail_indices = set(fail_indices or set())
        self.opened_indices = []
        self.terminated = False

    def get_device_count(self) -> int:
        return len(self.devices_map)

    def get_device_info_by_index(self, index: int) -> dict:
        if index not in self.devices_map:
            raise OSError(f"Invalid device index {index}")
        return dict(self.devices_map[index])

    def get_default_input_device_info(self) -> dict:
        return dict(self.devices_map[self.default_index])

    def open(self, format, channels, rate, input, input_device_index, frames_per_buffer):
        self.opened_indices.append(input_device_index)
        should_fail = input_device_index in self.fail_indices
        return _FakeStream(should_fail=should_fail)

    def terminate(self) -> None:
        self.terminated = True


class TestReproFix201ConnectionAndStatus(unittest.TestCase):
    # ------------------------------------------------------------------
    # Stage A: R2 & R14
    # ------------------------------------------------------------------
    def test_t_r2_1_env_example_no_private_maas(self):
        """T-R2-1: .env.example 中非注释行不含 maas.aliyuncs.com；全文不含 llm-0joa7mwnwelaxwgj"""
        env_example_path = os.path.join(ROOT_DIR, ".env.example")
        with open(env_example_path, "r", encoding="utf-8") as f:
            content = f.read()

        self.assertNotIn("llm-0joa7mwnwelaxwgj", content)
        for line in content.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            self.assertNotIn("maas.aliyuncs.com", stripped)

    def test_t_r2_2_switch_key_no_private_instance_id(self):
        """T-R2-2: switch_key.py 全文不含 llm-0joa7mwnwelaxwgj，且仍然同时包含 dashscope.aliyuncs.com 和 maas"""
        switch_key_path = os.path.join(ROOT_DIR, "switch_key.py")
        with open(switch_key_path, "r", encoding="utf-8") as f:
            content = f.read()

        self.assertNotIn("llm-0joa7mwnwelaxwgj", content)
        self.assertIn("dashscope.aliyuncs.com", content)
        self.assertIn("maas", content)

    def test_t_r2_3_resolve_ws_url_deterministic_routing(self):
        """T-R2-3: resolve_ws_url 按 Key 类型确定性路由"""
        self.assertTrue(hasattr(qwen_translators, "resolve_ws_url"), "缺少 resolve_ws_url 函数")
        resolve_ws_url = qwen_translators.resolve_ws_url

        maas_url = "wss://my-inst.cn-beijing.maas.aliyuncs.com/api-ws/v1/realtime?model=qwen3.5-livetranslate-flash-realtime"
        pub_url = "wss://dashscope.aliyuncs.com/api-ws/v1/realtime?model=qwen3.8-livetranslate-flash-realtime"

        # 普通公网 Key + maas URL -> 自动改走公网网关并保留 model 参数
        routed = resolve_ws_url(maas_url, "sk-abc123456")
        self.assertEqual(
            routed,
            "wss://dashscope.aliyuncs.com/api-ws/v1/realtime?model=qwen3.5-livetranslate-flash-realtime",
        )

        # sk-ws- 专属 Key + maas URL -> 原样返回
        self.assertEqual(resolve_ws_url(maas_url, "sk-ws-abc123456"), maas_url)

        # 公网 URL -> 原样返回
        self.assertEqual(resolve_ws_url(pub_url, "sk-abc123456"), pub_url)
        self.assertEqual(resolve_ws_url(pub_url, "sk-ws-abc123456"), pub_url)

    def test_t_r14_1_update_api_key_exits_forced_mock_and_starts_ws(self):
        """T-R14-1: 占位符 Key 启动进入 mock 后，调用 update_api_key 退出 mock 并启动 WS 线程"""
        ws_started = threading.Event()
        engine = QwenLiveTranslate38Engine(api_key="sk-your-dashscope-api-key-here")
        try:
            with patch.object(engine, "_run_ws", side_effect=lambda *a, **kw: ws_started.set()):
                engine.start()
                self.assertTrue(engine.mock_mode)
                self.assertTrue(hasattr(engine, "update_api_key"), "缺少 update_api_key 方法")
                engine.update_api_key("sk-test-validkey123456")
                self.assertFalse(engine.mock_mode)
                self.assertTrue(ws_started.wait(timeout=1.0), "update_api_key 后 WS 线程未启动")
        finally:
            engine.stop()

    def test_t_r14_2_explicit_mock_mode_preserved_on_update_api_key(self):
        """T-R14-2: 显式 mock_mode=True 构造的引擎，调用 update_api_key 后仍保持 mock_mode=True"""
        qwen_eng = QwenLiveTranslate38Engine(api_key="sk-real-key-123", mock_mode=True)
        gummy_eng = GummyZeroCopyEngine(api_key="sk-real-key-123", mock_mode=True)
        try:
            qwen_eng.start()
            gummy_eng.start()
            self.assertTrue(hasattr(qwen_eng, "update_api_key"), "Qwen 缺少 update_api_key")
            self.assertTrue(hasattr(gummy_eng, "update_api_key"), "Gummy 缺少 update_api_key")
            qwen_eng.update_api_key("sk-new-real-key-456")
            gummy_eng.update_api_key("sk-new-real-key-456")
            self.assertTrue(qwen_eng.mock_mode)
            self.assertTrue(gummy_eng.mock_mode)
        finally:
            qwen_eng.stop()
            gummy_eng.stop()

    def test_t_r14_3_channel_session_update_api_key_non_blocking(self):
        """T-R14-3: server.ChannelSession.update_api_key 调用耗时 < 50ms 且在后台重启激活引擎"""
        ch = server.ChannelSession("en_test", "A", "zh", "en", "测试通道")
        restarted = threading.Event()

        def slow_update(new_key: str):
            time.sleep(0.15)
            ch.qwen_engine.api_key = new_key
            restarted.set()

        with patch.object(ch.qwen_engine, "update_api_key", side_effect=slow_update, create=True):
            t0 = time.perf_counter()
            ch.update_api_key("sk-nonblocking-test-key")
            elapsed_ms = (time.perf_counter() - t0) * 1000.0

        self.assertLess(elapsed_ms, 50.0, f"update_api_key 阻塞耗时 {elapsed_ms:.2f}ms >= 50ms")
        self.assertTrue(restarted.wait(timeout=1.0), "ChannelSession.update_api_key 未在后台触发激活引擎重启")
        self.assertEqual(ch.gummy_engine.api_key, "sk-nonblocking-test-key")

    # ------------------------------------------------------------------
    # Stage B: R5 & R6
    # ------------------------------------------------------------------
    def test_t_r5_1_ws_error_401_auth_failed_and_dedup(self):
        """T-R5-1: status_code=401 -> auth_failed，且相同状态去重只回调 1 次"""
        engine = QwenLiveTranslate38Engine(api_key="sk-test-key", mock_mode=True)
        events = []
        engine.status_fn = lambda state, detail: events.append((state, detail))

        class FakeWsError(Exception):
            def __init__(self, status_code: int, msg: str = "Unauthorized"):
                super().__init__(msg)
                self.status_code = status_code

        engine._on_ws_error(None, FakeWsError(401, "HTTP 401 Unauthorized sk-test-key"))
        self.assertEqual(getattr(engine, "engine_state", None), "auth_failed")
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0][0], "auth_failed")
        self.assertNotIn("sk-test-key", events[0][1])

        # 再次传入相同状态错误 -> 去重不重复触发 status_fn
        engine._on_ws_error(None, FakeWsError(403, "HTTP 403 Forbidden"))
        self.assertEqual(len(events), 1)

    def test_t_r5_2_ws_error_classification_and_session_updated_ready(self):
        """T-R5-2: 429 -> rate_limited；普通异常 -> network_error；session.updated -> ready 且 _reconnect_attempt 归零"""
        engine = QwenLiveTranslate38Engine(api_key="sk-test-key", mock_mode=True)

        class FakeWsError(Exception):
            def __init__(self, status_code: int):
                super().__init__(f"HTTP {status_code}")
                self.status_code = status_code

        engine._on_ws_error(None, FakeWsError(429))
        self.assertEqual(getattr(engine, "engine_state", None), "rate_limited")

        engine._on_ws_error(None, Exception("boom"))
        self.assertEqual(getattr(engine, "engine_state", None), "network_error")

        engine._reconnect_attempt = 5
        engine._on_ws_message(None, '{"type":"session.updated"}')
        self.assertEqual(getattr(engine, "engine_state", None), "ready")
        self.assertEqual(getattr(engine, "_reconnect_attempt", None), 0)

    def test_t_r5_3_compute_reconnect_delay_bounds(self):
        """T-R5-3: compute_reconnect_delay(0) <= 0.5；任意 n <= 15.0"""
        self.assertTrue(
            hasattr(qwen_translators, "compute_reconnect_delay"),
            "缺少 compute_reconnect_delay 函数",
        )
        compute_reconnect_delay = qwen_translators.compute_reconnect_delay
        for _ in range(20):
            d0 = compute_reconnect_delay(0)
            self.assertGreaterEqual(d0, 0.0)
            self.assertLessEqual(d0, 0.5)
        for n in [1, 2, 5, 10, 50, 100]:
            dn = compute_reconnect_delay(n)
            self.assertGreaterEqual(dn, 0.0)
            self.assertLessEqual(dn, 15.0)

    def test_t_r6_1_get_meta_includes_api_key_configured_and_engine_status(self):
        """T-R6-1: server.get_meta() 包含 api_key_configured (bool) 和 engine_status (含 en, zh)"""
        resp = server.get_meta()
        data = json.loads(resp.body.decode("utf-8"))
        self.assertIn("api_key_configured", data)
        self.assertIsInstance(data["api_key_configured"], bool)
        self.assertIn("engine_status", data)
        self.assertIsInstance(data["engine_status"], dict)
        self.assertIn("en", data["engine_status"])
        self.assertIn("zh", data["engine_status"])

    def test_t_r6_2_float_ui_engine_status_before_subtitle_and_wait_prefix(self):
        """T-R6-2: float_ui.html 中 engine_status 判断在 scheduleSubtitleUpdate(data) 之前，且提示文案以 等待 开头"""
        float_ui_path = os.path.join(ROOT_DIR, "float_ui.html")
        with open(float_ui_path, "r", encoding="utf-8") as f:
            content = f.read()

        onmessage_idx = content.find("ws.onmessage")
        self.assertNotEqual(onmessage_idx, -1)
        sub_slice = content[onmessage_idx:]
        idx_engine_status = sub_slice.find("'engine_status'")
        if idx_engine_status == -1:
            idx_engine_status = sub_slice.find('"engine_status"')
        idx_schedule = sub_slice.find("scheduleSubtitleUpdate(data)")

        self.assertNotEqual(idx_engine_status, -1, "float_ui.html ws.onmessage 中未找到 engine_status 拦截")
        self.assertNotEqual(idx_schedule, -1)
        self.assertLess(
            idx_engine_status,
            idx_schedule,
            "engine_status 拦截必须出现在 scheduleSubtitleUpdate(data) 之前",
        )

        for expected_msg in [
            "等待 API Key：请点击 ⚙️ 填入阿里云百炼 API Key",
            "等待 Key 修正：API Key 无效或已欠费，请点击 ⚙️ 检查",
            "等待云端重连：网络中断，正在自动重试…",
            "等待限流恢复：请求过于频繁，正在自动重试…",
        ]:
            self.assertTrue(expected_msg.startswith("等待"))
            self.assertIn(expected_msg, content)

    def test_t_r6_3_index_html_has_engine_status_and_zero_inner_text(self):
        """T-R6-3: index.html 包含 engine_status，且 innerText 出现次数为 0"""
        index_path = os.path.join(ROOT_DIR, "index.html")
        with open(index_path, "r", encoding="utf-8") as f:
            content = f.read()

        self.assertIn("engine_status", content)
        self.assertEqual(content.count("innerText"), 0)

    # ------------------------------------------------------------------
    # Stage C: R8 & PERF
    # ------------------------------------------------------------------
    def test_t_r8_1_audio_worker_recovers_to_default_mic_after_consecutive_errors(self):
        """T-R8-1: 流持续抛 OSError 达到阈值后触发管理器恢复，切换到默认输入设备并继续推送帧"""
        devices = {
            0: {"index": 0, "name": "Built-in Microphone", "maxInputChannels": 1, "defaultSampleRate": 16000.0},
            1: {"index": 1, "name": "USB Headset Mic", "maxInputChannels": 1, "defaultSampleRate": 16000.0},
        }
        # 初始流在设备 1 上不断抛 OSError；默认设备 0 正常返回音频帧
        fake_pa = _FakePyAudio(devices_map=devices, default_index=0, fail_indices={1})
        received = []

        with patch.object(audio_pipeline.pyaudio, "PyAudio", side_effect=lambda: fake_pa):
            mgr = FastAudioCaptureManager()
            try:
                mgr.worker_a.set_device(1)
                self.assertEqual(mgr.worker_a.device_index, 1)
                mgr.worker_a.set_zero_copy_callback(lambda pcm: received.append(pcm))
                mgr.worker_a.start()

                deadline = time.time() + 1.5
                while time.time() < deadline:
                    if mgr.worker_a.device_index == 0 and len(received) >= 1:
                        break
                    time.sleep(0.02)

                self.assertEqual(mgr.worker_a.device_index, 0, "设备断开后未自动恢复到默认输入设备 0")
                self.assertGreaterEqual(len(received), 1, "恢复后未收到正常音频帧")
            finally:
                mgr.stop()

    def test_t_r8_2_channel_b_enters_safe_idle_when_no_loopback_on_recovery(self):
        """T-R8-2: 通道 B 在恢复过程中找不到 loopback 时进入 is_idle=True，绝不打开麦克风设备"""
        devices_only_mic = {
            0: {"index": 0, "name": "Built-in Microphone", "maxInputChannels": 1, "defaultSampleRate": 16000.0},
        }
        fake_pa = _FakePyAudio(devices_map=devices_only_mic, default_index=0, fail_indices=set())

        with patch.object(audio_pipeline.pyaudio, "PyAudio", side_effect=lambda: fake_pa):
            mgr = FastAudioCaptureManager()
            try:
                # 模拟原先通道 B 连接在虚拟声卡 (index=2) 上，随后该设备被移除且流持续抛 OSError
                mgr.worker_b.stream = _FakeStream(should_fail=True)
                mgr.worker_b.device_index = 2
                mgr.worker_b.is_idle = False
                fake_pa.opened_indices.clear()

                mgr.worker_b.start()
                deadline = time.time() + 1.5
                while time.time() < deadline:
                    if mgr.worker_b.is_idle:
                        break
                    time.sleep(0.02)

                self.assertTrue(mgr.worker_b.is_idle, "通道 B 在无 loopback 时未进入 is_idle=True")
                self.assertIsNone(mgr.worker_b.stream)
                # 确认恢复期间只打开了通道 A 的默认麦克风，通道 B 绝未打开麦克风作为自己的流
                self.assertIsNone(mgr.worker_b.device_index)
            finally:
                mgr.stop()

    def test_t_perf_process_frame_sla(self):
        """T-PERF: FastAudioCaptureWorker.process_frame 连续执行 1 万次 1600 字节帧，平均耗时 < 0.015ms"""
        worker = FastAudioCaptureWorker(channel_id="A", is_loopback_channel=False, enable_agc=True)
        try:
            frame = b"\x20\x01" * 800  # 1600 bytes
            # 预热
            for _ in range(200):
                worker.process_frame(frame)

            iters = 10000
            t0 = time.perf_counter()
            for _ in range(iters):
                worker.process_frame(frame)
            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            avg_ms = elapsed_ms / iters
            self.assertLess(avg_ms, 0.015, f"process_frame 平均耗时 {avg_ms:.6f}ms 超过 0.015ms SLA")
        finally:
            worker.terminate()


if __name__ == "__main__":
    unittest.main()
