import unittest
from unittest.mock import Mock, patch
import server


class AudioInputModeTests(unittest.TestCase):
    def route(self, mode, idle, mic=True, subscribed=True):
        a, b = Mock(), Mock()
        manager = Mock()
        manager.worker_b.is_idle = idle
        with patch.multiple(server, AUDIO_INPUT_MODE=mode, channel_en=a,
                            channel_zh=b, audio_capture_mgr=manager), \
                patch.object(server, "is_channel_subscribed", return_value=subscribed):
            (server._on_mic_pcm if mic else server._on_loopback_pcm)(b"audio")
        return a, b

    def test_shared_mic_reaches_both_even_with_active_loopback(self):
        a, b = self.route("shared_mic", False)
        a.push_audio.assert_called_once_with(b"audio")
        b.push_audio.assert_called_once_with(b"audio")

    def test_shared_mic_never_mixes_in_loopback(self):
        a, b = self.route("shared_mic", False, mic=False)
        a.push_audio.assert_not_called()
        b.push_audio.assert_not_called()

    def test_meeting_keeps_mic_and_loopback_separate(self):
        a, b = self.route("meeting", False)
        a.push_audio.assert_called_once()
        b.push_audio.assert_not_called()
        a, b = self.route("meeting", False, mic=False)
        a.push_audio.assert_not_called()
        b.push_audio.assert_called_once()

    def test_meeting_missing_loopback_does_not_silently_use_mic(self):
        _, b = self.route("meeting", True)
        b.push_audio.assert_not_called()

    def test_unsubscribed_channels_receive_no_audio(self):
        a, b = self.route("shared_mic", False, subscribed=False)
        a.push_audio.assert_not_called()
        b.push_audio.assert_not_called()


if __name__ == "__main__":
    unittest.main()
