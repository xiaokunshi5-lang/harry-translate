"""
Tier 2 Boundary Tests: Feature 3 (Remote Meeting Audio Guide).
Tests edge cases in audio setup: missing virtual audio device, channel downmixing,
sample rate mismatches, privacy permission denials, and formatting integrity.
"""
import os
from tests.harness import BaseE2ETest, PROJECT_ROOT


class TestBoundary03AudioGuide(BaseE2ETest):
    tier = 2
    feature_id = 3
    milestone = "M1"

    def _get_guide(self) -> str:
        path = os.path.join(PROJECT_ROOT, "docs", "AUDIO_SETUP_GUIDE.md")
        self.assertTrue(os.path.exists(path), f"Missing guide: {path}")
        with open(path, "r", encoding="utf-8") as f:
            return f.read()

    def test_b03_01_troubleshooting_missing_blackhole(self):
        """Guide includes troubleshooting steps when virtual loopback device is not detected."""
        text = self._get_guide().lower()
        has_troubleshooting = ("faq" in text or "排错" in text or "troubleshoot" in text or "找不到" in text or "not found" in text or "未显示" in text)
        self.assertTrue(has_troubleshooting, "Guide should provide troubleshooting for missing loopback device")

    def test_b03_02_channel_configuration_details(self):
        """Guide specifies channel layout (2ch vs multi-channel downmixing)."""
        text = self._get_guide().lower()
        has_channel_info = ("2ch" in text or "2通道" in text or "声道" in text or "channel" in text)
        self.assertTrue(has_channel_info, "Guide should mention 2-channel setup")

    def test_b03_03_sample_rate_clarification(self):
        """Guide mentions sample rate settings (16000 Hz, 44100 Hz, or 48000 Hz)."""
        text = self._get_guide()
        has_sample_rate = ("16000" in text or "16k" in text.lower() or "44100" in text or "48000" in text or "采样率" in text or "hz" in text.lower())
        self.assertTrue(has_sample_rate, "Guide should specify recommended audio sample rates")

    def test_b03_04_microphone_privacy_permission(self):
        """Guide covers macOS Microphone Privacy & Security permission authorization."""
        text = self._get_guide().lower()
        has_perm = ("privacy" in text or "security" in text or "权限" in text or "麦克风" in text or "permission" in text)
        self.assertTrue(has_perm, "Guide should explain microphone privacy permissions")

    def test_b03_05_markdown_formatting_integrity(self):
        """Guide maintains clean markdown formatting without broken code fences."""
        text = self._get_guide()
        fence_count = text.count("```")
        self.assertEqual(fence_count % 2, 0, f"Unbalanced markdown code fences in guide (count={fence_count})")
