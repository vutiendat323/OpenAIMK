import type { Payment } from './types'

export const CARD_COUNT = 16

/** The pickup card to show in big type (user decision 2026-11-06), or null when the order has
 *  none (orders made before pickup cards). The order's own card wins over the payment's. */
export function shownCard(card?: number | null, payment?: Payment | null): number | null {
  const value = card ?? payment?.vibrating_card
  return typeof value === 'number' && Number.isInteger(value) && value >= 1 && value <= CARD_COUNT
    ? value
    : null
}
