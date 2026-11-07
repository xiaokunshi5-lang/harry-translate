"""
【复现与回归测试】FIX-205: WebSocket 握手净化、错误自愈降级、SSL 与网关回退、热词同步修正及 macOS WebKit 废弃警告消除
覆盖需求: R1 (R1.1, R1.2, R1.3) / R2 / R3 / R4
验收标准:
  - Case 1: _on_ws_open 握手网络帧不含空译文 ""，且收到云端非鉴权/非限流参数 error 时自动补发无 corpus 的 session.update 自愈进入 ready
  - Case 2: _run_ws 传递 sslopt={"cert_reqs": ssl.CERT_NONE} 且私有 maas.aliyuncs.com 连接失败自动回退 dashscope.aliyuncs.com
  - Case 3: HUDWebKitHost 拦截 setValue_forKey_('drawsTransparentBackground') 重定向至 'drawsBackground'=False，终端零废弃调用警告且透明生效
  - Case 4: ChannelSession.sync_hotwords() 默认初始化时不将 239 个无译文 asr_fixes 作为显式热词注入 qwen_engine.hotwords
"""

import json
import os
import ssl
import sys
import time
import unittest
from unittest.mock import MagicMock, patch

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import engines.qwen_translators as qwen_translators
from engines.qwen_translators import QwenLiveTranslate38Engine
import server


