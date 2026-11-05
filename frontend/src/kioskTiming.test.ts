import { describe, expect, it } from 'vitest'
import { idleNoticeMs, parseTimingInput, timingErrors } from './kioskTiming'
import type { KioskTimingInfo, TimingValues } from './kioskTiming'

const defaults: TimingValues = {
  presence_distance_m: 0.6,
  enter_seconds: 2,
  leave_seconds: 3,
  idle_seconds: 120,
  session_limit_seconds: 600,
  warning_seconds: 60,
}
const limits: KioskTimingInfo['limits'] = {
  presence_distance_m: { min: 0.3, max: 2 },
  enter_seconds: { min: 0.5, max: 10 },
  leave_seconds: { min: 1, max: 30 },
  idle_seconds: { min: 30, max: 600 },
  session_limit_seconds: { min: 120, max: 3600 },
  warning_seconds: { min: 0, max: 300 },
}

describe('kiosk session timing', () => {
  it('accepts the defaults', () => {
    expect(timingErrors(defaults, limits)).toEqual({})
  })
  it('flags values outside the server limits or not numbers', () => {
    expect(timingErrors({ ...defaults, enter_seconds: 0.2 }, limits)).toEqual({
      enter_seconds: 'range',
    })
    expect(timingErrors({ ...defaults, idle_seconds: NaN }, limits)).toEqual({
      idle_seconds: 'range',
    })
  })
  it('needs the warning to come before the end of the session', () => {
    expect(
      timingErrors({ ...defaults, session_limit_seconds: 200, warning_seconds: 200 }, limits),
    ).toEqual({ warning_seconds: 'warning' })
  })
  it('reads decimal commas and rejects text', () => {
    expect(parseTimingInput('1,5')).toBe(1.5)
    expect(parseTimingInput(' 0.75 ')).toBe(0.75)
    expect(parseTimingInput('120')).toBe(120)
    expect(parseTimingInput('')).toBeNaN()
    expect(parseTimingInput('abc')).toBeNaN()
    expect(parseTimingInput('-3')).toBeNaN()
  })
  it('keeps the idle notice at three quarters of the idle time', () => {
    expect(idleNoticeMs(120)).toBe(90000)
    expect(idleNoticeMs(60)).toBe(45000)
  })
})
