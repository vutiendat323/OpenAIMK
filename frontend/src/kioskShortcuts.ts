// Staff keyboard shortcuts on the kiosk: Ctrl+Alt+S hides or shows the header Settings
// button, Ctrl+Alt+K turns the on-screen keyboard off or on (useful with a physical
// keyboard). Each choice is kept per browser; storage may be unavailable.

export const kioskShortcuts = {
  settings: { code: 'KeyS', label: 'Ctrl+Alt+S', storageKey: 'trendcoffee.settingsButton' },
  keyboard: { code: 'KeyK', label: 'Ctrl+Alt+K', storageKey: 'trendcoffee.virtualKeyboard' },
} as const
export type KioskShortcut = keyof typeof kioskShortcuts

type ShortcutEvent = Pick<
  KeyboardEvent,
  'code' | 'ctrlKey' | 'metaKey' | 'altKey' | 'shiftKey' | 'repeat'
> & { getModifierState?: (key: string) => boolean }

/** Ctrl+Alt+<key> (⌘+⌥+<key> on macOS), by physical key so any keyboard layout or IME works. */
export function matchShortcut(event: ShortcutEvent): KioskShortcut | null {
  if (
    event.repeat ||
    !(event.ctrlKey || event.metaKey) ||
    !event.altKey ||
    event.shiftKey ||
    // AltGr reports Ctrl+Alt on some layouts; it types a character, not the shortcut.
    event.getModifierState?.('AltGraph')
  ) {
    return null
  }
  const match = (Object.keys(kioskShortcuts) as KioskShortcut[]).find(
    (name) => kioskShortcuts[name].code === event.code,
  )
  return match ?? null
}

/** Whether the item is shown; it is shown unless staff turned it off in this browser. */
export function storedShown(
  name: KioskShortcut,
  storage: Pick<Storage, 'getItem'> | null = safeStorage(),
) {
  try {
    return storage?.getItem(kioskShortcuts[name].storageKey) !== 'hidden'
  } catch {
    return true
  }
}

export function saveShown(
  name: KioskShortcut,
  shown: boolean,
  storage: Pick<Storage, 'setItem'> | null = safeStorage(),
) {
  try {
    storage?.setItem(kioskShortcuts[name].storageKey, shown ? 'shown' : 'hidden')
  } catch {
    // The toggle still works for this page when browser storage is unavailable.
  }
}

function safeStorage() {
  try {
    return typeof localStorage === 'undefined' ? null : localStorage
  } catch {
    return null
  }
}
