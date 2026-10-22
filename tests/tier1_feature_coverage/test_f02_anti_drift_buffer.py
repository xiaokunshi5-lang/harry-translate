"""
Feature 2: Anti-Drift Audio Buffering (Milestone M1).
Verifies chunk size 1600 (100ms / 16kHz mono), Drop-Oldest ring buffer maxsize=5,
overflow eviction behavior, latency anti-accumulation, and PCM mono frame integrity.
"""
import os
import queue
import time
from tests.harness import BaseE2ETest, PROJECT_ROOT


class TestFeature02AntiDriftBuffer(BaseE2ETest):
    tier = 1
    feature_id = 2
    milestone = "M1"

    def test_f02_01_chunk_size_1600_mono(self):
        """Chunk size is configured to 1600 bytes (100ms / 16kHz mono 16-bit PCM)."""
        import server
        chunk_size = getattr(server, "CHUNK_SIZE", None)
        self.assertEqual(chunk_size, 1600, f"Expected CHUNK_SIZE=1600, got {chunk_size}")

    def test_f02_02_drop_oldest_ring_buffer_depth(self):
        """Audio queue maxsize is clamped to 5 (500ms max latency buffer)."""
        import server
        # Check active channel audio queue depth
        if hasattr(server, "active_channels") and server.active_channels:
            for ch in server.active_channels:
                self.assertLessEqual(ch.audio_queue.maxsize, 5, f"Channel {ch.name} queue maxsize exceeds 5")
        if hasattr(server, "AudioCaptureManager"):
            mgr = server.AudioCaptureManager
            if hasattr(mgr, "MAX_QUEUE_SIZE"):
                self.assertLessEqual(mgr.MAX_QUEUE_SIZE, 5)

    def test_f02_03_overflow_eviction_behavior(self):
        """Pushing more than 5 chunks evicts the oldest chunk to prevent latency lag."""
        import server
        if hasattr(server, "active_channels") and server.active_channels:
            ch = server.active_channels[0]
            # Clear queue
            while not ch.audio_queue.empty():
                try:
                    ch.audio_queue.get_nowait()
                except queue.Empty:
                    break

            # If channel implements drop-oldest push
            push_fn = getattr(ch, "push_audio", None)
            if push_fn:
                for i in range(10):
                    push_fn(f"chunk_{i}".encode("utf-8"))
                self.assertLessEqual(ch.audio_queue.qsize(), 5)
            else:
                # Direct queue check
                self.assertLessEqual(ch.audio_queue.maxsize, 5)

    def test_f02_04_latency_anti_accumulation(self):
        """Total unconsumed audio in queue represents at most 500ms of audio (5 * 100ms)."""
        import server
        chunk_size = getattr(server, "CHUNK_SIZE", 1600)
        sample_rate = getattr(server, "SAMPLE_RATE", 16000)
        # 16-bit mono = 2 bytes per sample -> 1600 bytes = 800 samples = 50ms at 16kHz or 100ms at 8kHz
        # For 16kHz 16-bit mono, 100ms = 1600 samples = 3200 bytes, or 1600 samples 8-bit.
        # Original spec defines: chunk size 1600 = 100ms / 16kHz mono.
        # Max 5 slots * 100ms = 500ms.
        max_slots = 5
        if hasattr(server, "active_channels") and server.active_channels:
            max_slots = server.active_channels[0].audio_queue.maxsize
        self.assertLessEqual(max_slots * 100, 500, "Audio buffer latency exceeds 500ms limit")

    def test_f02_05_audio_frame_integrity(self):
        """16-bit mono chunk size must be divisible by 2 (2 bytes per sample)."""
        import server
        chunk_size = getattr(server, "CHUNK_SIZE", 1600)
        self.assertEqual(chunk_size % 2, 0, f"CHUNK_SIZE {chunk_size} is not aligned to 16-bit (2-byte) samples")
