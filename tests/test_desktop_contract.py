"""Desktop release requirements; no real account or microphone needed."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch


class DesktopContract(unittest.TestCase):
    def test_resource_and_user_data_are_separate(self):
        from core.app_paths import resource_path, data_path
        with tempfile.TemporaryDirectory() as directory:
            with patch.dict('os.environ', {'HARRY_DATA_DIR': directory}):
                self.assertEqual(data_path('settings.json'), Path(directory) / 'settings.json')
                self.assertNotEqual(resource_path('settings.json'), data_path('settings.json'))

    def test_endpoint_rejects_non_alibaba_and_bad_workspace(self):
        from core.desktop_security import endpoint_for
        self.assertIn('dashscope.aliyuncs.com', endpoint_for('beijing', ''))
        for region, workspace in [('evil.example', ''), ('beijing', '../bad')]:
            with self.assertRaises(ValueError):
                endpoint_for(region, workspace)

    def test_empty_key_never_connects(self):
        from core.desktop_security import validate_key
        with patch('websocket.create_connection') as connect:
            with self.assertRaises(ValueError):
                validate_key('', 'beijing', '')
            connect.assert_not_called()

    def test_cloud_validation_requires_session_ack_and_closes(self):
        from core.desktop_security import validate_key
        ws = Mock()
        ws.recv.side_effect = ['{"type":"session.created"}', '{"type":"session.updated"}']
        with patch('websocket.create_connection', return_value=ws):
            result = validate_key('unit-test-private', 'beijing', '')
        self.assertIn('ws_url', result)
        ws.close.assert_called_once()
        self.assertNotIn('input_audio_buffer.append', str(ws.send.call_args_list))

    def test_failed_validation_redacts_secret(self):
        from core.desktop_security import validate_key
        ws = Mock()
        ws.recv.return_value = '{"type":"error","error":{"message":"unit-test-private invalid_api_key"}}'
        with patch('websocket.create_connection', return_value=ws):
            with self.assertRaises(ValueError) as result:
                validate_key('unit-test-private', 'beijing', '')
        self.assertNotIn('unit-test-private', str(result.exception))
        ws.close.assert_called_once()

    def test_audio_manager_can_enumerate_without_opening_mic(self):
        from core.audio_pipeline import FastAudioCaptureManager
        with patch('core.audio_pipeline.pyaudio.PyAudio') as audio:
            manager = FastAudioCaptureManager(defer_open=True)
            audio.return_value.open.assert_not_called()
            manager.terminate()


if __name__ == '__main__':
    unittest.main()
