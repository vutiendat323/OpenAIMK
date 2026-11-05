// Dragging the on-screen keyboard: the offset is kept inside the viewport so the keyboard
// (and its drag handle) can never be pushed out of reach.

export type Offset = { x: number; y: number }
export type Box = { left: number; top: number; width: number; height: number }
export type Viewport = { width: number; height: number }

export const NO_OFFSET: Offset = { x: 0, y: 0 }

const clamp = (value: number, low: number, high: number) =>
  low > high ? 0 : Math.min(Math.max(value, low), high)

/** `base` is the keyboard's box with no offset applied; returns the offset kept on screen. */
export function clampOffset(base: Box, wanted: Offset, viewport: Viewport): Offset {
  return {
    x: clamp(wanted.x, -base.left, viewport.width - base.width - base.left),
    y: clamp(wanted.y, -base.top, viewport.height - base.height - base.top),
  }
}
