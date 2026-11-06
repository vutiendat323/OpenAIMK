import type { Payment } from './types'

export const CARD_COUNT = 16

/** The pickup card to show in big type (user decision 2026-11-06), or null when the order has
 *  none (orders made before pickup cards). The order's own card wins over the payment's.
 *  With a panel status, it shows only while the QR is up or once paid: a rejected or
 *  uncertain order has no card for the guest to wait on. */
export function shownCard(
  card?: number | null,
  payment?: Payment | null,
  status?: string,
): number | null {
  if (status !== undefined && !(status === 'paid' || (status === 'pending' && payment?.qr_image)))
    return null
  const value = card ?? payment?.vibrating_card
  return typeof value === 'number' && Number.isInteger(value) && value >= 1 && value <= CARD_COUNT
    ? value
    : null
}
