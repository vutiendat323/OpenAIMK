"""Make 16kHz avatar features, optionally preserving 48kHz RTP playback."""

from av import AudioFrame, AudioResampler


class AvatarPCMStream:
    def __init__(self, preserve_original=True):
        self.playback = (
            AudioResampler(format="s16", layout="mono", rate=48000) if preserve_original else None
        )
        self.model = AudioResampler(format="s16", layout="mono", rate=16000)
        self.model_pending = bytearray()
        self.playback_pending = bytearray()

    def push(self, raw, rate, channels):
        frame = AudioFrame(
            format="s16",
            layout="mono" if channels == 1 else "stereo",
            samples=len(raw) // (channels * 2),
        )
        frame.planes[0].update(raw)
        frame.sample_rate = rate
        natives = self.playback.resample(frame) if self.playback is not None else [frame]
        for native in natives:
            if self.playback is not None:
                self.playback_pending.extend(bytes(native.planes[0])[: native.samples * 2])
            for feature in self.model.resample(native):
                self.model_pending.extend(bytes(feature.planes[0])[: feature.samples * 2])
        result = []
        while len(self.model_pending) >= 640 and (
            self.playback is None or len(self.playback_pending) >= 1920
        ):
            original = bytes(self.playback_pending[:1920]) if self.playback is not None else None
            result.append((bytes(self.model_pending[:640]), original))
            del self.model_pending[:640]
            del self.playback_pending[:1920]
        return result
