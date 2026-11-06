import { expect, it } from 'vitest'
import { shownCard } from './vibratingCard'

it('shows the order card first, then the card the payment reports', () => {
  expect(shownCard(7, null)).toBe(7)
  expect(shownCard(undefined, { status: 'pending', vibrating_card: 3 })).toBe(3)
  expect(shownCard(5, { status: 'paid', vibrating_card: 5 })).toBe(5)
})

it('shows nothing for orders made before pickup cards', () => {
  expect(shownCard(undefined, { status: 'pending' })).toBeNull()
  expect(shownCard(undefined, { status: 'pending', vibrating_card: null })).toBeNull()
  expect(shownCard(undefined, null)).toBeNull()
})

it('shows only real card numbers 1 to 16', () => {
  expect(shownCard(0, null)).toBeNull()
  expect(shownCard(17, null)).toBeNull()
  expect(shownCard(2.5, null)).toBeNull()
  expect(shownCard(16, null)).toBe(16)
})

it('shows the card only while the QR is up or once paid', () => {
  const qr = { status: 'pending', qr_image: 'data:image/png;base64,x' }
  expect(shownCard(7, qr, 'pending')).toBe(7)
  expect(shownCard(7, { status: 'paid' }, 'paid')).toBe(7)
  for (const status of ['creating', 'rejected', 'uncertain', 'review_required', 'cancelled'])
    expect(shownCard(7, { status }, status)).toBeNull()
  expect(shownCard(7, { status: 'pending', qr_image: null }, 'pending')).toBeNull()
})
