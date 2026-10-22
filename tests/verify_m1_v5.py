#!/usr/bin/env python3
"""
tests/verify_m1_v5.py - Verification Suite for Worker M1: AudioCore & EngineMaster

Verifies:
1. Strict 50ms chunking: SAMPLE_RATE=16000, CHUNK_SAMPLES=800 (50ms), CHUNK_BYTES=1600.
2. Average hot-path processing latency <0.015ms (15µs) across 5,000 frames.
3. Maxsize=3 Drop-Oldest ring buffer under simulated network jitter (0 overflow).
4. Channel B loopback autodetection with safe idle without microphone theft.
5. Python 3.13+ PEP 594 audioop degradation & array downmix.
6. GummyZeroCopyEngine: guarded push (no cold-start crash), mock fallback, standardized output payload.
7. QwenLiveTranslate38Engine & TokenBucketLimiter: session.update <5ms, RPM=10 quota protection.
"""

import array
import os
import queue
import sys
import time

# Ensure project root in sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import core
from core.audio_pipeline import (
    CHUNK_BYTES,
    CHUNK_SAMPLES,
    CHUNK_SIZE,
    MAX_JSON_QUEUE_SIZE,
    SAMPLE_RATE,
    FastAudioCaptureManager,
    FastAudioCaptureWorker,
    downmix_to_mono,
    is_loopback_device_name,
)
import engines
from engines.qwen_translators import (
    GummyZeroCopyEngine,
    QwenLiveTranslate38Engine,
    TokenBucketLimiter,
)


def test_1_strict_50ms_chunking():
    print("\n--- Test 1: Strict 50ms Chunking Specification ---")
    assert SAMPLE_RATE == 16000, f"Expected SAMPLE_RATE=16000, got {SAMPLE_RATE}"
    assert CHUNK_SAMPLES == 800, f"Expected CHUNK_SAMPLES=800, got {CHUNK_SAMPLES}"
    assert CHUNK_BYTES == 1600, f"Expected CHUNK_BYTES=1600, got {CHUNK_BYTES}"
    assert CHUNK_SIZE == 1600, f"Expected CHUNK_SIZE=1600, got {CHUNK_SIZE}"

    # Calculate time duration
    duration_ms = (CHUNK_SAMPLES / SAMPLE_RATE) * 1000.0
    assert duration_ms == 50.0, f"Expected duration 50.0ms, got {duration_ms}ms"

    # Frame alignment (16-bit mono = 2 bytes per sample)
    assert CHUNK_BYTES % 2 == 0, "CHUNK_BYTES must be 2-byte aligned"
    print(f"  [PASS] 50ms chunking confirmed: {SAMPLE_RATE}Hz, {CHUNK_SAMPLES} samples, {CHUNK_BYTES} bytes ({duration_ms:.1f}ms per frame)")


def test_2_hot_path_latency():
    print("\n--- Test 2: Hot-Path Processing Latency (<0.015ms / 15µs) ---")
    worker = FastAudioCaptureWorker(channel_id="A", is_loopback_channel=False)

    received_frames = []

    def zero_copy_cb(pcm_bytes: bytes):
        received_frames.append(len(pcm_bytes))

    worker.set_zero_copy_callback(zero_copy_cb)

    dummy_frame = b"\x12\x34" * CHUNK_SAMPLES  # 1600 bytes
    N = 5000

    # Warmup
    for _ in range(200):
        if worker.direct_zero_copy_cb:
            worker.direct_zero_copy_cb(dummy_frame)
        worker.push_to_json_queue(dummy_frame)

    received_frames.clear()

    # Benchmark 5,000 frames
    t0 = time.perf_counter()
    for _ in range(N):
        # Hot-path dual-track execution
        cb = worker.direct_zero_copy_cb
        if cb is not None:
            cb(dummy_frame)
        worker.push_to_json_queue(dummy_frame)
    t1 = time.perf_counter()

    total_time_ms = (t1 - t0) * 1000.0
    avg_latency_ms = total_time_ms / N
    avg_latency_us = avg_latency_ms * 1000.0

    print(f"  Processed {N} frames in {total_time_ms:.3f}ms")
    print(f"  Average hot-path per-frame latency: {avg_latency_ms:.6f}ms ({avg_latency_us:.3f}µs)")
    assert avg_latency_ms < 0.015, f"Latency SLA VIOLATION: {avg_latency_ms:.6f}ms >= 0.015ms"
    print(f"  [PASS] Hot-path latency SLA met: {avg_latency_ms:.6f}ms < 0.015ms ({avg_latency_us:.2f}µs)")


