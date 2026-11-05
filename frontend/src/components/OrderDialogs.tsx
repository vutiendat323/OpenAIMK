import { usePreferences } from '../usePreferences'
import { Minus, Plus, X } from 'lucide-react'
import { useRef, useState } from 'react'
import { Button } from '@/components/ui/button'
import { Dialog, DialogClose, DialogContent, DialogDescription, DialogTitle } from './ui/dialog'
import { ProductImage } from './ProductImage'
import { PaymentQr } from './PaymentQr'
import { money } from '../api'
import type { ImageMap, MenuItem, Options, Order } from '../types'

export function ProductPanel({
  item,
  images,
  onClose,
  onAdd,
  locked = false,
}: {
  item: MenuItem | null
  locked?: boolean
  images: ImageMap
  onClose: () => void
  onAdd: (item: MenuItem, quantity: number, options: Options) => void
}) {
  const { t } = usePreferences()
  const [quantity, setQuantity] = useState(1)
  const [options, setOptions] = useState<Options>({})
  const opener = useRef(document.activeElement)
  if (!item) return null
  return (
    <Dialog
      open={!!item}
      onOpenChange={(open) => {
        if (!open) onClose()
      }}
    >
      <DialogContent
        className="product-dialog product-panel"
        overlayClassName="product-overlay"
        showCloseButton={false}
        aria-describedby={item.description ? 'product-description' : undefined}
        onCloseAutoFocus={(event) => {
          event.preventDefault()
          if (opener.current instanceof HTMLElement && opener.current.isConnected)
            opener.current.focus()
        }}
      >
        <div className="product-dialog-toolbar">
          <DialogClose asChild>
            <Button
              variant="ghost"
              size="icon"
              aria-label={t('Đóng')}
              className="product-close border-0 shadow-none focus-visible:border-transparent focus-visible:ring-0"
            >
              <X />
            </Button>
          </DialogClose>
        </div>
        <div className="product-large">
          <ProductImage item={item} images={images} eager />
        </div>
        <div className="product-information">
          <header>
            <div className="product-title-price">
              <DialogTitle>{item.name}</DialogTitle>
              <div className="product-detail-price">{money(item.price_vnd)}</div>
            </div>
            {item.description && (
              <DialogDescription id="product-description">{item.description}</DialogDescription>
            )}
          </header>
          {Object.entries(item.options).map(([key, values]) => (
            <fieldset className="product-options" key={key}>
              <legend>{key === 'size' ? t('Kích cỡ') : key}</legend>
              <div>
                {values.map((value) => (
                  <Button
                    key={value}
                    disabled={locked}
                    variant="outline"
                    aria-pressed={(options[key] || values[0]) === value}
                    onClick={() => setOptions({ ...options, [key]: value })}
                  >
                    {value}
                  </Button>
                ))}
              </div>
            </fieldset>
          ))}
          <div className="product-add">
            <div className="product-quantity-row">
              <span className="product-quantity-label">{t('Số lượng')}</span>
              <div className="stepper">
                <Button
                  variant="ghost"
                  size="icon"
                  aria-label={t('Giảm số lượng')}
                  disabled={locked || quantity === 1}
                  onClick={() => setQuantity(quantity - 1)}
                >
                  <Minus />
                </Button>
                <span role="status" aria-label={t('Số lượng')}>
                  {quantity}
                </span>
                <Button
                  variant="ghost"
                  size="icon"
                  aria-label={t('Tăng số lượng')}
                  disabled={locked || quantity === 100}
                  onClick={() => setQuantity(quantity + 1)}
                >
                  <Plus />
                </Button>
              </div>
            </div>
            <Button
              className="primary-action"
              disabled={locked || item.stale || item.availability === 'sold_out'}
              onClick={() => {
                onAdd(
                  item,
                  quantity,
                  Object.fromEntries(
                    Object.entries(item.options).map(([key, values]) => [
                      key,
                      options[key] || values[0],
                    ]),
                  ),
                )
                onClose()
              }}
            >
              {t('Thêm vào giỏ')} ({money(item.price_vnd * quantity)})
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  )
}

export function CheckoutResult({
  order,
  token,
  onProgress,
}: {
  order: Order | null
  token: string
  onProgress: () => void
}) {
  const { t } = usePreferences()
  if (!order) return null
  return (
    <section className="checkout-result" aria-labelledby="checkout-result-title">
      <header>
        <h2 id="checkout-result-title">THANK YOU!</h2>
        {!order.merchant && <p>{t('Đã lưu yêu cầu của bạn!')}</p>}
      </header>
      {order.merchant && (
        <PaymentQr
          key={token + order.id}
          token={token}
          orderId={order.id}
          initialPayment={order.payment}
          variant="checkout"
        />
      )}
      <section className="checkout-result-details" aria-labelledby="checkout-summary-title">
        <h3 id="checkout-summary-title">{t('Tóm tắt đơn hàng:')}</h3>
        <div className="checkout-lines">
          {order.lines.map((line, index) => (
            <div key={index}>
              <span>
                {line.quantity}x {line.name}
                {line.note ? (
                  <small className="checkout-line-note">
                    {t('Ghi chú:')} {line.note}
                  </small>
                ) : null}
              </span>
              <strong>{money(line.subtotal_vnd)}</strong>
            </div>
          ))}
        </div>
        {order.order_note && (
          <p className="checkout-order-note">
            {t('Ghi chú cho đơn:')} {order.order_note}
          </p>
        )}
        {!order.merchant && (
          <div className="checkout-subtotal">
            <span>{t('Tạm tính')}</span>
            <strong>{money(order.total_vnd)}</strong>
          </div>
        )}
      </section>
      <Button
        className="checkout-check"
        aria-label={'CHECK · ' + t('Xem tiến độ yêu cầu')}
        onClick={onProgress}
      >
        CHECK
      </Button>
    </section>
  )
}
