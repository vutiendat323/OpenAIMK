import { afterEach, expect, it, vi } from 'vitest'
import { boundPetPointer } from './pointerBoundary'

afterEach(() => vi.unstubAllGlobals())

it('keeps nearby tracking but clears it beyond the Pet without swallowing menu events', () => {
  const window = new EventTarget()
  const document = new EventTarget()
  vi.stubGlobal('window', window)
  vi.stubGlobal('document', document)
  const canvas = {
    getBoundingClientRect: () => ({
      x: 20,
      y: 80,
      width: 280,
      height: 570,
      left: 20,
      right: 300,
      top: 80,
      bottom: 650,
      toJSON: () => ({}),
    }),
  }
  // Model Wobnimo 0.2's window tracking and document-leave contract.
  let following = false
  window.addEventListener('pointermove', () => (following = true))
  document.addEventListener('pointerleave', () => (following = false))
  const menuMove = vi.fn()
  const unbind = boundPetPointer(canvas)
  window.addEventListener('pointermove', menuMove)
  const move = (x: number, y: number) =>
    window.dispatchEvent(Object.assign(new Event('pointermove'), { clientX: x, clientY: y }))

  move(280, 300)
  expect(following).toBe(true)
  move(324, 300) // A small margin avoids an abrupt cutoff at the panel edge.
  expect(following).toBe(true)
  for (const [x, y] of [
    [325, 300],
    [-5, 300],
    [160, 55],
    [160, 675],
    [800, 500],
  ]) {
    move(x, y)
    expect(following).toBe(false)
  }
  move(160, 300)
  expect(following).toBe(true)
  window.dispatchEvent(new Event('blur'))
  expect(following).toBe(false)
  expect(menuMove).toHaveBeenCalledTimes(8)

  unbind()
  move(800, 500)
  expect(following).toBe(true)
})
