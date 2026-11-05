import { describe, expect, it } from 'vitest'
import { matchShortcut, saveShown, storedShown } from './kioskShortcuts'

const key = (overrides: Partial<Parameters<typeof matchShortcut>[0]> = {}) => ({
  code: 'KeyS',
  ctrlKey: true,
  metaKey: false,
  altKey: true,
  shiftKey: false,
  repeat: false,
  ...overrides,
})

function memoryStorage() {
  const data: Record<string, string> = {}
  return {
    data,
    getItem: (name: string) => data[name] ?? null,
    setItem: (name: string, value: string) => {
      data[name] = value
    },
  }
}

describe('kiosk shortcuts', () => {
  it('maps Ctrl+Alt+S to Settings and Ctrl+Alt+K to the on-screen keyboard', () => {
    expect(matchShortcut(key())).toBe('settings')
    expect(matchShortcut(key({ code: 'KeyK' }))).toBe('keyboard')
    expect(matchShortcut(key({ ctrlKey: false, metaKey: true, code: 'KeyK' }))).toBe('keyboard')
  })
  it('ignores other combinations, held keys and AltGr typing', () => {
    expect(matchShortcut(key({ altKey: false }))).toBeNull()
    expect(matchShortcut(key({ ctrlKey: false }))).toBeNull()
    expect(matchShortcut(key({ shiftKey: true }))).toBeNull()
    expect(matchShortcut(key({ code: 'KeyD' }))).toBeNull()
    expect(matchShortcut(key({ repeat: true }))).toBeNull()
    expect(matchShortcut(key({ getModifierState: (k) => k === 'AltGraph' }))).toBeNull()
  })
  it('shows each item by default and remembers each choice separately', () => {
    const storage = memoryStorage()
    expect(storedShown('settings', storage)).toBe(true)
    expect(storedShown('keyboard', storage)).toBe(true)
    saveShown('keyboard', false, storage)
    expect(storedShown('keyboard', storage)).toBe(false)
    expect(storedShown('settings', storage)).toBe(true)
    saveShown('keyboard', true, storage)
    expect(storedShown('keyboard', storage)).toBe(true)
  })
  it('keeps the Settings choice saved before this change', () => {
    const storage = memoryStorage()
    storage.data['trendcoffee.settingsButton'] = 'hidden'
    expect(storedShown('settings', storage)).toBe(false)
  })
  it('keeps working when browser storage throws', () => {
    const broken = {
      getItem: () => {
        throw new Error('blocked')
      },
      setItem: () => {
        throw new Error('blocked')
      },
    }
    expect(storedShown('keyboard', broken)).toBe(true)
    expect(() => saveShown('keyboard', false, broken)).not.toThrow()
  })
})
