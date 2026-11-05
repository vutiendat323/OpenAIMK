import { describe, expect, it } from 'vitest'
import { initialNavigation, navigationReducer } from './navigation'

describe('kiosk navigation', () => {
  it('returns to menu by closing the sidebar', () => {
    expect(navigationReducer(initialNavigation, 'menu')).toEqual({ open: false, view: 'cart' })
  })
  it.each(['cart', 'payment', 'progress'] as const)('reopens the requested %s section', (view) => {
    const closed = navigationReducer(initialNavigation, 'menu')
    expect(navigationReducer(closed, view)).toEqual({ open: true, view })
  })
  it('toggles without losing the selected section and resets for the next guest', () => {
    const orders = navigationReducer(initialNavigation, 'progress')
    expect(navigationReducer(orders, 'toggle')).toEqual({ open: false, view: 'progress' })
    expect(navigationReducer(orders, 'reset')).toEqual(initialNavigation)
  })
})