class TestReproFix205WSHandshakeAndWebKit(unittest.TestCase):
    tier = 1
    feature_id = 7
    milestone = "M2"

    # =========================================================================
    # Case 1: _on_ws_open 握手网络帧净化 与 参数级 error 自动补发自愈
    # =========================================================================
    def test_case1a_on_ws_open_network_frame_excludes_empty_translations(self):
        """Case 1A: _on_ws_open 发送的 WebSocket 网络帧必须过滤掉空译文串 ""，不得向云端发送畸形空值"""
        qwen = QwenLiveTranslate38Engine(target_lang="en", mock_mode=False)
        fake_ws = MagicMock()
        fake_sock = MagicMock()
        fake_sock.connected = True
        fake_ws.sock = fake_sock
        qwen.ws_client = fake_ws

        # 模拟包含空译文的热词输入（如 asr_fixes 或未提供翻译的词）
        qwen.hotwords = ["大模型", "思维链:Chain of Thought", "单抗"]
        qwen.corpus_phrases = {"大模型": "", "思维链": "Chain of Thought", "单抗": ""}

        qwen._on_ws_open(fake_ws)

        # 1. 验证已向底层 websocket 发送数据
        fake_ws.send.assert_called_once()
        sent_str = fake_ws.send.call_args[0][0]
        sent_payload = json.loads(sent_str)

        # 2. 检查网络发送帧中的 phrases 绝不包含空字符串 ""
        phrases = (
            sent_payload.get("session", {})
            .get("translation", {})
            .get("corpus", {})
            .get("phrases", {})
        )
        for term, trans in phrases.items():
            self.assertTrue(
                bool(trans and str(trans).strip()),
                f"Network frame must not contain empty translation for {term!r}: got {trans!r}",
            )

        # 3. 验证与 FIX-204 历史测试契约兼容：last_sent_config 结构保留
        self.assertIsNotNone(qwen.last_sent_config)
        self.assertIn("translation", qwen.last_sent_config["session"])

    def test_case1b_parameter_error_auto_recovery_without_corpus(self):
        """Case 1B: 收到云端参数级 error（非鉴权/非限流）时，绝不误报 network_error，而是自动补发无 corpus 的 session.update 自愈进入 ready"""
        qwen = QwenLiveTranslate38Engine(target_lang="en", mock_mode=False)
        fake_ws = MagicMock()
        fake_sock = MagicMock()
        fake_sock.connected = True
        fake_ws.sock = fake_sock
        qwen.ws_client = fake_ws
        qwen._set_state("connecting")
        qwen.is_ready.clear()

        # 模拟云端返回参数级错误帧（如 InvalidParameter: phrases invalid）
        err_frame = json.dumps({
            "type": "error",
            "error": {
                "code": "InvalidParameter",
                "message": "The phrases parameter in session.update contains invalid values",
            }
        })

        qwen._on_ws_message(fake_ws, err_frame)

        # 1. 断言绝不得将非鉴权/非限流参数报错误判为 network_error
        self.assertNotEqual(
            qwen.engine_state,
            "network_error",
            "Parameter-level error must NOT be classified as network_error (would hang HUD)",
        )

        # 2. 断言已自动在当前连接上补发降级自愈帧（无 corpus 的 session.update）
        fake_ws.send.assert_called()
        last_sent_raw = fake_ws.send.call_args[0][0]
        last_sent = json.loads(last_sent_raw)
        self.assertEqual(last_sent.get("type"), "session.update")
        trans_obj = last_sent.get("session", {}).get("translation", {})
        self.assertNotIn(
            "corpus",
            trans_obj,
            "Auto-recovery frame must strip corpus to guarantee cloud acceptance",
        )

        # 3. 断言引擎自愈进入 ready 状态
        self.assertTrue(qwen.is_ready.is_set(), "Engine must be ready after parameter-level auto-recovery")
        self.assertEqual(qwen.engine_state, "ready")

    # =========================================================================
    # Case 2: _run_ws sslopt CERT_NONE 注入 与 私有 MaaS 自动回退 DashScope
    # =========================================================================
    def test_case2a_run_ws_sslopt_injection(self):
        """Case 2A: _run_ws 在调用 ws_client.run_forever 时必须注入 sslopt={"cert_reqs": ssl.CERT_NONE}"""
        qwen = QwenLiveTranslate38Engine(api_key="sk-test-validkey123")
        qwen.is_running = True

        recorded_kwargs = {}

        class MockWebSocketApp:
            def __init__(self, *args, **kwargs):
                pass

            def run_forever(self, **kwargs):
                recorded_kwargs.update(kwargs)
                qwen.is_running = False

        with patch("engines.qwen_translators.websocket.WebSocketApp", MockWebSocketApp):
            qwen._run_ws()

        self.assertIn("sslopt", recorded_kwargs, "run_forever must be called with sslopt")
        self.assertEqual(
            recorded_kwargs["sslopt"],
            {"cert_reqs": ssl.CERT_NONE},
            "sslopt must specify cert_reqs=ssl.CERT_NONE for macOS/Win certificate resilience",
        )

    def test_case2b_private_maas_reconnect_fallback_to_public_dashscope(self):
        """Case 2B: 当私有 maas.aliyuncs.com 域名连接失败时，下一次重连必须自动回退至公网 dashscope.aliyuncs.com"""
        maas_url = "wss://my-inst.cn-beijing.maas.aliyuncs.com/api-ws/v1/realtime?model=qwen3.8-livetranslate-flash-realtime"
        qwen = QwenLiveTranslate38Engine(ws_url=maas_url, api_key="sk-ws-testkey")
        qwen.is_running = True

        created_urls = []
        attempt_count = 0

        class MockFailingWebSocketApp:
            def __init__(self, url, **kwargs):
                created_urls.append(url)
                self.url = url

            def run_forever(self, **kwargs):
                nonlocal attempt_count
                attempt_count += 1
                if attempt_count >= 2:
                    qwen.is_running = False
                raise ConnectionRefusedError("Unable to connect to private maas endpoint")

        with patch("engines.qwen_translators.websocket.WebSocketApp", MockFailingWebSocketApp):
            with patch("time.sleep", return_value=None):
                qwen._run_ws()

        self.assertGreaterEqual(len(created_urls), 2, "Must attempt at least 2 connection attempts")
        self.assertIn("maas.aliyuncs.com", created_urls[0], "First attempt must target configured maas URL")
        self.assertIn("dashscope.aliyuncs.com", created_urls[1], "Second attempt must fallback to public dashscope URL")
        self.assertIn("model=qwen3.8-livetranslate-flash-realtime", created_urls[1], "Fallback URL must preserve model parameter")

    # =========================================================================
    # Case 3: HUDWebKitHost drawsTransparentBackground 拦截与零警告
    # =========================================================================
    def test_case3_webkit_host_draws_transparent_background_remapping(self):
        """Case 3: HUDWebKitHost 拦截 drawsTransparentBackground 并重映射为 drawsBackground=False，零废弃调用警告"""
        import float_app

        if sys.platform != "darwin":
            self.skipTest("WebKit HUDWebKitHost test is macOS specific")

        import AppKit
        import WebKit

        # 1. 验证 HUDWebKitHost 定义了 setValue_forKey_ 与 valueForKey_
        self.assertTrue(
            hasattr(float_app.HUDWebKitHost, "setValue_forKey_"),
            "HUDWebKitHost must override setValue_forKey_ to intercept deprecated KVC calls",
        )
        self.assertTrue(
            hasattr(float_app.HUDWebKitHost, "valueForKey_"),
            "HUDWebKitHost must implement valueForKey_ for transparent background getter parity",
        )

        rect = AppKit.NSMakeRect(0, 0, 100, 100)
        cfg = WebKit.WKWebViewConfiguration.alloc().init()
        webview = float_app.HUDWebKitHost.alloc().initWithFrame_configuration_(rect, cfg)

        # 2. 捕获 fd 2 (stderr) 验证无 -[WKWebView _setDrawsTransparentBackground:] 警告
        stderr_fileno = 2
        old_stderr = os.dup(stderr_fileno)
        pipe_r, pipe_w = os.pipe()
        os.dup2(pipe_w, stderr_fileno)
        os.close(pipe_w)

        try:
            webview.setValue_forKey_(True, "drawsTransparentBackground")
        finally:
            os.dup2(old_stderr, stderr_fileno)
            os.close(old_stderr)
            captured_warning = os.read(pipe_r, 4096).decode("utf-8", errors="ignore")
            os.close(pipe_r)

        self.assertNotIn(
            "_setDrawsTransparentBackground",
            captured_warning,
            f"Must not emit deprecated warning: captured {captured_warning!r}",
        )

        # 3. 验证底层 drawsBackground 已置为 False 保持透明
        self.assertFalse(
            bool(webview.valueForKey_("drawsBackground")),
            "drawsBackground must be False for transparent window background",
        )
        self.assertTrue(
            bool(webview.valueForKey_("drawsTransparentBackground")),
            "drawsTransparentBackground getter must return True",
        )

    # =========================================================================
    # Case 4: ChannelSession.sync_hotwords() 默认初始化洁净度
    # =========================================================================
    def test_case4_channel_session_default_init_does_not_inject_empty_translation_asr_fixes(self):
        """Case 4: ChannelSession.sync_hotwords() 默认初始化时不将 239 个无译文 asr_fixes 作为显式热词注入 qwen_engine.hotwords"""
        session = server.ChannelSession("en", "A", "zh", "en", "中译英-英文屏")
        session.qwen_engine.hotwords = []

        # 获取词库中全部无英文翻译的 asr_fixes 词条
        hw_all = server.glossary_mgr.get_hotwords(channel="en")
        cp_all = server.glossary_mgr.get_corpus_phrases(channel="en", target_lang="en", limit=900)
        untranslated_asr_fixes = [w for w in hw_all if w not in cp_all]
        self.assertGreaterEqual(len(untranslated_asr_fixes), 200, "Baseline assertion: untranslated asr_fixes must be present in bank")

        # 1. 默认无参同步 (explicit_hotwords=False)
        session.sync_hotwords()

        qwen_hw = getattr(session.qwen_engine, "hotwords", []) or []
        polluted_terms = [w for w in untranslated_asr_fixes if w in qwen_hw]
        self.assertEqual(
            polluted_terms,
            [],
            f"Default sync_hotwords must not pollute qwen_engine.hotwords with 239 untranslated asr_fixes; found {len(polluted_terms)}: {polluted_terms[:5]}",
        )

        # 2. 显式热词同步 (explicit_hotwords=True) 依然正常生效
        session.sync_hotwords(hotwords=["AI:人工智能", "LoRA:低秩自适应"])
        explicit_hw = getattr(session.qwen_engine, "hotwords", [])
        self.assertIn("AI", explicit_hw)
        self.assertIn("LoRA", explicit_hw)


if __name__ == "__main__":
    unittest.main()
