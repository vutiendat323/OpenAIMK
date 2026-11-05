import { describe, expect, it } from 'vitest'
import { initialState, reducer } from './state'
import type { MenuItem, Quote } from './types'

const item: MenuItem = {
  id: 'coffee',
  name: 'Cà phê sữa',
  price_vnd: 35000,
  options: { size: ['tiêu chuẩn'] },
  category: 'cà phê',
  variant_name: 'tiêu chuẩn',
  availability: 'unknown',
  stale: false,
  source_url: 'https://trendcoffee.net/menu',
  verified_at: '2026-10-16T15:00:00Z',
}
const quote = {
  id: 'q1',
  confirmation_token: 'opaque',
  lines: [],
  total_vnd: 70000,
  fulfillment: 'takeaway',
  table_label: null,
  notice: 'Chờ xác nhận',
  expires_at: Date.now() / 1000 + 300,
} as Quote

describe('kiosk order lifecycle', () => {
  it('combines identical cups but keeps distinct options separate', () => {
    let s = reducer(initialState(), {
      type: 'add',
      item,
      quantity: 1,
      options: { size: 'tiêu chuẩn' },
    })
    s = reducer(s, { type: 'add', item, quantity: 2, options: { size: 'tiêu chuẩn' } })
    expect(s.cart).toHaveLength(1)
    expect(s.cart[0].quantity).toBe(3)
    s = reducer(s, { type: 'add', item, quantity: 1, options: { size: 'L' } })
    expect(s.cart).toHaveLength(2)
  })
  it('keeps the same drink with different notes separate and note edits invalidate the quote', () => {
    let s = reducer(initialState(), { type: 'add', item, quantity: 1, options: {} })
    s = reducer(s, { type: 'line_note', key: s.cart[0].key, value: 'less ice' })
    s = reducer(s, { type: 'add', item, quantity: 1, options: {} })
    expect(s.cart).toHaveLength(2)
    expect(s.cart.map((line) => line.note)).toEqual(['less ice', ''])
    s = reducer(s, { type: 'quote', quote, revision: s.revision })
    const key = s.cart[1].key
    s = reducer(s, { type: 'line_note', key, value: 'no sugar' })
    expect(s.cart[1].key).toBe(key)
    expect(s.quote).toBeNull()
    expect(s.revision).toBeGreaterThan(0)
  })
  it('clears whole-order notes between guests and invalidates checkout revision on edits', () => {
    let s = reducer(initialState(), { type: 'order_note', value: 'call when ready ' })
    expect(s.orderNote).toBe('call when ready ')
    s = reducer(s, { type: 'clear' })
    expect(s.orderNote).toBe('')
    s = reducer(s, { type: 'order_note', value: 'call when ready' })
    const beforeReset = s.revision
    s = reducer(s, { type: 'reset' })
    expect(s.orderNote).toBe('')
    expect(s.revision).toBe(beforeReset + 1)
  })
  it('invalidates the quote after quantity, mode, table or removal changes', () => {
    let s = reducer(initialState(), { type: 'add', item, quantity: 1, options: {} })
    s = reducer(s, { type: 'fulfillment', value: 'takeaway' })
    s = reducer(s, { type: 'quote', quote, revision: s.revision })
    expect(s.quote).toBe(quote)
    for (const action of [
      { type: 'quantity', key: s.cart[0].key, value: 2 } as const,
      { type: 'fulfillment', value: 'at_table' } as const,
      { type: 'table', value: 'Bàn 3' } as const,
      { type: 'remove', key: s.cart[0].key } as const,
    ])
      expect(reducer(s, action).quote).toBeNull()
  })
  it('rejects late quote responses for a previous cart revision', () => {
    const s = reducer(initialState(), { type: 'add', item, quantity: 1, options: {} })
    expect(reducer(s, { type: 'quote', quote, revision: s.revision - 1 }).quote).toBeNull()
  })
  it('clears private state between guests and rejects an old quote', () => {
    let s = reducer(initialState(), { type: 'add', item, quantity: 1, options: {} })
    const revision = s.revision
    s = reducer(s, { type: 'reset' })
    expect(s.cart).toEqual([])
    expect(s.fulfillment).toBe('')
    expect(s.tableLabel).toBe('')
    expect(s.quote).toBeNull()
    expect(reducer(s, { type: 'quote', quote, revision }).quote).toBeNull()
  })
  it('never permits zero, decimal, negative, or excessive quantity', () => {
    const s = reducer(initialState(), { type: 'add', item, quantity: 1, options: {} })
    for (const value of [0, -2, 1.5, 101, NaN]) {
      expect(reducer(s, { type: 'quantity', key: s.cart[0].key, value }).cart[0].quantity).toBe(1)
    }
  })
})

it('hydrates the shared voice cart without resurrecting an older revision', () => {
  const current = { ...initialState(), revision: 7 }
  const server = {
    ...initialState(),
    revision: 8,
    cart: [{ key: 'coffee[]', item, quantity: 3, options: {} }],
  }
  const next = reducer(current, { type: 'hydrate', state: server })
  expect(next.cart[0].quantity).toBe(3)
  expect(reducer(next, { type: 'hydrate', state: { ...server, revision: 6 } })).toBe(next)
})
