# Website Codex voice selection — 2026-10-23

## Supported voices

Queried the installed Codex CLI **0.163.0** through the experimental
thread/realtime/listVoices method. Its **v3** list has 25 entries:

Juniper, Maple, Spruce, Ember, Vale, Breeze, Arbor, Sol, Cove, Aube, Bubbie,
Haetsal, Hanul, Himari, Leher, Miko, Neer, Porto, Rindo, Rio, Rivage, Selva,
Sonna, Tinta and Viola.

The CLI's v2 list is different (10 voices); its overall protocol enum includes
both families. The kiosk uses v3 and exposes only that runtime list. No gender
metadata is returned, so the UI uses names without invented male/female labels.
The default option omits the native voice override, preserving Codex's default.
Catalogs are cached per CLI process and reloaded when its process restarts.

Official context: [Codex App Server](https://learn.chatgpt.com/docs/app-server),
[ChatGPT Voice](https://learn.chatgpt.com/docs/features/voice). The exact list above
comes from the installed CLI, rather than the separate public Realtime API list.

## Website behavior

- The assistant has a **Giọng nói** selector backed by GET /api/kiosk/voices.
- A non-secret voice ID is remembered in localStorage for the current origin.
  Blocked browser storage does not prevent selection during the current page visit.
- Authenticated controller attachment and settings changes validate the selected ID
  against Codex's v3 catalog. Unsupported voices are rejected before taking control.
- A waiting controller can change the next voice directly. During a guest session,
  changes apply to the next session; active conversation, cart and owner remain intact.
- Both PCM and WebRTC start requests receive the voice captured for their thread.
  A prepared call with a different voice cannot be adopted for the guest.
- Connection setup keeps the selector disabled until the socket opens. Voice settings
  acknowledgments survive guest-boundary notifications; business commands remain
  scoped to their guest. Shutdown cancels all outstanding commands.
- Recorded greeting/goodbye clips keep their existing voice. The chosen voice affects
  native conversation speech. Luna/medium/priority and Fusion speaker checks remain.

## Verification evidence

New native/catalog/host regressions failed before implementation, then passed.
Built-browser tests select Maple, change to Rio during an active guest, verify
deferred application, and retain Rio after reload. Two review findings were also
reproduced before fixing: changing during socket connection, and receiving a guest
notification before a settings acknowledgment. All six browser boundary cases passed
after the fixes. Independent review found no remaining material findings.

A real isolated native session connected successfully with voice=maple and version=v3;
the request explicitly carried Maple. See output/voice-selection-live.json. No user
audio, business tools, merchant order, payment or printer operation was sent.
This verifies configuration/connection, not an acoustic comparison of all 25 voices.

Final verification: **223 backend/browser tests passed in 54.36 s**; **20 frontend
tests passed**. TypeScript/Vite production build, Ruff lint/format, oxlint and
Prettier passed. Built-browser smoke at 1440/768/375 px reported no browser errors
or axe violations, and preserved shared cart, guest isolation and restart recovery.
Screenshots were inspected; no committed visual baseline or formal Core Web Vitals
benchmark was used. Tests use temporary databases and fake capture.

Started owned Visual pid 32786 and API pid 32832. Both ports 9877/8080 listen;
health is ok and voice_prepared=true. The live voices endpoint returns 25 entries.
A permission-free browser visit to the deployed page confirmed 26 options including
the default, with no page errors. Catalog evidence: output/codex-voice-catalog.json.
No microphone/camera permission, guest controller or business action was opened by
that deployed-page check. Recheck runtime rather than treating these PIDs as permanent.

## Self-evaluation

Accuracy 4/5: runtime catalog, native Maple connection and fixtures verified; all-voice
acoustic comparison unperformed. Completeness 4/5: all supported v3 IDs selectable,
fixed boundary recordings remain. Clarity 5/5: default and deferred selection explicit.
Actionability 5/5: selection lives in the website. Conciseness 5/5: existing media,
controller and prepared-call lifecycle reused. Overall 4.6/5. Next improvement:
verify preferred voices with the user's actual microphone and speakers.
