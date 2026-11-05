# Consistent kiosk voice

The selected Codex v3 voice must speak the greeting, conversation and farewell.
Keep the existing Vietnamese sentences and immediate boundary playback. Capture the
voice at guest start; a preference change during a guest applies to the next guest,
including keeping the current guest's farewell in their original voice.

The existing mismatch comes from two generic WAV files played independently of
the native conversation's voice. Generate per-voice WAV clips through the same
installed native Codex v3 engine, including its unoverridden default. Use an
isolated thread without business tools or real microphone input. Existing fixed
clips serve only as synthetic input to an exact-repeat renderer, because the
installed CLI's text-append probes produced no speech on the WebRTC path. Require
the final transcript to match the intended sentence before saving a clip.

Alternatives considered: generating at every guest boundary adds network latency
and can fail after the customer leaves; a separate TTS engine has a different
voice catalog and cannot guarantee identity. Prebuilt native clips preserve both
identity and prompt boundary playback. This implementation choice is the agent's.

Expose only native voices with both clips available, so every selectable voice
supports all three speech stages. A reproducible preparation command refreshes
the asset set when the installed native catalog changes. Keep the two old source
recordings for rendering only. Conversation transport and business tools stay as
they are. No automatic changes to an active guest's voice or cart.

Verification: distinguish two voices' audio, preserve the captured farewell on a
mid-session selection, keep boundary playback independent of connection/cleanup,
check every available voice's assets, and run native rendering plus browser checks.
