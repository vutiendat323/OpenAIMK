# Voice integration self-evaluation

Overall **4.0/5**. Engineering checks passed; field acceptance is explicitly separate.

| Axis | Score | Evidence and improvement |
| --- | --- | --- |
| Accuracy | 4 | 79 backend, 100 Visual and 9 frontend tests; native synthetic menu-tool call and real-model rejection verified. Validate recognition with real customers before claiming field accuracy. |
| Completeness | 4 | Camera/session/Fusion/native transport/cart/quote/payment-status/cleanup implemented. Physical PAD, lip sync, overlap/TSE and camera calibration remain field checks. |
| Clarity | 4 | README and workflow specify ports, model setup, state boundaries and limitations. A short operator walkthrough at the installed kiosk would improve onboarding. |
| Actionability | 4 | Managed local services and browser controls run; remote tunnel instructions supplied. Operator must grant devices and run physical acceptance. |
| Conciseness | 4 | Final response stays short; detailed evidence lives in files. Workflow is longer because both model setup and state boundaries need reproducible instructions. |

Highest impact improvements: run a consented at-counter acceptance with real camera/microphone; measure representative p95 latency and noisy overlap recognition. Self-check: the implementation and its measured limits are inspectable; no field-quality or bank/POS success is inferred. Deliver the local implementation with these limits.
