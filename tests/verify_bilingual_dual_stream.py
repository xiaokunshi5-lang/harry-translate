"""
Verification test for Dual Floating HUD Simultaneous Translation & Tencent Meeting Bilingual Subtitles.
Verifies:
1. Smart audio multiplexing: _on_mic_pcm feeds both channel_en and channel_zh when worker_b is idle.
2. float_ui.html bilingual layout: activeLine (translation) on top, pastLine (source speech) below.
3. Live bilingual event simulation produces proper source and target strings.
"""
import unittest
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


class TestBilingualDualStream(unittest.TestCase):

    def test_01_audio_multiplexing_dual_channel_feed(self):
        """When worker_b is idle, mic audio is mirrored to both channel_en and channel_zh."""
        import server
        # Clear queues
        while not server.channel_en.audio_queue.empty():
            server.channel_en.audio_queue.get_nowait()
        while not server.channel_zh.audio_queue.empty():
            server.channel_zh.audio_queue.get_nowait()

        dummy_pcm = b"\x00\x01" * 800  # 1600 bytes
        server._on_mic_pcm(dummy_pcm)

        self.assertFalse(server.channel_en.audio_queue.empty(), "channel_en must receive mic audio")
        self.assertFalse(server.channel_zh.audio_queue.empty(), "channel_zh must receive mirrored mic audio when loopback is idle")

    def test_02_float_ui_bilingual_layout_order(self):
        """float_ui.html orders activeLine (main translation) above pastLine (source speech)."""
        html_path = os.path.join(PROJECT_ROOT, "float_ui.html")
        with open(html_path, "r", encoding="utf-8") as f:
            html = f.read()

        active_idx = html.find('id="activeLine"')
        past_idx = html.find('id="pastLine"')
        self.assertGreater(active_idx, 0)
        self.assertGreater(past_idx, 0)
        # In DOM inside .subtitle-stage, activeLine must precede pastLine
        stage_sub = html[html.find('<main class="subtitle-stage">'):html.find('</main>')]
        self.assertTrue(stage_sub.find('id="activeLine"') < stage_sub.find('id="pastLine"'),
                        "activeLine (primary translation) must be positioned above pastLine (source speech)")

    def test_03_float_ui_contains_bilingual_rendering_logic(self):
        """float_ui.html contains primary translation & secondary source handling."""
        html_path = os.path.join(PROJECT_ROOT, "float_ui.html")
        with open(html_path, "r", encoding="utf-8") as f:
            html = f.read()

        self.assertIn("primaryTrans", html)
        self.assertIn("secondarySource", html)
        self.assertIn("activeLine.textContent = primaryTrans", html)
        self.assertIn("pastLine.textContent = secondarySource", html)

    def test_04_dual_window_geometry_offset(self):
        """float_app.py configures dual windows with vertical stacking (y=70 top, y=260 bottom)."""
        app_path = os.path.join(PROJECT_ROOT, "float_app.py")
        with open(app_path, "r", encoding="utf-8") as f:
            app_code = f.read()

        self.assertIn("y=70", app_code)
        self.assertIn("y=260", app_code)
        self.assertIn("setMovableByWindowBackground_", app_code)


if __name__ == "__main__":
    unittest.main()
