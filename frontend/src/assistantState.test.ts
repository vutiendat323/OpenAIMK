import { afterEach, expect, test, vi } from 'vitest'
import {
  appendTranscript,
  assistantPhase,
  waveformLevels,
  SpeakingIndicator,
} from './assistantState'

test('avatar only reports speaking when audio is actually playing', () => {
  const voice = {
    armed: true,
    active: true,
    busy: false,
    locked: true,
    speaking: false,
    state: 'listening',
  }
  expect(assistantPhase(voice)).toBe('listening')
  expect(assistantPhase({ ...voice, speaking: true })).toBe('speaking')
  expect(assistantPhase({ ...voice, state: 'connecting' })).toBe('connecting')
  expect(assistantPhase({ ...voice, state: 'unavailable' })).toBe('unavailable')
  expect(assistantPhase({ ...voice, state: 'unavailable', speaking: true })).toBe('speaking')
  expect(assistantPhase({ ...voice, active: false, locked: false })).toBe('waiting')
  expect(assistantPhase({ ...voice, armed: false, active: false })).toBe('off')
})

test('transcripts preserve both speakers and retain only the current short conversation', () => {
  let messages = appendTranscript([], 'user', 'Cho mình cà phê muối')
  messages = appendTranscript(messages, 'assistant', 'Bạn dùng tại quán hay mang đi?')
  expect(messages.map((m) => m.role)).toEqual(['user', 'assistant'])
  expect(appendTranscript(messages, 'developer', 'private')).toEqual(messages)
  expect(appendTranscript(messages, 'user', '  ')).toEqual(messages)
  for (let i = 0; i < 8; i++) messages = appendTranscript(messages, 'user', String(i))
  expect(messages).toHaveLength(6)
  expect(messages.at(-1)?.text).toBe('7')
})

test('transcript partials update one turn bubble when final text arrives', () => {
  let messages = appendTranscript([], 'user', 'Cho mình', 'turn-1', true)
  messages = appendTranscript(messages, 'assistant', 'Dạ', 'turn-2', true)
  messages = appendTranscript(messages, 'user', 'Cho mình cà phê muối', 'turn-1', false)
  expect(messages).toEqual([
    { role: 'user', text: 'Cho mình cà phê muối', turnId: 'turn-1', partial: false },
    { role: 'assistant', text: 'Dạ', turnId: 'turn-2', partial: true },
  ])
})

test('waveform is silent for silence and responds to the actual audio samples', () => {
  expect(waveformLevels(new Uint8Array(256).fill(128))).toEqual(new Array(24).fill(0))
  const levels = waveformLevels(Uint8Array.from({ length: 256 }, (_, i) => (i % 2 ? 150 : 106)))
  expect(levels).toHaveLength(24)
  expect(levels.every((value) => value > 0 && value <= 1)).toBe(true)
})

test('ready microphone reports listening before speaker identity locks', () => {
  const voice = {
    armed: true,
    active: true,
    busy: false,
    locked: false,
    speaking: false,
    state: 'listening',
  }
  expect(assistantPhase(voice)).toBe('listening')
  expect(assistantPhase({ ...voice, state: 'connecting' })).toBe('connecting')
  expect(assistantPhase({ ...voice, state: 'unavailable' })).toBe('unavailable')
  expect(assistantPhase({ ...voice, active: false })).toBe('waiting')
})

afterEach(() => vi.useRealTimers())

test('speaking label bridges clause pauses without delaying an explicit interruption', () => {
  vi.useFakeTimers()
  const changed = vi.fn()
  const indicator = new SpeakingIndicator(changed)
  indicator.update(true)
  indicator.update(false)
  vi.advanceTimersByTime(500)
  indicator.update(true)
  expect(changed.mock.calls.map((call) => call[0])).toEqual([true])
  indicator.update(false)
  indicator.reset()
  expect(changed.mock.calls.map((call) => call[0])).toEqual([true, false])
  indicator.update(true)
  vi.advanceTimersByTime(1000)
  expect(changed.mock.calls.map((call) => call[0])).toEqual([true, false, true])
  indicator.update(false)
  vi.advanceTimersByTime(750)
  expect(changed.mock.calls.map((call) => call[0])).toEqual([true, false, true, false])
})
