# Kiosk Virtual Keyboard Implementation Plan

**Goal:** Provide an on-screen touch virtual keyboard for customers when interacting with any text input or textarea on the kiosk (menu search, line item notes, order notes, table number) since the kiosk hardware does not have a physical keyboard.

**Architecture:**
- Create `frontend/src/components/VirtualKeyboard.tsx` as a global touch keyboard component rendered at the root of `App.tsx`.
- Support automatic detection of focused text inputs (`input[type="text"]`, `input:not([type])`, `textarea`) via global document event listeners (`focusin`, `pointerdown`).
- Direct synthetic event dispatching (`Object.getOwnPropertyDescriptor(prototype, 'value').set` + `dispatchEvent(new Event('input'))`) so all existing React state, filters, and reducers in `App.tsx` and `Cart.tsx` update seamlessly without breaking existing contracts.
- Support Vietnamese text input via:
  1. Dedicated Vietnamese letters row (`ă, â, đ, ê, ô, ơ, ư`) and tone mark keys (`´, \`, ˀ, ~, .`).
  2. Telex rules engine (`applyTelex`) for standard typing (`as` -> `á`, `aa` -> `â`, `dd` -> `đ`, etc.).
  3. Context-sensitive Quick Chips (1-touch note suggestions: `Ít đá`, `Không đường`, `Nhiều đá`, `Nóng`, `Mang về`... and search suggestions: `Cà phê`, `Trà`, `Matcha`...).
- Specialized Numpad layout when focusing table number (`#table-label`).
- Touch-friendly sizing (minimum 48px key height, tactile feedback, focus prevention so active input remains active).

**Files:**
- `frontend/src/components/virtualKeyboardTelex.ts`: Pure Vietnamese Telex and tone accent helper functions with unit tests.
- `frontend/src/components/virtualKeyboardTelex.test.ts`: Vitest unit tests for Telex transformation and tone application.
- `frontend/src/components/VirtualKeyboard.tsx`: Keyboard logic, layout definitions, and touch handlers.
- `frontend/src/components/VirtualKeyboard.test.tsx`: Component unit tests.
- `frontend/src/App.tsx`: Mount `<VirtualKeyboard />` at the root layout.
- `frontend/src/index.css`: Virtual keyboard styling, slide-up animations, dark slate theme, responsive layout, and key states.

---

### Task 1: Vietnamese Telex and Tone Helpers
- [x] Create `frontend/src/components/virtualKeyboardTelex.ts`
- [x] Create `frontend/src/components/virtualKeyboardTelex.test.ts`
- [x] Run `npm --prefix frontend test` to verify

### Task 2: VirtualKeyboard Component
- [x] Create `frontend/src/components/VirtualKeyboard.tsx`
- [x] Create `frontend/src/components/VirtualKeyboard.test.tsx`
- [x] Run `npm --prefix frontend test` to verify

### Task 3: CSS Styles and Responsiveness
- [x] Add `.kiosk-virtual-keyboard` styles in `frontend/src/index.css`

### Task 4: Integration in App.tsx and Verification
- [x] Mount `<VirtualKeyboard />` in `frontend/src/App.tsx`
- [x] Run `npm --prefix frontend run typecheck && npm --prefix frontend run lint && npm --prefix frontend test`
- [x] Run `npm --prefix frontend run build` to update static production assets
- [x] Run browser tests