def test_3_drop_oldest_ring_buffer_under_jitter():
    print("\n--- Test 3: Track 2 Maxsize=3 Drop-Oldest Under Network Jitter ---")
    worker = FastAudioCaptureWorker(channel_id="A", is_loopback_channel=False)
    assert worker.json_queue.maxsize == 3, f"Queue maxsize must be 3, got {worker.json_queue.maxsize}"

    # Push 10 distinct chunks without consuming (simulating consumer blocked for 200ms)
    # 4 chunks = 200ms, pushing 10 chunks = 500ms jitter
    for i in range(10):
        chunk_data = f"FRAME_{i:02d}".encode("ascii").ljust(CHUNK_BYTES, b"\x00")
        worker.push_to_json_queue(chunk_data)

    # Queue should be clamped strictly to maxsize=3
    qsize = worker.json_queue.qsize()
    assert qsize == 3, f"Expected qsize=3, got {qsize}"
    assert worker.dropped_frames_count == 7, f"Expected 7 dropped frames, got {worker.dropped_frames_count}"

    # The 3 remaining items must be the newest frames: FRAME_07, FRAME_08, FRAME_09
    items = []
    while not worker.json_queue.empty():
        items.append(worker.json_queue.get_nowait())

    labels = [item[:8].decode("ascii") for item in items]
    expected_labels = ["FRAME_07", "FRAME_08", "FRAME_09"]
    assert labels == expected_labels, f"Expected newest frames {expected_labels}, got {labels}"
    print(f"  [PASS] Maxsize=3 Drop-Oldest verified: dropped {worker.dropped_frames_count} old frames, preserved newest {labels}")


def test_4_channel_b_safe_idle_no_mic_theft():
    print("\n--- Test 4: Channel B Safe Idle Without Microphone Theft ---")
    worker_b = FastAudioCaptureWorker(channel_id="B", is_loopback_channel=True)

    # Trigger device switch with None (autodetect)
    result = worker_b.switch_device(None)

    # If no virtual soundcard (BlackHole, Stereo Mix, etc.) is installed on the machine:
    if worker_b._find_loopback_device() is None:
        assert worker_b.is_idle is True, "Channel B must enter is_idle=True when no loopback device exists"
        assert worker_b.stream is None, "Channel B must NOT open an audio stream when idle"
        assert worker_b.device_index is None, "Channel B must NOT have an active device index"
        assert result.get("status") == "idle", f"Expected status='idle', got {result.get('status')}"
        print(f"  [PASS] Channel B in SAFE IDLE: {result.get('message')}")
    else:
        # Loopback device was found; verify device name matches loopback pattern
        assert is_loopback_device_name(worker_b.device_name), f"Device {worker_b.device_name} is not loopback"
        print(f"  [PASS] Loopback device detected and bound: {worker_b.device_name}")

    # Now verify that trying to force a physical microphone index onto Channel B is rejected
    default_mic_idx = None
    try:
        def_info = worker_b.p.get_default_input_device_info()
        default_mic_idx = int(def_info.get("index", 0))
        def_name = str(def_info.get("name", ""))
    except Exception:
        def_name = ""

    if default_mic_idx is not None and not is_loopback_device_name(def_name):
        # Attempt to set physical microphone onto Channel B
        res = worker_b.switch_device(default_mic_idx)
        assert res.get("status") == "idle", f"Channel B should refuse microphone device, got {res}"
        assert worker_b.is_idle is True, "Channel B must remain in safe idle when microphone is targeted"
        assert worker_b.stream is None, "Channel B must NEVER hijack microphone stream"
        print(f"  [PASS] Channel B strictly refused physical microphone [{default_mic_idx}: {def_name}]")


def test_5_pep594_audioop_degradation():
    print("\n--- Test 5: PEP 594 3-Tier audioop Fallback & Downmixing ---")
    print(f"  Current active audioop backend: {core.AUDIOOP_BACKEND}")

    # 1. Test mono pass-through
    mono_in = b"\x01\x00\x02\x00" * 400  # 1600 bytes
    mono_out = downmix_to_mono(mono_in, channels=1)
    assert mono_out == mono_in, "Mono input must pass through unchanged"

    # 2. Test stereo downmix (3200 bytes stereo -> 1600 bytes mono)
    # Left channel = 100, Right channel = 200
    stereo_samples = []
    for _ in range(800):
        stereo_samples.extend([100, 200])
    stereo_bytes = array.array("h", stereo_samples).tobytes()
    assert len(stereo_bytes) == 3200

    downmixed = downmix_to_mono(stereo_bytes, channels=2)
    assert len(downmixed) == 1600, f"Expected 1600 bytes, got {len(downmixed)}"

    # 3. Test tier-3 array slicing directly
    a = array.array("h")
    a.frombytes(stereo_bytes)
    c_slice_mono = a[0::2].tobytes()
    assert len(c_slice_mono) == 1600
    res_samples = array.array("h")
    res_samples.frombytes(c_slice_mono)
    assert all(s == 100 for s in res_samples), "Left channel values must be preserved"

    print("  [PASS] PEP 594 degradation verified (3200B stereo -> 1600B mono downmix)")


