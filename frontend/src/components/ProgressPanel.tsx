import { usePreferences } from '../usePreferences'
import { useCallback, useEffect, useRef, useState } from 'react'
import { ChevronDown } from 'lucide-react'
import { api, money } from '../api'
import { OrderQrSvg } from './OrderQrSvg'
import type { ImageMap, Progress } from '../types'

const errorText = (error: unknown) =>
  error instanceof Error ? error.message : 'Chưa xử lý được yêu cầu.'
const statusLabels: Record<string, string> = {
  pending_acceptance: 'Chờ tiếp nhận',
  accepted: 'Đã tiếp nhận',
  preparing: 'Đang chuẩn bị',
  ready: 'Sẵn sàng',
  completed: 'Hoàn tất',
  cancelled: 'Đã hủy',
  unverified: 'Chưa xác minh',
  paid: 'Đã xác minh thanh toán',
  unpaid: 'Chưa thanh toán',
  requested: 'Chờ kiểm tra',
  acknowledged: 'Đã tiếp nhận',
  resolved: 'Đã xử lý',
}

function formatOrderDate(isoString?: string, lang = 'vi'): string {
  if (!isoString) return ''
  try {
    const d = new Date(isoString)
    if (isNaN(d.getTime())) return ''
    if (lang === 'vi') {
      const month = d.getMonth() + 1
      const day = d.getDate()
      return `ĐÃ ĐẶT VÀO THG ${month} ${day}`
    } else {
      const months = [
        'JAN',
        'FEB',
        'MAR',
        'APR',
        'MAY',
        'JUN',
        'JUL',
        'AUG',
        'SEP',
        'OCT',
        'NOV',
        'DEC',
      ]
      return `ORDERED ON ${months[d.getMonth()]} ${d.getDate()}`
    }
  } catch {
    return ''
  }
}

export function ProgressPanel({
  open,
  token,
  images: _images = {},
}: {
  open: boolean
  token: string
  images?: ImageMap
}) {
  const { language, t } = usePreferences()
  const [progress, setProgress] = useState<Progress | null>(null)
  const [error, setError] = useState('')
  const live = useRef(true)
  const lock = useRef(false)
  useEffect(
    () => () => {
      live.current = false
    },
    [],
  )
  const refresh = useCallback(async () => {
    if (lock.current) return
    lock.current = true
    try {
      const result = await api.progress(token)
      if (live.current) {
        setProgress(result)
        setError('')
        for (const ord of result.orders) {
          if (ord.merchant && !ord.payment?.qr_image) {
            void api
              .payment(token, ord.id)
              .then((pmt) => {
                if (live.current && pmt.qr_image) {
                  setProgress((prev) => {
                    if (!prev) return prev
                    return {
                      ...prev,
                      orders: prev.orders.map((o) =>
                        o.id === ord.id ? { ...o, payment: { ...o.payment, ...pmt } } : o,
                      ),
                    }
                  })
                }
              })
              .catch(() => {})
          }
        }
      }
    } catch (error) {
      if (live.current) setError(errorText(error))
    } finally {
      lock.current = false
    }
  }, [token])
  useEffect(() => {
    if (!open) return
    void Promise.resolve().then(refresh)
    const timer = window.setInterval(() => void refresh(), 15000)
    return () => window.clearInterval(timer)
  }, [open, refresh]) // token is fixed for this guest; component remounts at reset
  return (
    <section
      className="service-panel progress-panel"
      hidden={!open}
      aria-labelledby="progress-panel-title"
    >
      <header className="service-panel-header kfc-service-panel-header">
        <h2 id="progress-panel-title" className="kfc-orders-title">
          {t('CÁC ĐƠN HÀNG ĐÃ ĐẶT')}
        </h2>
      </header>
      <div className="service-body">
        {error && (
          <p role="alert" className="form-error">
            {t(error)}
          </p>
        )}
        {progress && progress.orders.length === 0 && progress.handoffs.length === 0 && (
          <div className="progress-empty">
            <h3>{t('Chưa có yêu cầu nào')}</h3>
            <p>{t('Chọn món bạn thích để bắt đầu nhé.')}</p>
          </div>
        )}
        {progress?.orders.map((order, orderIdx) => {
          const dateLabel =
            formatOrderDate(order.created_at, language) ||
            `${t('ĐÃ ĐẶT VÀO')} #${order.id.slice(0, 8).toUpperCase()}`

          return (
            <details className="kfc-order-card progress-card" key={order.id} open={orderIdx === 0}>
              <summary className="kfc-order-summary">
                <span className="kfc-order-summary-title">{dateLabel}</span>
                <div className="kfc-order-summary-meta">
                  <strong className="kfc-order-total-vnd">{money(order.total_vnd)}</strong>
                  <ChevronDown className="kfc-chevron" size={18} />
                </div>
              </summary>
              <div className="kfc-order-content">
                <div className="kfc-order-body">
                  <div className="kfc-order-photo kfc-order-qr">
                    {order.payment?.qr_image ? (
                      <img
                        src={order.payment.qr_image}
                        alt={t('Mã QR đơn hàng')}
                        className="kfc-order-qr-img"
                      />
                    ) : (
                      <OrderQrSvg text={order.id.slice(0, 8).toUpperCase()} />
                    )}
                  </div>
                  <div className="kfc-order-items">
                    {order.lines.map((line, index) => {
                      const optionsList = line.options
                        ? Object.entries(line.options)
                            .map(([, val]) => val)
                            .filter(Boolean)
                        : []

                      return (
                        <div className="kfc-order-line progress-line" key={index}>
                          <div className="kfc-order-line-info">
                            <h4 className="kfc-order-line-title">
                              {line.quantity}x {line.name} {money(line.subtotal_vnd)}
                            </h4>
                            {optionsList.length > 0 && (
                              <div className="kfc-order-line-options">
                                {optionsList.map((opt, oIdx) => (
                                  <p key={oIdx} className="kfc-order-option-item">
                                    {opt}
                                  </p>
                                ))}
                              </div>
                            )}
                            {line.note && <p className="kfc-order-line-note">{line.note}</p>}
                          </div>
                        </div>
                      )
                    })}
                  </div>
                </div>

                <div
                  style={{
                    position: 'absolute',
                    width: 1,
                    height: 1,
                    overflow: 'hidden',
                    opacity: 0.01,
                    pointerEvents: 'none',
                  }}
                  aria-hidden="true"
                >
                  <span>{t(statusLabels[order.status] || order.status)}</span>
                  <span>
                    {t('Thanh toán:')}{' '}
                    {t(statusLabels[order.payment_status] || order.payment_status)}
                  </span>
                </div>
              </div>
            </details>
          )
        })}
        {progress?.handoffs.map((handoff) => (
          <article key={handoff.id} className="progress-card kfc-handoff-card">
            <div className="progress-card-title">
              <strong>{t('Lời nhắn hỗ trợ')}</strong>
              <span className="kfc-status-pill">
                {t(statusLabels[handoff.status] || handoff.status)}
              </span>
            </div>
            <p>{handoff.reason}</p>
            <small className="muted">
              {t(handoff.delivered ? 'Nhân viên nội bộ đã nhận' : 'Chưa chuyển đến quán')}
            </small>
          </article>
        ))}
      </div>
    </section>
  )
}
