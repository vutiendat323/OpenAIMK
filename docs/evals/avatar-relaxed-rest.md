# Original smile after speech

User reference: the standing clip's relaxed, slightly smiling closed lips. The
generated zero-audio pose instead looked pursed. Keeping that generated texture
after speech changed the character's expression.

## Cause and correction

The GPU worker used packet arrival to decide whether to infer. Silent packets
therefore kept it working, and a packet gap also requested a neutral generated
mouth. The presenter continued displaying that cached mouth over the source.

The presenter now restores **the actual current source frame** after 280 ms
without voiced assistant PCM. Voiced PCM uses RMS >0.001 (-60 dBFS). This check
is only on the assistant audio copied to the avatar; microphone processing and
speaker PCM are unchanged. The source's eyes, face, clothing and background stay
in the same clip and source clock.

Rest also clears the old mouth texture. Resumed speech keeps the original smile
until a fresh generated texture arrives, rather than flashing the preceding
utterance's final mouth. The worker skips neutral inference during silent packets
and gaps. The independent source presenter continues at 24 FPS.

## Evidence

- CPU regression: voiced PCM displays the generated mouth, continuously arriving
  zero PCM restores the source pixel for pixel, resumed PCM waits for a fresh
  mouth, then displays its new texture.
- CPU worker regression: silent packets and pauses perform no neutral-mouth
  inference. Smile without speech preserves source pixels.
- Actual decoded WebRTC recording reports `mouth_mode: source` during the PCM
  gap and `generated` during speech. [Received resting frame](../../output/avatar-quality-review/neural-fps/conversation-optimized/relaxed-source-smile.jpg)
  shows the original relaxed smile. [Preview](../../output/avatar-quality-review/neural-fps/conversation-optimized/conversation-preview.mp4)
  contains speech, rest, resumed speech and waving.

The preview uses prerecorded reference PCM aligned at feed time +160 ms. It is
not a physical speaker/microphone recording and does not establish acoustic sync
or acceptance of generated lips during speech. The source smile itself is not
reconstructed by the mouth model.