def test_6_gummy_engine_and_standardized_payload():
    print("\n--- Test 6: GummyZeroCopyEngine & Standardized Payload ---")
    emitted = []

    def test_emit(payload):
        emitted.append(payload)

    engine = GummyZeroCopyEngine(
        channel_id="A",
        source_lang="zh",
        target_lang="en",
        emit_fn=test_emit,
        mock_mode=True,
    )

    # 1. Guard check before start
    assert not engine.is_ready.is_set(), "Engine must not be ready before start"
    sent_before = engine.send_audio_frame(b"\x00" * 1600)
    assert sent_before is False, "Frame push before on_open must be safely guarded"

    # 2. Start engine
    assert engine.start(), "Engine start failed"
    assert engine.is_ready.is_set(), "Engine must be ready after start"

    # 3. Push frame after ready
    sent_after = engine.send_audio_frame(b"\x00" * 1600)
    assert sent_after is True, "Frame push after ready must succeed"

    # 4. Standardized payload format check
    payload = engine.simulate_event(
        source="全球国际会议同声传译",
        target="Global International Conference Simultaneous Interpretation",
        is_final=True,
        latency_ms=425,
        sentence_id=101,
    )

    required_keys = ["type", "ch", "id", "source", "target", "is_final", "latency_ms"]
    for k in required_keys:
        assert k in payload, f"Standardized payload missing key '{k}'"

    assert payload["type"] == "sub", f"Expected type='sub', got {payload['type']}"
    assert payload["ch"] == "A", f"Expected ch='A', got {payload['ch']}"
    assert payload["id"] == "101", f"Expected id='101', got {payload['id']}"
    assert payload["source"] == "全球国际会议同声传译"
    assert payload["target"] == "Global International Conference Simultaneous Interpretation"
    assert payload["is_final"] is True
    assert payload["latency_ms"] == 425

    print(f"  [PASS] GummyZeroCopyEngine cold-start guard & standardized payload verified: {payload}")


def test_7_qwen_engine_and_token_bucket_limiter():
    print("\n--- Test 7: QwenLiveTranslate38Engine & TokenBucketLimiter ---")
    # 1. TokenBucketLimiter RPM=10 check
    limiter = TokenBucketLimiter(capacity=10.0, fill_rate=10.0 / 60.0)
    assert limiter.current_tokens == 10.0

    # Exhaust 10 tokens
    for i in range(10):
        ok = limiter.try_acquire(1.0)
        assert ok is True, f"Failed to acquire token {i+1}"

    # 11th token should fail
    excess = limiter.try_acquire(1.0)
    assert excess is False, "11th token must be denied by RPM=10 quota limiter"
    print("  [PASS] TokenBucketLimiter enforced RPM=10 quota protection (10 granted, 11th rejected)")

    # 2. QwenLiveTranslate38Engine live_update_session SLA < 5ms
    qwen = QwenLiveTranslate38Engine(
        channel_id="B",
        target_lang="en",
        mock_mode=True,
        limiter=limiter,
    )
    qwen.start()

    res = qwen.live_update_session(target_lang="zh", hotwords=["Aliyun", "Gummy", "Qwen"])
    elapsed_ms = res["elapsed_ms"]
    assert res["status"] == "ok"
    assert res["target_lang"] == "zh"
    assert res["hotwords"] == ["Aliyun", "Gummy", "Qwen"]
    assert elapsed_ms < 5.0, f"live_update_session SLA violation: took {elapsed_ms}ms >= 5ms"
    print(f"  [PASS] Qwen 3.8 live_update_session completed in {elapsed_ms:.3f}ms (<5ms SLA)")


def test_8_fast_audio_capture_manager():
    print("\n--- Test 8: FastAudioCaptureManager Dual-Channel Coordination ---")
    mgr = FastAudioCaptureManager()

    # Verify device enumeration contract
    dev_info = mgr.get_devices()
    assert dev_info["status"] == "ok"
    assert "devices" in dev_info
    assert "active_index" in dev_info
    assert "channel_a_device" in dev_info
    assert "channel_b_device" in dev_info
    assert "channel_b_idle" in dev_info

    # Verify is_loopback flag on device list
    for dev in dev_info["devices"]:
        assert "is_loopback" in dev, "Device item must include 'is_loopback'"
        assert isinstance(dev["is_loopback"], bool), "'is_loopback' must be boolean"

    # Backward compatibility properties
    assert hasattr(mgr, "active_stream")
    assert hasattr(mgr, "active_index")
    assert hasattr(mgr, "channels")
    assert hasattr(mgr, "active_channels")
    assert hasattr(mgr, "switch_device")
    assert hasattr(mgr, "set_device")
    assert mgr.MAX_QUEUE_SIZE == 3

    print(f"  [PASS] FastAudioCaptureManager verified: {len(dev_info['devices'])} devices enumerated, backward-compatible API intact")


def main():
    print("=" * 70)
    print(" WORKER M1: AudioCore & EngineMaster Comprehensive Verification")
    print("=" * 70)

    test_1_strict_50ms_chunking()
    test_2_hot_path_latency()
    test_3_drop_oldest_ring_buffer_under_jitter()
    test_4_channel_b_safe_idle_no_mic_theft()
    test_5_pep594_audioop_degradation()
    test_6_gummy_engine_and_standardized_payload()
    test_7_qwen_engine_and_token_bucket_limiter()
    test_8_fast_audio_capture_manager()

    print("\n" + "=" * 70)
    print(" ALL WORKER M1 ACCEPTANCE CRITERIA VERIFIED (100% PASS)")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(main())
