# Audio

Reusable speaker fusion ("Hợp nhất người nói") and delayed STT masking with
optional TSE: diarizer slots, Vision face and active-speaker evidence, the
per-session customer lock, and clean audio for any STT. Ported from OpenJarvis
`server/voice/speaker*.py`; design in
`../docs/superpowers/specs/2026-10-16-audio-repo-design.md`.

## Commands
- Setup: `uv sync` (add `--extra nemo` for the model adapters)
- Tests: `uv run pytest -q`
- Lint: `uv run ruff check src tests tools`; `uv run ruff format --check src tests tools`

## Rules
- Boundary: clean STT audio and speaker verdicts leave the library; turns,
  STT, VAD and agents belong to the host.
- Layers: `application → domain ← infrastructure`, enforced by
  `tests/test_architecture.py`. Domain takes the standard library, numpy and scipy only.
- Never import `openjarvis`, `pipecat` or `loguru` from `src/`; use `logging`.
- Behaviour must match OpenJarvis: verdicts, released STT audio, `voice_speaker_*`
  error codes, telemetry JSON, ASD protocol. Keep customer audio and face data local.
- After changing `domain/`, `application/stream.py` or `application/console.py`,
  rerun the parity check against OpenJarvis (read-only), from `../OpenJarvis`:
  `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=../Audio/src .venv/bin/python ../Audio/tools/parity_check.py`
- `tools/port/` records how the code was ported (`parity-baseline` tag); it is
  not used at runtime.
- Model tests (`tests/infrastructure/test_speaker_{sortformer,titanet,tse}.py`)
  skip without NeMo, torch, a GPU and weights; a skip is not a pass.
- A host adapter forwards raw microphone audio to its own VAD before calling
  `SpeakerStream.push_audio`, as OpenJarvis's processor did; the collector
  counts in `tests/application/test_speaker_audio.py` describe that contract.
  The full host contract (one session per stream, event-loop thread, inline
  callbacks, `finish()` before `close()`) is in `application/stream.py`'s docstring.
- The library logs through stdlib `logging` under `audio.*`. A host whose log
  is not stdlib (OpenJarvis uses loguru) must forward that logger, or the
  fusion and ASD session summaries are lost.
