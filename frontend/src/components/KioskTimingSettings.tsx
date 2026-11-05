import { useEffect, useMemo, useState } from 'react'
import { Button } from './ui/button'
import { api } from '../api'
import { parseTimingInput, timingErrors, timingGroups } from '../kioskTiming'
import type { KioskTimingInfo, TimingField, TimingValues } from '../kioskTiming'
import { usePreferences } from '../usePreferences'

type Drafts = Record<TimingField, string>

const asDrafts = (values: TimingValues) =>
  Object.fromEntries(Object.entries(values).map(([name, value]) => [name, String(value)])) as Drafts

export function KioskTimingSettings() {
  const { t } = usePreferences()
  const [info, setInfo] = useState<KioskTimingInfo | null>(null)
  const [drafts, setDrafts] = useState<Drafts | null>(null)
  // Kept only while this dialog is open; never stored in the browser.
  const [staffCode, setStaffCode] = useState('')
  const [saving, setSaving] = useState(false)
  const [status, setStatus] = useState<{ kind: 'ok' | 'error'; text: string } | null>(null)

  useEffect(() => {
    let active = true
    api
      .kioskTiming()
      .then((result) => {
        if (!active) return
        setInfo(result)
        setDrafts(asDrafts(result.values))
      })
      .catch((error: Error) => {
        if (active) setStatus({ kind: 'error', text: error.message })
      })
    return () => {
      active = false
    }
  }, [])

  const values = useMemo(
    () =>
      drafts &&
      (Object.fromEntries(
        Object.entries(drafts).map(([name, text]) => [name, parseTimingInput(text)]),
      ) as TimingValues),
    [drafts],
  )
  const errors = info && values ? timingErrors(values, info.limits) : {}
  const changed =
    !!info &&
    !!values &&
    (Object.keys(values) as TimingField[]).some((name) => values[name] !== info.values[name])

  if (!info || !drafts || !values) {
    return (
      <p className="settings-hint" role="status">
        {status ? t(status.text) : t('Đang tải…')}
      </p>
    )
  }

  async function save() {
    if (!values || Object.keys(errors).length) return
    setSaving(true)
    setStatus(null)
    try {
      const result = await api.saveKioskTiming(staffCode.trim(), values)
      setInfo(result)
      setDrafts(asDrafts(result.values))
      setStatus({
        kind: 'ok',
        text:
          result.applies === 'now'
            ? 'Đã lưu. Áp dụng ngay cho khách tiếp theo.'
            : 'Đã lưu. Khách hiện tại giữ thiết lập cũ; áp dụng từ khách tiếp theo.',
      })
    } catch (error) {
      setStatus({ kind: 'error', text: (error as Error).message })
    } finally {
      setSaving(false)
    }
  }

  return (
    <form
      className="kiosk-timing"
      onSubmit={(event) => {
        event.preventDefault()
        void save()
      }}
    >
      {timingGroups.map((group) => (
        <fieldset key={group.title} className="kiosk-timing-group">
          <legend>{t(group.title)}</legend>
          {group.fields.map(({ name, label, unit }) => {
            const limit = info.limits[name]
            const error = errors[name]
            const id = 'kiosk-timing-' + name
            return (
              <div key={name} className="settings-row kiosk-timing-row">
                <label htmlFor={id}>
                  {t(label)}
                  <small>
                    {limit.min}–{limit.max} {unit} · {t('mặc định')} {info.defaults[name]} {unit}
                  </small>
                  {error && (
                    <small className="kiosk-timing-error" role="alert">
                      {t(
                        error === 'warning'
                          ? 'Phải nhỏ hơn thời lượng tối đa.'
                          : 'Ngoài giới hạn cho phép.',
                      )}
                    </small>
                  )}
                </label>
                <span className="kiosk-timing-input">
                  <input
                    id={id}
                    type="text"
                    inputMode="decimal"
                    autoComplete="off"
                    aria-invalid={!!error}
                    value={drafts[name]}
                    onChange={(event) => {
                      setStatus(null)
                      setDrafts({ ...drafts, [name]: event.target.value })
                    }}
                  />
                  <span aria-hidden="true">{unit}</span>
                </span>
              </div>
            )
          })}
        </fieldset>
      ))}
      <div className="settings-row kiosk-timing-row">
        <label htmlFor="kiosk-timing-staff">{t('Mã nhân viên')}</label>
        <span className="kiosk-timing-input kiosk-timing-code">
          <input
            id="kiosk-timing-staff"
            type="password"
            autoComplete="off"
            value={staffCode}
            onChange={(event) => setStaffCode(event.target.value)}
          />
        </span>
      </div>
      <p className="settings-hint">
        {t('Thay đổi áp dụng từ khách tiếp theo; khách đang trò chuyện giữ thiết lập cũ.')}
      </p>
      {status && (
        <p
          className={'settings-hint' + (status.kind === 'error' ? ' kiosk-timing-error' : '')}
          role={status.kind === 'error' ? 'alert' : 'status'}
        >
          {t(status.text)}
        </p>
      )}
      <div className="kiosk-timing-actions">
        <Button
          type="button"
          variant="outline"
          onClick={() => {
            setStatus(null)
            setDrafts(asDrafts(info.defaults))
          }}
        >
          {t('Khôi phục mặc định')}
        </Button>
        <Button
          type="submit"
          disabled={saving || !changed || !staffCode.trim() || Object.keys(errors).length > 0}
        >
          {t(saving ? 'Đang lưu…' : 'Lưu')}
        </Button>
      </div>
    </form>
  )
}
