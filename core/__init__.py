"""
core module for Apple-style floating simultaneous translation system.
Exposes FastAudioCaptureWorker, FastAudioCaptureManager, and audio SLA constants.
"""

from .audio_pipeline import (
    AUDIOOP_BACKEND,
    CHUNK_BYTES,
    CHUNK_SAMPLES,
    CHUNK_SIZE,
    LOOPBACK_KEYWORDS,
    MAX_JSON_QUEUE_SIZE,
    SAMPLE_RATE,
    AudioCaptureManager,
    FastAudioCaptureManager,
    FastAudioCaptureWorker,
    downmix_to_mono,
    is_loopback_device_name,
)

__all__ = [
    "AUDIOOP_BACKEND",
    "CHUNK_BYTES",
    "CHUNK_SAMPLES",
    "CHUNK_SIZE",
    "LOOPBACK_KEYWORDS",
    "MAX_JSON_QUEUE_SIZE",
    "SAMPLE_RATE",
    "AudioCaptureManager",
    "FastAudioCaptureManager",
    "FastAudioCaptureWorker",
    "downmix_to_mono",
    "is_loopback_device_name",
]
