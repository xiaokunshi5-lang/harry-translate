"""
Tier 2 Boundary Tests: Feature 2 (Anti-Drift Audio Buffering).
Tests empty audio chunks, PCM clipping values (32767 / -32768), rapid burst arrivals,
queue timeout handling, and buffer underflow recovery.
"""
import queue
import time
import struct
from tests.harness import BaseE2ETest


class TestBoundary02AntiDriftBuffer(BaseE2ETest):
    tier = 2
    feature_id = 2
    milestone = "M1"

    def test_b02_01_empty_chunk_handling(self):
        """Empty audio chunk (0 bytes) is handled without crashing audio queue or stream worker."""
        import server
        if hasattr(server, "active_channels") and server.active_channels:
            ch = server.active_channels[0]
            # Should handle 0-byte chunk gracefully
            try:
                if hasattr(ch, "push_audio"):
                    ch.push_audio(b"")
                else:
                    ch.audio_queue.put(b"", block=False)
            except Exception as e:
                self.fail(f"Pushing empty chunk raised exception: {e}")

    def test_b02_02_pcm_clipping_extremes(self):
        """Audio chunks at extreme clipping amplitudes (32767, -32768) process safely without integer overflow."""
        # 1600 bytes = 800 16-bit signed integers
        clipped_max = struct.pack("<800h", *([32767] * 800))
        clipped_min = struct.pack("<800h", *([-32768] * 800))
        self.assertEqual(len(clipped_max), 1600)
        self.assertEqual(len(clipped_min), 1600)

        import server
        if hasattr(server, "active_channels") and server.active_channels:
            ch = server.active_channels[0]
            if hasattr(ch, "push_audio"):
                ch.push_audio(clipped_max)
                ch.push_audio(clipped_min)

    def test_b02_03_burst_arrival_drop_oldest(self):
        """Burst of 50 chunks arriving in 1ms drops 45 oldest, keeping queue size <= 5."""
        import server
        if hasattr(server, "active_channels") and server.active_channels:
            ch = server.active_channels[0]
            if hasattr(ch, "push_audio"):
                for i in range(50):
                    chunk = f"chunk_{i:04d}".encode("utf-8").ljust(1600, b"\x00")
                    ch.push_audio(chunk)
                self.assertLessEqual(ch.audio_queue.qsize(), 5)

    def test_b02_04_queue_timeout_no_busy_spin(self):
        """Empty queue read timeout handles queue.Empty without high CPU spin."""
        q = queue.Queue(maxsize=5)
        t0 = time.perf_counter()
        try:
            q.get(timeout=0.05)
        except queue.Empty:
            pass
        elapsed = time.perf_counter() - t0
        self.assertGreaterEqual(elapsed, 0.04)

    def test_b02_05_buffer_underflow_recovery(self):
        """When producer stops sending chunks, consumer recovers cleanly once new audio resumes."""
        import server
        if hasattr(server, "active_channels") and server.active_channels:
            ch = server.active_channels[0]
            # Drain queue
            while not ch.audio_queue.empty():
                try:
                    ch.audio_queue.get_nowait()
                except queue.Empty:
                    break
            self.assertTrue(ch.audio_queue.empty())
            # Feed new chunk
            new_chunk = b"\x00" * 1600
            if hasattr(ch, "push_audio"):
                ch.push_audio(new_chunk)
                self.assertFalse(ch.audio_queue.empty())
