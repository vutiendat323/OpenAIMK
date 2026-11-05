// Staff hide or show the header Settings button with a keyboard shortcut, so guests at the
// kiosk do not open settings. The choice is kept per browser; storage may be unavailable.

export const SETTINGS_SHORTCUT_LABEL = 'Ctrl+Alt+S'
const STORAGE_KEY = 'trendcoffee.settingsButton'

type ShortcutEvent = Pick<
  KeyboardEvent,
  'code' | 'ctrlKey' | 'metaKey' | 'altKey' | 'shiftKey' | 'repeat'
> & { getModifierState?: (key: string) => boolean }

/** Ctrl+Alt+S (⌘+⌥+S on macOS), by physical key so any keyboard layout or IME works. */
export function isSettingsShortcut(event: ShortcutEvent) {
  return (
    !event.repeat &&
    (event.ctrlKey || event.metaKey) &&
    event.altKey &&
    !event.shiftKey &&
    event.code === 'KeyS' &&
    // AltGr reports Ctrl+Alt on some layouts; it types a character, not the shortcut.
    !event.getModifierState?.('AltGraph')
  )
}

export function storedSettingsVisible(storage: Pick<Storage, 'getItem'> | null = safeStorage()) {
  try {
    return storage?.getItem(STORAGE_KEY) !== 'hidden'
  } catch {
    return true
  }
}

export function saveSettingsVisible(
  visible: boolean,
  storage: Pick<Storage, 'setItem'> | null = safeStorage(),
) {
  try {
    storage?.setItem(STORAGE_KEY, visible ? 'shown' : 'hidden')
  } catch {
    // The button still toggles for this page when browser storage is unavailable.
  }
}

function safeStorage() {
  try {
    return typeof localStorage === 'undefined' ? null : localStorage
  } catch {
    return null
  }
}
