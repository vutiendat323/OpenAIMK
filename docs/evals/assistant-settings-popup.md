# Assistant settings popup — 2026-10-27

The user simplified the separate-settings-page request to a popup and invoked
`karpathy-guidelines`. Moved the existing voice/camera dropdowns and deferred-voice
hint into the existing Radix dialog. A “Cài đặt” button sits below microphone
controls. The microphone buttons remain on the assistant.

Only `AvatarAssistant.tsx` and supporting CSS changed in application source.
No routes, dependencies, backend, voice/camera hooks or persistence behavior
changed. Existing busy/armed guards and handlers remain. The popup explains that
microphone capture must stop before switching camera source. Escape/X close it;
Radix manages focus and returns it to the trigger.

Witnessed the browser regression fail with two inline dropdowns before the fix.
Three responsive cases now verify no inline selectors, popup choices retained
after closing/reopening, cart preservation, saved voice after reload, Escape/X,
focus restoration and no horizontal overflow. Existing six browser capture/voice
boundary cases now use the popup and retain their device capture, next-guest
voice, greeting/farewell and disarm assertions. Independent review found no
material findings.

Final verification: **279 backend/browser tests passed in 78.80 s**, plus
**21 frontend tests**, build, lint, formatting and patch whitespace checks.
Evidence: `output/assistant-settings-pytest.txt` and
`output/assistant-settings-{1440,768,375}.png`. Runtime evidence is in
`output/assistant-settings-runtime.json`. Services need no restart for this
frontend change; existing tabs need reload. No real orders, payments or new
print requests were created by validation.

| Self-evaluation | Score | Evidence / improvement |
| --- | --- | --- |
| Accuracy | 4 | Original handlers/guards retained; browser integration verifies behavior. Physical device behavior still depends on existing capture code. |
| Completeness | 4 | Both requested selectors moved, microphone retained; changing camera while armed still requires closing the popup and turning off the microphone. |
| Clarity | 4 | Labeled fields and disabled-camera hint; the settings trigger adds one small control below the microphone. |
| Actionability | 4 | Built assets served without restart; users must reload existing tabs. |
| Conciseness | 4 | Two application files, shared dialog, no new hooks/dependencies/routes; the shared accessible dialog adds bundled UI code. |

Overall 4.0/5. Self-check: this is the requested small popup, with the existing
voice/camera behavior preserved. Additional settings remain outside this change.
