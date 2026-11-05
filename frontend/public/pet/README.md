# Wobnimo Volt fallback renders

Source: https://github.com/Pouryaak/wobnimo, published npm package `wobnimo@0.2.0`.
MIT license: ../licenses/wobnimo-MIT.txt.

The five WebP images were rendered from the package's original Volt character using
its `snapshot` API (384 CSS pixels, pixelRatio 1, framing 1.05, floor 0, seed 0.5).
The supported palette in `frontend/src/components/pet/volt.ts` changes shell and
accent colours only. Geometry, LED facial expressions and animation remain upstream.

The kiosk passes actual assistant playback states to `Mascot.setState`.
Volt's speaking-mouth animation is synthetic; this integration does not estimate
phonemes or synchronize individual mouth shapes to audio.
