import { usePreferences } from '../usePreferences'
import { useEffect, useState } from 'react'
import { api, money } from '../api'
import type { Payment } from '../types'
import { shownCard } from '../vibratingCard'
import { Button } from './ui/button'

const labels: Record<string, string> = {
  paid: 'Quán đã xác nhận thanh toán thành công.',
  expired: 'QR đã hết hạn. Vui lòng nhờ nhân viên kiểm tra đơn trước khi thanh toán.',
  cancelled: 'Giao dịch đã hủy. Vui lòng liên hệ nhân viên.',
  not_connected: 'Đơn này đang lưu nội bộ, chưa có QR từ hệ thống quán.',
  uncertain: 'Chưa rõ quán đã nhận đơn hay chưa. Nhờ nhân viên kiểm tra trước khi đặt lại.',
  creating: 'Đang chờ hệ thống quán trả thông tin đơn và QR…',
  rejected: 'Hệ thống quán chưa tiếp nhận đơn. Vui lòng nhờ nhân viên kiểm tra.',
  review_required: 'Thông tin đơn hoặc thanh toán cần nhân viên kiểm tra. Chưa thể hiển thị QR.',
  unavailable: 'Chưa cập nhật được thanh toán. Nếu đã chuyển tiền, vui lòng giữ biên lai.',
  order_required: 'Chưa có đơn hàng để hiển thị QR thanh toán.',
}

export function PaymentQr({
  token,
  orderId,
  initialPayment,
  variant = 'default',
  card,
}: {
  token: string
  orderId?: string
  initialPayment?: Payment
  variant?: 'default' | 'checkout'
  card?: number
}) {
  const { t } = usePreferences()
  const [payment, setPayment] = useState<Payment | null>(initialPayment || null)
  const [now, setNow] = useState(() => Date.now())
  const [refreshKey, setRefreshKey] = useState(0)
  useEffect(() => {
    let active = true
    let timer = 0
    let id = orderId
    async function refresh() {
      try {
        if (!id) id = (await api.progress(token)).orders[0]?.id
        const result = id ? await api.payment(token, id) : { status: 'order_required' }
        if (!active) return
        setPayment(result)
        if (
          ['pending', 'creating', 'unavailable'].includes(result.status) ||
          (result.status === 'expired' &&
            result.expires_at &&
            Date.now() / 1000 < result.expires_at + 120)
        ) {
          timer = window.setTimeout(() => void refresh(), 3000)
        }
      } catch {
        if (active) {
          setPayment({ status: 'unavailable' })
          timer = window.setTimeout(() => void refresh(), 5000)
        }
      }
    }
    if (initialPayment && refreshKey === 0) {
      if (
        ['pending', 'creating', 'unavailable'].includes(initialPayment.status) ||
        initialPayment.status === 'expired'
      ) {
        timer = window.setTimeout(() => void refresh(), 3000)
      }
    } else {
      void refresh()
    }
    const clock = window.setInterval(() => setNow(Date.now()), 1000)
    return () => {
      active = false
      clearTimeout(timer)
      clearInterval(clock)
    }
  }, [token, orderId, refreshKey, initialPayment])
  const remaining = payment?.expires_at
    ? Math.max(0, Math.ceil(payment.expires_at - now / 1000))
    : null
  const status = payment?.status === 'pending' && remaining === 0 ? 'expired' : payment?.status
  const pickupCard = shownCard(card, payment, status ?? '')
  return (
    <section
      className={`payment-qr${status === 'order_required' ? ' payment-qr-empty' : ''}`}
      data-status={status}
      aria-label={t('Thanh toán đơn hàng')}
      aria-live="polite"
    >
      <h3>{t(status === 'paid' ? 'Đã thanh toán' : 'Quét QR thanh toán')}</h3>
      {pickupCard !== null && (
        <div className="payment-card-number" aria-label={t('Thẻ số') + ' ' + pickupCard}>
          {pickupCard}
        </div>
      )}
      {status === 'pending' && payment?.qr_image && (
        <>
          <img
            className="merchant-qr"
            src={payment.qr_image}
            alt={t('Mã QR thanh toán do Trend Coffee cung cấp')}
          />
          <strong>{money(payment.amount_vnd || 0)}</strong>
          {remaining !== null && (
            <p className="payment-expiry">
              {t('Hiệu lực còn')} {Math.floor(remaining / 60)}:
              {String(remaining % 60).padStart(2, '0')}
            </p>
          )}
        </>
      )}
      {payment?.merchant_order_id && (
        <small className="payment-order-id">
          {variant === 'checkout' ? '#' : t('Mã đơn tại quán:') + ' '}
          {payment.merchant_order_id}
        </small>
      )}
      {status !== 'pending' && (
        <p>{t(status ? labels[status] || 'Đang chờ thông tin từ quán.' : 'Đang lấy QR…')}</p>
      )}
      {status &&
        ![
          'paid',
          'creating',
          'order_required',
          'not_connected',
          'uncertain',
          'rejected',
          'pending',
        ].includes(status) && (
          <Button variant="outline" onClick={() => setRefreshKey((value) => value + 1)}>
            {t('Cập nhật thanh toán')}
          </Button>
        )}
    </section>
  )
}
