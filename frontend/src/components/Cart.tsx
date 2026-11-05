import { usePreferences } from '../usePreferences'
import { Check, Minus, Plus } from 'lucide-react'
import { Select } from 'radix-ui'
import { getNonce } from 'get-nonce'
import { useEffect, useRef, useState } from 'react'
import type { ChangeEvent } from 'react'
import type { Dispatch } from 'react'
import { Button } from '@/components/ui/button'
import type { Action, KioskState } from '../state'
import { money } from '../api'
import { ProductImage } from './ProductImage'
import type { Fulfillment, ImageMap } from '../types'
import cartBucket from '../../Category/green-open-bucket-no-drumstick.png'

function NoteField({
  label,
  value,
  multiline = false,
  maxLength,
  placeholder,
  disabled = false,
  onChange,
}: {
  label: string
  value: string
  multiline?: boolean
  maxLength: number
  placeholder: string
  disabled?: boolean
  onChange: (value: string) => void
}) {
  const [draft, setDraft] = useState(value)
  const draftRef = useRef(value)
  const focused = useRef(false)
  const awaitingEcho = useRef(false)

  useEffect(() => {
    if (awaitingEcho.current) {
      if (value === draftRef.current) awaitingEcho.current = false
      return
    }
    if (!focused.current) {
      draftRef.current = value
      setDraft(value)
    }
  }, [value])

  const change = (next: string) => {
    draftRef.current = next
    awaitingEcho.current = true
    setDraft(next)
    onChange(next)
  }
  const common = {
    'aria-label': label,
    maxLength,
    placeholder,
    disabled,
    value: draft,
    autoComplete: 'off',
    autoCorrect: 'off',
    autoCapitalize: 'off',
    spellCheck: false,
    onFocus: () => {
      focused.current = true
    },
    onBlur: () => {
      focused.current = false
      if (!awaitingEcho.current) {
        draftRef.current = value
        setDraft(value)
      }
    },
    onChange: (event: ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) =>
      change(event.target.value),
  }
  return multiline ? <textarea {...common} rows={2} /> : <input {...common} type="text" />
}

