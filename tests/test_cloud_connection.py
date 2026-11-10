import contextlib
import io
import json
import unittest
from unittest.mock import Mock, patch

from engines.qwen_translators import QwenLiveTranslate38Engine


class CloudConnectionTests(unittest.TestCase):
    def test_session_explicitly_sets_supported_voice_and_text_output(self):
        engine = QwenLiveTranslate38Engine(api_key="test-token")
        engine.ws_client = Mock()
        engine.ws_client.sock.connected = True
        engine.live_update_session("en", ["meeting"])
        session = json.loads(engine.ws_client.send.call_args.args[0])["session"]
        self.assertEqual(session["voice"], "Tina")
        self.assertEqual(session["output_modalities"], ["text"])
        self.assertEqual(session["modalities"], ["text"])
        self.assertEqual(session["input_audio_transcription"]["model"], "qwen3-asr-flash-realtime")

    def test_cloud_error_clears_ready_and_redacts_key(self):
        engine = QwenLiveTranslate38Engine(api_key="private-test-token")
        engine.is_ready.set()
        with contextlib.redirect_stdout(io.StringIO()) as captured:
            engine._on_ws_message(None, json.dumps({"type": "error", "error": "Rejected private-test-token"}))
        self.assertFalse(engine.is_ready.is_set())
        self.assertNotIn("private-test-token", engine.last_error + captured.getvalue())
        self.assertIn("Rejected", engine.last_error)

    def test_missing_key_does_not_permanently_enable_mock_mode(self):
        engine = QwenLiveTranslate38Engine()
        engine.api_key = ""
        self.assertFalse(engine.start())
        self.assertFalse(engine.mock_mode)
        with patch("engines.qwen_translators.threading.Thread") as thread:
            self.assertTrue(engine.start("test-token"))
            self.assertTrue(engine.start("test-token"))
            self.assertEqual(thread.call_count, 1)


if __name__ == "__main__":
    unittest.main()
