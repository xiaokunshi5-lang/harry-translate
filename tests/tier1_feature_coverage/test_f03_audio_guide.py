"""
Feature 3: Remote Meeting Audio Guide (Milestone M1).
Verifies existence and quality of docs/AUDIO_SETUP_GUIDE.md covering macOS BlackHole 2ch,
Windows Stereo Mix/VB-CABLE, echo loop prevention, and step-by-step setup.
"""
import os
from tests.harness import BaseE2ETest, PROJECT_ROOT


class TestFeature03AudioGuide(BaseE2ETest):
    tier = 1
    feature_id = 3
    milestone = "M1"

    def _get_guide_text(self) -> str:
        guide_path = os.path.join(PROJECT_ROOT, "docs", "AUDIO_SETUP_GUIDE.md")
        self.assertTrue(os.path.exists(guide_path), f"Missing guide file at {guide_path}")
        with open(guide_path, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertGreater(len(content.strip()), 100, "Guide file is too short or empty")
        return content

    def test_f03_01_guide_file_existence(self):
        """docs/AUDIO_SETUP_GUIDE.md exists and contains markdown documentation."""
        text = self._get_guide_text()
        self.assertTrue(text.startswith("#"), "Guide should start with a markdown header")

    def test_f03_02_macos_blackhole_instructions(self):
        """Guide provides clear macOS instructions for BlackHole 2ch and Multi-Output Device."""
        text = self._get_guide_text().lower()
        self.assertIn("blackhole", text, "Guide missing BlackHole 2ch instructions")
        self.assertTrue(
            "multi-output" in text or "多输出设备" in text,
            "Guide missing Multi-Output Device configuration steps"
        )

    def test_f03_03_windows_stereo_mix_instructions(self):
        """Guide provides clear Windows instructions for Stereo Mix or VB-CABLE."""
        text = self._get_guide_text().lower()
        has_win_guide = ("stereo mix" in text or "立体声混音" in text or "vb-cable" in text or "vbcable" in text)
        self.assertTrue(has_win_guide, "Guide missing Windows Stereo Mix / VB-CABLE setup")

    def test_f03_04_echo_prevention_guidance(self):
        """Guide documents echo feedback prevention (speaker vs mic loop)."""
        text = self._get_guide_text().lower()
        has_echo_guide = ("echo" in text or "回音" in text or "啸叫" in text or "feedback" in text or "耳机" in text or "headphone" in text)
        self.assertTrue(has_echo_guide, "Guide missing guidance on preventing audio echo/feedback loops")

    def test_f03_05_zero_barrier_step_by_step(self):
        """Guide includes step-by-step numbered steps or verification methods."""
        text = self._get_guide_text()
        # Should have numbered steps (1., 2., 3.) or clear sections
        has_steps = any(f"{i}." in text or f"{i}、" in text for i in range(1, 4))
        self.assertTrue(has_steps, "Guide should provide numbered step-by-step instructions")
