import unittest
from unittest.mock import Mock
from core.audio_pipeline import FastAudioCaptureWorker


class NativeRateTests(unittest.TestCase):
    def test_48k_only_microphone_opens_without_manual_setup(self):
        audio = Mock()
        audio.get_device_info_by_index.return_value = {'name': 'Native microphone', 'maxInputChannels': 1, 'defaultSampleRate': 48000}
        stream = Mock()
        def open_audio(**kwargs):
            if kwargs['rate'] != 48000:
                raise OSError('unsupported sample rate')
            return stream
        audio.open.side_effect = open_audio
        worker = FastAudioCaptureWorker('A', shared_pyaudio=audio)
        result = worker.switch_device(2)
        self.assertEqual(result['status'], 'ok')
        self.assertEqual(worker.capture_rate, 48000)
        self.assertEqual(worker.sample_rate, 16000)
        worker.stop()

    def test_native_capture_delivers_16k_50ms_mono_frames(self):
        audio = Mock()
        worker = FastAudioCaptureWorker('A', shared_pyaudio=audio)
        worker.capture_rate = 48000
        worker.stream = Mock()
        worker.stream.read.side_effect = lambda size, **kwargs: b'\x01\x00' * size
        frames = []
        def received(frame):
            frames.append(frame)
            if len(frames) == 2:
                worker.is_running = False
        worker.direct_zero_copy_cb = received
        worker.is_running = True
        worker._capture_loop()
        self.assertEqual([len(frame) for frame in frames], [1600, 1600])
        self.assertEqual(worker.stream.read.call_args.args[0], 2400)
        self.assertEqual(frames[0], b'\x01\x00' * 800)
        worker.stop()


if __name__ == '__main__':
    unittest.main()
