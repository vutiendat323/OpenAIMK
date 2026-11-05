// Staff-tuned session boundaries (server: trendcoffee/kiosk_timing.py). Read by anyone,
// changed only with the staff code; they apply from the next guest.

export type TimingField =
  | 'presence_distance_m'
  | 'enter_seconds'
  | 'leave_seconds'
  | 'idle_seconds'
  | 'session_limit_seconds'
  | 'warning_seconds'
export type TimingValues = Record<TimingField, number>
export type KioskTimingInfo = {
  values: TimingValues
  defaults: TimingValues
  limits: Record<TimingField, { min: number; max: number }>
}

export const timingGroups: {
  title: string
  fields: { name: TimingField; label: string; unit: 'm' | 's'; step: number; hint?: string }[]
}[] = [
  {
    title: 'Bắt đầu phiên',
    fields: [
      { name: 'presence_distance_m', label: 'Khoảng cách kích hoạt', unit: 'm', step: 0.05 },
      { name: 'enter_seconds', label: 'Đứng trước camera', unit: 's', step: 0.5 },
    ],
  },
  {
    title: 'Kết thúc phiên',
    fields: [
      { name: 'leave_seconds', label: 'Rời đi bao lâu thì kết thúc', unit: 's', step: 1 },
      { name: 'session_limit_seconds', label: 'Thời lượng tối đa', unit: 's', step: 30 },
      { name: 'warning_seconds', label: 'Cảnh báo trước khi hết giờ', unit: 's', step: 5 },
    ],
  },
  {
    title: 'Nhắc khách',
    fields: [
      {
        name: 'idle_seconds',
        label: 'Hỏi khách sau khi im lặng',
        unit: 's',
        step: 5,
        hint: 'Khách không nói, không chạm, không đổi giỏ trong khoảng này thì Trend hỏi một câu hợp với lúc đó (chọn món, thanh toán, thêm món). Phiên không kết thúc.',
      },
    ],
  },
]

export const DEFAULT_IDLE_SECONDS = 120

/** Parses what staff typed ("1,5" or "1.5"); NaN when it is not a number. */
export function parseTimingInput(text: string) {
  const normalized = text.trim().replace(',', '.')
  return normalized === '' || !/^\d*\.?\d+$|^\d+\.$/.test(normalized) ? NaN : Number(normalized)
}

/** Fields whose value cannot be saved, with the reason to show. */
export function timingErrors(values: TimingValues, limits: KioskTimingInfo['limits']) {
  const errors: Partial<Record<TimingField, 'range' | 'warning'>> = {}
  for (const name of Object.keys(limits) as TimingField[]) {
    const value = values[name]
    if (!Number.isFinite(value) || value < limits[name].min || value > limits[name].max) {
      errors[name] = 'range'
    }
  }
  if (!errors.warning_seconds && values.warning_seconds >= values.session_limit_seconds) {
    errors.warning_seconds = 'warning'
  }
  return errors
}
