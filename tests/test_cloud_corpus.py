import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from core.glossary_manager import GlossaryManager
from engines.qwen_translators import QwenLiveTranslate38Engine


class CloudCorpusTests(unittest.TestCase):
    def setUp(self):
        self.engine = QwenLiveTranslate38Engine(api_key="private-test-key")
        self.engine.ws_client = Mock()
        self.engine.ws_client.sock.connected = True

    def sent_session(self):
        return json.loads(self.engine.ws_client.send.call_args.args[0])["session"]

    def test_glossary_direction_and_snapshot(self):
        with tempfile.TemporaryDirectory() as directory:
            glossary = GlossaryManager(str(Path(directory) / 'glossary.json'))
            glossary.reload({"asr_fixes": {"落拉": "LoRA"},
                             "terms_zh_to_en": {"提示词工程": "Prompt Engineering"},
                             "terms_en_to_zh": {"Transformer": "变换器"}})
            terms = glossary.get_cloud_phrases('en')
            self.assertEqual(terms, {"提示词工程": "Prompt Engineering"})
            self.assertEqual(glossary.get_cloud_phrases('zh'), {"Transformer": "变换器"})
            terms.clear()
            self.assertTrue(glossary.get_cloud_phrases('en'))
            self.assertEqual(glossary.get_cloud_phrases('ja'), {})

    def test_correct_nested_payload_and_cloud_confirmation(self):
        terms = {"提示词工程": "Prompt Engineering"}
        self.engine.live_update_session('en', ['提示词工程'], phrases=terms)
        session = self.sent_session()
        self.assertNotIn('corpus', session)
        self.assertEqual(session['translation']['corpus']['phrases'], terms)
        self.assertEqual(self.engine.corpus_status, 'sent')
        self.engine._on_ws_message(None, json.dumps({'type': 'session.updated', 'session': session}))
        self.assertEqual(self.engine.corpus_status, 'confirmed')

    def test_reload_replaces_terms_and_empty_dictionary_clears(self):
        self.engine.live_update_session(phrases={'old': '旧'})
        self.engine.live_update_session(phrases={'new': '新'})
        self.assertEqual(self.sent_session()['translation']['corpus']['phrases'], {'new': '新'})
        self.engine.live_update_session(phrases={})
        self.assertEqual(self.sent_session()['translation']['corpus']['phrases'], {})

    def test_reconnect_resends_current_terms(self):
        self.engine.live_update_session(phrases={'LoRA': '低秩自适应'})
        self.engine.ws_client.send.reset_mock()
        self.engine._on_ws_open(self.engine.ws_client)
        self.assertEqual(self.sent_session()['translation']['corpus']['phrases'], {'LoRA': '低秩自适应'})

    def test_old_ack_does_not_confirm_new_terms(self):
        self.engine.live_update_session(phrases={'old': '旧'})
        old_session = self.sent_session()
        self.engine.live_update_session(phrases={'new': '新'})
        self.engine._on_ws_message(None, json.dumps({'type': 'session.updated', 'session': old_session}))
        self.assertEqual(self.engine.corpus_status, 'unconfirmed')

    def test_send_failure_is_visible_without_key_leak(self):
        self.engine.ws_client.send.side_effect = RuntimeError('Failed private-test-key')
        with contextlib.redirect_stdout(io.StringIO()) as output:
            result = self.engine.live_update_session(phrases={'term': '术语'})
        self.assertEqual(result['status'], 'error')
        self.assertEqual(self.engine.corpus_status, 'error')
        self.assertNotIn('private-test-key', output.getvalue() + self.engine.last_error)

    def test_active_session_reconnects_only_for_changed_configuration(self):
        self.engine.is_running = True
        self.engine.live_update_session(phrases={'old': '旧'})
        self.engine.stop = Mock()
        self.engine.start = Mock(return_value=True)
        self.engine.ws_client.send.reset_mock()
        self.engine.live_update_session(phrases={'old': '旧'})
        self.engine.stop.assert_not_called()
        self.engine.ws_client.send.assert_not_called()
        result = self.engine.live_update_session(phrases={'new': '新'})
        self.assertTrue(result['reconnecting'])
        self.engine.stop.assert_called_once()
        self.engine.start.assert_called_once()
        self.engine._on_ws_open(self.engine.ws_client)
        self.assertEqual(self.sent_session()['translation']['corpus']['phrases'], {'new': '新'})


if __name__ == '__main__':
    unittest.main()
