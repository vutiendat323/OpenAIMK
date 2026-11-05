# Whole-menu intent reasoning — 2026-10-20

The reported input `trái cây` previously returned zero search items from a 51-item catalog. The agent now receives the whole current catalog at native thread/realtime startup, reasons over names/descriptions/categories/prices, then displays its chosen real IDs. Uncertain name-search results also return the full catalog for review. No fruit-keyword expansion table, embeddings, additional model provider or paid-order action was added.

## Verification

- Four regression tests failed before implementation and passed after it: whole-catalog fallback, semantic-ID display without text overlap, atomic rejection of invented IDs, and catalog delivery to thread plus voice with cleanup on stop.
- Full Python suite: **179 passed**, latest full run 36.57 seconds. Final menu/MCP focused tests: **13 passed**. Ruff check/format passed.
- Actual native **gpt-6-luna, medium** text turns used the same catalog, prompt, tool schema and `InteractionHost` callback as voice. [Captured results](../../output/menu-semantic-native.json):
  - `trái cây` → Trà nhiệt đới (58,000đ), Trà Ổi Hồng (55,000đ).
  - Fruit drinks, no coffee, below 50,000đ → Cam tươi (45,000đ), Nước dừa (39,000đ), Nước ép các loại (49,000đ) displayed; speech text named only the first two.
  - Each final case used **one display call with item_ids**, zero keyword searches, valid actual catalog IDs, no cart/order mutation, replies within 30 words and at most two named drinks.
  - Total text-turn completion samples were 5.72 and 4.52 seconds; these include full response generation and are not microphone/voice latency measurements or an SLA.
- Isolated real-browser smoke displayed two chosen fruit drinks while the search field said `trái cây`. Existing speech-typo candidates, manual-search reset, guest reset, shared cart and waveform checks passed. Zero browser errors, axe violations or overflow at 1440/768/375. Screenshot: `.runtime/voice-browser/menu-semantic-recommendation.png`.
- Production stack stayed stopped. Live microphone recognition and actual customer recommendations were not exercised; new behavior is loaded on next API/native guest session and MCP host reload.

## Self-evaluation

| Axis | Score | Evidence / improvement |
|---|---:|---|
| Accuracy | 4/5 | Real model chose valid items/prices in two cases; broaden preference evaluations during field use. |
| Completeness | 5/5 | Native catalog context, MCP full-menu guidance, validated ID display and uncertain-search review all cover the reported failure. |
| Clarity | 5/5 | Whole-menu reasoning is distinct from optional name lookup; docs and captured tool calls show the actual path. |
| Actionability | 4/5 | Code and browser behavior verified; stopped runtime/host reload defer live availability. |
| Conciseness | 5/5 | Existing model performs selection; no extra inference service or customer step. |

Overall: **4.6/5**. Remaining improvement: validate diverse live speech preferences after the operator restarts the existing stack. Would the user agree? The agent now reasons from the menu and responds briefly, with no keyword reformulation required.