export function Cart({
  state,
  dispatch,
  images,
  submitting,
  onFulfillment,
  tables,
  tablesLoading,
  merchantConnected,
}: {
  state: KioskState
  dispatch: Dispatch<Action>
  images: ImageMap
  submitting: boolean
  onFulfillment: (value: Fulfillment) => void
  tables: { id: string; name: string; status: string; available: boolean }[]
  tablesLoading: boolean
  merchantConnected: boolean
}) {
  const { t } = usePreferences()
  const [tableOpen, setTableOpen] = useState(false)
  const [editingLine, setEditingLine] = useState<string | null>(null)
  const count = state.cart.reduce((sum, line) => sum + line.quantity, 0)
  const total = state.cart.reduce((sum, line) => sum + line.quantity * line.item.price_vnd, 0)
  return (
    <section className="order-card kfc-cart" aria-labelledby="cart-heading">
      <header className="kfc-cart-header">
        <div>
          <h2 id="cart-heading">{t('Giỏ hàng của tôi')}</h2>
          <Button
            variant="outline"
            className="kfc-remove-all"
            disabled={submitting || !count}
            onClick={() => dispatch({ type: 'clear' })}
          >
            {t('Xóa tất cả')}
          </Button>
        </div>
        <div className="kfc-cart-header-actions">
          <Select.Root
            value={state.tableLabel}
            open={tableOpen}
            onOpenChange={(open) => {
              setTableOpen(open)
              if (open) onFulfillment('at_table')
            }}
            disabled={submitting}
            onValueChange={(value) => dispatch({ type: 'table', value })}
          >
            <div
              id="fulfillment"
              tabIndex={-1}
              className="order-mode kfc-cart-controls"
              role="group"
              aria-label={t('Hình thức phục vụ')}
            >
              {(['takeaway', 'at_table'] as const).map((mode) => {
                const button = (
                  <Button
                    key={mode}
                    variant="outline"
                    className="kfc-cart-mode"
                    aria-label={t(mode === 'takeaway' ? 'Mang đi' : 'Tại quán')}
                    aria-pressed={state.fulfillment === mode}
                    aria-description={
                      mode === 'at_table' && state.tableLabel
                        ? t('Bàn') + ' ' + state.tableLabel
                        : undefined
                    }
                    disabled={submitting}
                    onClick={
                      mode === 'at_table'
                        ? undefined
                        : () => {
                            setTableOpen(false)
                            onFulfillment(mode)
                          }
                    }
                  >
                    {t(mode === 'takeaway' ? 'Mang đi' : 'Tại quán')}
                  </Button>
                )
                return mode === 'at_table' ? (
                  <Select.Trigger key={mode} id="table-label" asChild>
                    {button}
                  </Select.Trigger>
                ) : (
                  button
                )
              })}
            </div>
            <Select.Portal>
              <Select.Content
                className="cart-table-menu"
                position="popper"
                align="end"
                sideOffset={5}
                collisionPadding={12}
              >
                <Select.Viewport className="cart-table-viewport" nonce={getNonce()}>
                  {tablesLoading ? (
                    <div className="cart-table-status" role="status">
                      {t('Đang tải bàn…')}
                    </div>
                  ) : (
                    tables.map((table) => (
                      <Select.Item
                        className="cart-table-option"
                        key={table.id}
                        value={table.name}
                        disabled={!table.available}
                      >
                        <Select.ItemText>
                          {t('Bàn') + ' ' + table.name} -{' '}
                          {t(
                            table.available
                              ? 'Bàn trống'
                              : table.status === 'reserved'
                                ? 'Đã đặt'
                                : 'Không xác định',
                          )}
                        </Select.ItemText>
                        <Select.ItemIndicator>
                          <Check size={14} />
                        </Select.ItemIndicator>
                      </Select.Item>
                    ))
                  )}
                  {!tablesLoading && !tables.length && (
                    <div className="cart-table-status">
                      {t(
                        merchantConnected
                          ? 'Chưa có dữ liệu bàn để chọn. Bạn thử lại hoặc chọn mang đi nhé.'
                          : 'Chưa kết nối danh sách bàn. Bạn có thể chọn mang đi.',
                      )}
                    </div>
                  )}
                </Select.Viewport>
              </Select.Content>
            </Select.Portal>
          </Select.Root>
        </div>
      </header>
      <div className="kfc-cart-summary">
        <div>
          <h2>{t('Tổng số món')}</h2>
          <span>{t('Tạm tính')}</span>
        </div>
        <div className="kfc-cart-summary-value">
          <span className="checkout-dock-bag cart-bucket">
            <img src={cartBucket} alt="" draggable={false} />
            <span className="checkout-dock-count" aria-label={t('Tổng số món')}>
              {count}
            </span>
          </span>
          <strong>{money(total)}</strong>
        </div>
      </div>
      <div className="order-lines kfc-cart-lines">
        {!count && <p className="kfc-cart-empty">{t('Chưa có món trong giỏ.')}</p>}
        {state.cart.map((line) => (
          <article className="cart-line kfc-cart-line" key={line.key}>
            <div className="kfc-cart-photo">
              <ProductImage item={line.item} images={images} />
            </div>
            <div className="kfc-cart-line-info">
              <h3>{line.item.name}</h3>
              {line.note && <p className="kfc-cart-note">{line.note}</p>}
              <div className="kfc-cart-line-actions">
                <Button
                  className="kfc-cart-customize"
                  aria-expanded={editingLine === line.key}
                  aria-controls={'cart-editor-' + line.key}
                  onClick={() => setEditingLine(editingLine === line.key ? null : line.key)}
                >
                  {t('Tùy chỉnh')}
                </Button>
                <Button
                  variant="outline"
                  className="kfc-remove-item"
                  aria-label={t('Bỏ') + ' ' + line.item.name}
                  disabled={submitting}
                  onClick={() => dispatch({ type: 'remove', key: line.key })}
                >
                  {t('Bỏ món')}
                </Button>
              </div>
            </div>
            {editingLine === line.key && (
              <div className="kfc-cart-editor" id={'cart-editor-' + line.key}>
                <p>{Object.values(line.options).join(' · ')}</p>
                <label className="cart-note-label">
                  NOTE
                  <NoteField
                    label={t('Ghi chú cho') + ' ' + line.item.name}
                    multiline
                    maxLength={300}
                    placeholder={t('Ví dụ: ít đá…')}
                    value={line.note || ''}
                    disabled={submitting}
                    onChange={(value) => dispatch({ type: 'line_note', key: line.key, value })}
                  />
                </label>
              </div>
            )}
            <div className="kfc-cart-quantity">
              <Button
                variant="ghost"
                size="icon"
                aria-label={t('Giảm') + ' ' + line.item.name}
                disabled={submitting}
                onClick={() =>
                  dispatch(
                    line.quantity === 1
                      ? { type: 'remove', key: line.key }
                      : { type: 'quantity', key: line.key, value: line.quantity - 1 },
                  )
                }
              >
                <Minus />
              </Button>
              <span aria-label={t('Số lượng') + ' ' + line.item.name}>{line.quantity}</span>
              <Button
                variant="ghost"
                size="icon"
                aria-label={t('Tăng') + ' ' + line.item.name}
                disabled={submitting || count >= 100}
                onClick={() =>
                  dispatch({ type: 'quantity', key: line.key, value: line.quantity + 1 })
                }
              >
                <Plus />
              </Button>
            </div>
            <strong className="kfc-cart-line-total">
              {money(line.quantity * line.item.price_vnd)}
            </strong>
          </article>
        ))}
        <div className="kfc-cart-order-note">
          <label className="cart-note-label">
            NOTE
            <NoteField
              label={t('Ghi chú cho đơn hàng')}
              maxLength={1000}
              multiline
              placeholder={t('Lời nhắn cho quán…')}
              value={state.orderNote}
              disabled={submitting || !count}
              onChange={(value) => dispatch({ type: 'order_note', value })}
            />
          </label>
        </div>
      </div>
    </section>
  )
}
