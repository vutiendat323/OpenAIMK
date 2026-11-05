import { describe, expect, it } from 'vitest'
import { clampOffset } from './keyboardDrag'

const viewport = { width: 1000, height: 800 }
const base = { left: 80, top: 500, width: 840, height: 250 }

describe('clampOffset', () => {
  it('passes a position that stays on screen through unchanged', () => {
    expect(clampOffset(base, { x: 40, y: -300 }, viewport)).toEqual({ x: 40, y: -300 })
  })

  it('stops the keyboard at each viewport edge', () => {
    expect(clampOffset(base, { x: -500, y: -900 }, viewport)).toEqual({ x: -80, y: -500 })
    expect(clampOffset(base, { x: 500, y: 900 }, viewport)).toEqual({ x: 80, y: 50 })
  })

  it('does not move sideways when the keyboard is as wide as the screen', () => {
    const full = { left: 0, top: 500, width: 1000, height: 250 }
    expect(clampOffset(full, { x: 120, y: 10 }, viewport)).toEqual({ x: 0, y: 10 })
  })

  it('returns no offset when the keyboard is larger than the viewport', () => {
    const huge = { left: 0, top: 0, width: 1200, height: 900 }
    expect(clampOffset(huge, { x: 30, y: 30 }, viewport)).toEqual({ x: 0, y: 0 })
  })
})
