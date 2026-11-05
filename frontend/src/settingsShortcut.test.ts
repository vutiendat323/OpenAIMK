import { describe, expect, it } from 'vitest'
import { isSettingsShortcut, saveSettingsVisible, storedSettingsVisible } from './settingsShortcut'

const key = (overrides: Partial<Parameters<typeof isSettingsShortcut>[0]> = {}) => ({
  code: 'KeyS',
  ctrlKey: true,
  metaKey: false,
  altKey: true,
  shiftKey: false,
  repeat: false,
  ...overrides,
})

function memoryStorage(initial: Record<string, string> = {}) {
  const data = { ...initial }
  return {
    data,
    getItem: (name: string) => data[name] ?? null,
    setItem: (name: string, value: string) => {
      data[name] = value
    },
  }
}

describe('settings button shortcut', () => {
  it('toggles on Ctrl+Alt+S and on Cmd+Option+S', () => {
    expect(isSettingsShortcut(key())).toBe(true)
    expect(isSettingsShortcut(key({ ctrlKey: false, metaKey: true }))).toBe(true)
  })
  it('ignores other combinations, held keys and AltGr typing', () => {
    expect(isSettingsShortcut(key({ altKey: false }))).toBe(false)
    expect(isSettingsShortcut(key({ ctrlKey: false }))).toBe(false)
    expect(isSettingsShortcut(key({ shiftKey: true }))).toBe(false)
    expect(isSettingsShortcut(key({ code: 'KeyD' }))).toBe(false)
    expect(isSettingsShortcut(key({ repeat: true }))).toBe(false)
    expect(isSettingsShortcut(key({ getModifierState: (k) => k === 'AltGraph' }))).toBe(false)
  })
  it('shows the button by default and remembers the choice', () => {
    const storage = memoryStorage()
    expect(storedSettingsVisible(storage)).toBe(true)
    saveSettingsVisible(false, storage)
    expect(storedSettingsVisible(storage)).toBe(false)
    saveSettingsVisible(true, storage)
    expect(storedSettingsVisible(storage)).toBe(true)
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
    expect(storedSettingsVisible(broken)).toBe(true)
    expect(() => saveSettingsVisible(false, broken)).not.toThrow()
  })
})
