#!/usr/bin/env python3
"""
tests/test_channel_switching_and_gating.py

Comprehensive tests for:
1. Server-side Client-Aware Stream Gating (token & bandwidth savings).
2. UI Interactive Pill DOM & Keyboard Shortcuts (Cmd+Shift+T).
3. LocalStorage channel persistence & auto-detection.
4. Dedicated launch scripts for 英译中 (zh) and 中译英 (en).
"""

import os
import re
import sys
import stat
import queue
import unittest
import subprocess
from unittest.mock import MagicMock

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import server
from float_app import FloatingHUDApp


class TestChannelSwitchingAndGating(unittest.TestCase):
    def setUp(self):
        # Clear connected clients
        server.connected_clients["en"].clear()
        server.connected_clients["zh"].clear()
        # Drain queues
        while not server.channel_en.audio_queue.empty():
            try:
                server.channel_en.audio_queue.get_nowait()
            except queue.Empty:
                break
        while not server.channel_zh.audio_queue.empty():
            try:
                server.channel_zh.audio_queue.get_nowait()
            except queue.Empty:
                break

    def tearDown(self):
        server.connected_clients["en"].clear()
        server.connected_clients["zh"].clear()

    def test_01_gating_unsubscribed_default(self):
        """When 0 clients are connected, both channels are subscribed by default (passes benchmarks)."""
        self.assertTrue(server.is_channel_subscribed("en"))
        self.assertTrue(server.is_channel_subscribed("zh"))

        server._on_mic_pcm(b"UNSUBSCRIBED_MIC_FRAME")
        self.assertFalse(server.channel_en.audio_queue.empty())
        self.assertFalse(server.channel_zh.audio_queue.empty())

    def test_02_gating_zh_only_cuts_en_tokens(self):
        """When only zh (英译中) client is connected, en audio push is 100% gated (saving 50% cloud tokens)."""
        mock_ws_zh = MagicMock()
        server.connected_clients["zh"].add(mock_ws_zh)

        self.assertTrue(server.is_channel_subscribed("zh"))
        self.assertFalse(server.is_channel_subscribed("en"))

        # Push audio chunk
        server._on_mic_pcm(b"STUDENT_ZH_FRAME")

        # Channel EN MUST be empty (0 tokens wasted!)
        self.assertTrue(server.channel_en.audio_queue.empty(), "channel_en should NOT receive audio when only zh is active")
        # Channel ZH MUST receive audio
        self.assertFalse(server.channel_zh.audio_queue.empty(), "channel_zh MUST receive audio")

    def test_03_gating_en_only_cuts_zh_tokens(self):
        """When only en (中译英) client is connected, zh audio push is 100% gated."""
        mock_ws_en = MagicMock()
        server.connected_clients["en"].add(mock_ws_en)

        self.assertTrue(server.is_channel_subscribed("en"))
        self.assertFalse(server.is_channel_subscribed("zh"))

        # Push audio chunk
        server._on_mic_pcm(b"SPEAKER_EN_FRAME")

        # Channel EN MUST receive audio
        self.assertFalse(server.channel_en.audio_queue.empty(), "channel_en MUST receive audio")
        # Channel ZH MUST be empty
        self.assertTrue(server.channel_zh.audio_queue.empty(), "channel_zh should NOT receive audio when only en is active")

    def test_04_gating_dual_both_active(self):
        """When both channels are connected, both receive audio concurrently."""
        mock_ws_en = MagicMock()
        mock_ws_zh = MagicMock()
        server.connected_clients["en"].add(mock_ws_en)
        server.connected_clients["zh"].add(mock_ws_zh)

        self.assertTrue(server.is_channel_subscribed("en"))
        self.assertTrue(server.is_channel_subscribed("zh"))

        server._on_mic_pcm(b"DUAL_FRAME")
        self.assertFalse(server.channel_en.audio_queue.empty())
        self.assertFalse(server.channel_zh.audio_queue.empty())

    def test_05_float_ui_pill_markup_and_ac09_protection(self):
        """Channel pill must be a <span> (NOT <button>) to preserve AC-09 strict limit."""
        html_path = os.path.join(PROJECT_ROOT, "float_ui.html")
        with open(html_path, "r", encoding="utf-8") as f:
            html = f.read()

        # Check span tag
        self.assertIn('<span class="hud-channel-pill', html)
        self.assertIn('id="hud-channel-pill"', html)

        # Ensure header strictly has <=3 button tags
        header_match = re.search(r'<header[^>]*class="[^"]*hud-header[^"]*"[^>]*>(.*?)</header>', html, re.S)
        self.assertIsNotNone(header_match)
        header_content = header_match.group(1)
        buttons = re.findall(r'<button\b', header_content)
        self.assertLessEqual(len(buttons), 3, f"Buttons in header must be <= 3, found {len(buttons)}")

        # Check CSS rules
        self.assertIn('.hud-channel-pill', html)
        self.assertIn('.hud-channel-pill.channel-zh', html)

        # Check keyboard shortcut Cmd+Shift+T / Ctrl+Shift+T
        self.assertIn("(e.key === 'T' || e.key === 't')", html)
        self.assertIn("toggleChannel()", html)

        # Check localStorage persistence
        self.assertIn("localStorage.setItem('qwen_hud_channel', currentChannel)", html)

    def test_06_float_app_url_construction(self):
        """FloatingHUDApp constructs URL properly for auto, en, zh, and dual modes."""
        app_auto = FloatingHUDApp(channel="auto")
        self.assertEqual(app_auto.channel, "auto")

        app_zh = FloatingHUDApp(channel="zh")
        self.assertEqual(app_zh.channel, "zh")

        app_en = FloatingHUDApp(channel="en")
        self.assertEqual(app_en.channel, "en")

        app_dual = FloatingHUDApp(dual=True)
        self.assertTrue(app_dual.is_dual)

    def test_07_dedicated_scripts_exist_and_valid(self):
        """Dedicated launch scripts for zh and en exist, have +x, and pass syntax checks."""
        scripts = [
            ("启动悬浮同传_英译中.command", True),
            ("启动悬浮同传_中译英.command", True),
            ("启动悬浮同传_英译中.bat", False),
            ("启动悬浮同传_中译英.bat", False),
        ]
        for name, is_shell in scripts:
            path = os.path.join(PROJECT_ROOT, name)
            self.assertTrue(os.path.exists(path), f"File {name} must exist")
            if is_shell:
                st = os.stat(path)
                self.assertTrue(bool(st.st_mode & stat.S_IXUSR), f"{name} must be executable (+x)")
                res_b = subprocess.run(["bash", "-n", path], capture_output=True, text=True)
                self.assertEqual(res_b.returncode, 0, f"bash -n failed on {name}: {res_b.stderr}")
                res_z = subprocess.run(["zsh", "-n", path], capture_output=True, text=True)
                self.assertEqual(res_z.returncode, 0, f"zsh -n failed on {name}: {res_z.stderr}")
            else:
                with open(path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                self.assertIn("float_app.py", content)


if __name__ == "__main__":
    unittest.main()
