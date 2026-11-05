"""Wav2Lip source motion adapter for the pinned local LiveTalking checkout.

The same model lip-syncs talking and waving frames; actions never preempt PCM.
The queue boundary carries an epoch so reset discards already-rendered old audio.
"""

import asyncio
import queue
import time
from fractions import Fraction
from functools import lru_cache

import numpy as np
import torch
from aiortc.mediastreams import MediaStreamError
from av import AudioFrame, VideoFrame
from avatars.base_avatar import AudioFrameData
from avatars.wav2lip_avatar import LipReal, load_avatar

from trendcoffee.avatar_composite import composite_face
from trendcoffee.avatar_motion import MotionController
from trendcoffee.avatar_playout import AvatarPlayout


@lru_cache(maxsize=2)
def wave_avatar(avatar_id):
    return load_avatar(avatar_id)


class RealtimeMotion:
    def __init__(self, *, manifest, **kwargs):
        super().__init__(**kwargs)
        count = len(self.frame_list_cycle)
        wave_count = self.append_wave(manifest["wave_avatar_id"])
        self.motion = MotionController.from_manifest(
            manifest, talking_count=count, wave_count=wave_count
        )
        self.last_pcm_at = 0
        self.audio_active = False
        self.playout = AvatarPlayout()
        self.sequence = 0
        self.asr.get_audio_frame = self._audio_frame

    def put_audio_frame(self, audio_chunk, datainfo=None):
        self.last_pcm_at = time.monotonic()
        info = dict(datainfo or {})
        info["sequence"] = self.sequence
        self.playout.push(info["epoch"], self.sequence, info["pcm48"])
        self.sequence += 1
        super().put_audio_frame(audio_chunk, info)

    def install_audio_clock(self):
        player = self.output._player
        track = player.audio
        origin = None
        samples = 0

        async def recv():
            nonlocal origin, samples
            if track.readyState != "live":
                raise MediaStreamError
            player._start(track)
            now = time.monotonic()
            if origin is None or now - (origin + samples / 48000) > 0.2:
                origin = now - samples / 48000
            await asyncio.sleep(max(0, origin + samples / 48000 - time.monotonic()))
            frame = AudioFrame(format="s16", layout="mono", samples=960)
            frame.planes[0].update(self.playout.read())
            frame.sample_rate = 48000
            frame.pts, frame.time_base = samples, Fraction(1, 48000)
            samples += 960
            return frame

        track.recv = recv

    def notify(self, eventpoint):
        sequence = eventpoint.get("audio_sequence")
        if sequence is not None:
            self.playout.activate(eventpoint["epoch"], sequence)

    def _audio_frame(self):
        # The upstream 10ms timeout inserts silence between ordinary 20ms native
        # packets. Wait through short delivery jitter while real PCM is arriving.
        timeout = 0.08 if time.monotonic() - self.last_pcm_at < 0.25 else 0.01
        try:
            frame = self.asr.queue.get(timeout=timeout)
            if not self.audio_active:
                # Pre-roll six 20ms frames once per utterance, like an audio device
                # jitter buffer. GPU batching must not consume right at packet arrival.
                deadline = time.monotonic() + 0.16
                while self.asr.queue.qsize() < 5 and time.monotonic() < deadline:
                    time.sleep(0.005)
                self.audio_active = True
            return frame
        except queue.Empty:
            if time.monotonic() - self.last_pcm_at >= 0.25:
                self.audio_active = False
            return AudioFrameData(np.zeros(self.chunk, dtype=np.float32), type=1)

    def reset_motion(self, epoch):
        # Never wait for CUDA under the motion lock. Publish/reset are atomic at queue boundary.
        with self.motion.lock:
            self.motion.reset(epoch)
            self.playout.reset(epoch)
            self.sequence = 0
            self.audio_active = False
            self.flush_talk()
            self._drain(self.res_frame_queue)
            player = self.output._player
            if player:
                self._drain(player.audio._queue)
                self._drain(player.video._queue)

    @staticmethod
    def _drain(items):
        while True:
            try:
                items.get_nowait()
            except queue.Empty:
                return

    @torch.no_grad()
    def inference(self, quit_event):
        while not quit_event.is_set():
            try:
                features = self.asr.feat_queue.get(timeout=0.2)
            except queue.Empty:
                continue
            audio = []
            while len(audio) < self.batch_size * 2 and not quit_event.is_set():
                try:
                    audio.append(self.asr.output_queue.get(timeout=0.2))
                except queue.Empty:
                    continue
            if quit_event.is_set():
                break
            with self.motion.lock:
                epoch = self.motion.epoch
                stale = any(item.userdata.get("epoch", epoch) != epoch for item in audio)
                if stale:
                    audio = [
                        AudioFrameData(np.zeros(self.chunk, dtype=np.float32), type=1)
                        for _ in audio
                    ]
                speaking = any(item.type == 0 for item in audio)
                indices = self.motion.frames(self.batch_size, speaking=speaking)
            predictions = (
                self._infer_indices(indices, features) if speaking else [None] * len(indices)
            )
            for offset, (idx, prediction) in enumerate(zip(indices, predictions, strict=True)):
                if self.motion.epoch != epoch or quit_event.is_set():
                    break
                item = (epoch, prediction, audio[offset * 2 : offset * 2 + 2], idx)
                try:
                    self.res_frame_queue.put(item, timeout=0.2)
                except queue.Full:
                    # Bound latency under overload instead of blocking session teardown.
                    continue

    def process_frames(self, quit_event):
        while not quit_event.is_set():
            try:
                epoch, prediction, audio, index = self.res_frame_queue.get(timeout=0.2)
            except queue.Empty:
                continue
            if epoch != self.motion.epoch:
                continue
            frame = (
                self.frame_list_cycle[index]
                if prediction is None
                else self.paste_back_frame(prediction, index)
            )
            video = VideoFrame.from_ndarray(frame, format="bgr24")
            with self.motion.lock:
                player = self.output._player
                if epoch != self.motion.epoch or not player:
                    continue
                video_queue = player.video._queue
                if video_queue.full():
                    continue
                sequence = next(
                    (item.userdata.get("sequence") for item in audio if item.type == 0), None
                )
                video_queue.put_nowait((video, {"epoch": epoch, "audio_sequence": sequence}))
                self.speaking = prediction is not None


class MotionAvatar(RealtimeMotion, LipReal):
    def append_wave(self, avatar_id):
        wave = wave_avatar(avatar_id)
        self.frame_list_cycle = self.frame_list_cycle + wave[0]
        self.face_list_cycle = self.face_list_cycle + wave[1]
        self.coord_list_cycle = self.coord_list_cycle + wave[2]
        return len(wave[0])

    @torch.no_grad()
    def _infer_indices(self, indices, features):
        faces = np.asarray([self.face_list_cycle[index] for index in indices])
        masked = faces.copy()
        masked[:, faces.shape[1] // 2 :] = 0
        images = np.concatenate((masked, faces), axis=3).astype(np.float32) / 255
        mel = np.asarray(features, dtype=np.float32)[..., None]
        device = next(self.model.parameters()).device
        images = torch.from_numpy(images.transpose(0, 3, 1, 2)).to(device)
        mel = torch.from_numpy(mel.transpose(0, 3, 1, 2)).to(device)
        return self.model(mel, images).cpu().numpy().transpose(0, 2, 3, 1) * 255

    def paste_back_frame(self, prediction, index):
        return composite_face(
            self.frame_list_cycle[index], prediction, self.coord_list_cycle[index]
        )
