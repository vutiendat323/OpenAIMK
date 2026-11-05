import { useLayoutEffect, useMemo, useState } from 'react'
import type { ReactNode } from 'react'
import { translate } from './translations'
import { PreferencesContext } from './usePreferences'
import type { Theme, Language, Character } from './usePreferences'

function stored<T extends string>(key: string, choices: readonly T[], fallback: T): T {
  try {
    const value = localStorage.getItem(key)
    return choices.find((choice) => choice === value) ?? fallback
  } catch {
    return fallback
  }
}

function save(key: string, value: string) {
  try {
    localStorage.setItem(key, value)
  } catch {
    // Preferences still work for this page when browser storage is unavailable.
  }
}

export function PreferencesProvider({ children }: { children: ReactNode }) {
  const [theme, setTheme] = useState<Theme>(() =>
    stored('trendcoffee.theme', ['light', 'dark', 'system'], 'light'),
  )
  const [language, setLanguage] = useState<Language>(() =>
    stored('trendcoffee.language', ['vi', 'en'], 'vi'),
  )
  const [character, setCharacter] = useState<Character>(() =>
    stored('trendcoffee.character', ['avatar3d', 'pet'], 'avatar3d'),
  )
  useLayoutEffect(() => {
    const media = window.matchMedia('(prefers-color-scheme: dark)')
    const apply = () => {
      const resolved = theme === 'system' ? (media.matches ? 'dark' : 'light') : theme
      document.documentElement.dataset.theme = resolved
      document.documentElement.classList.toggle('dark', resolved === 'dark')
      document.documentElement.style.colorScheme = resolved
    }
    apply()
    if (theme === 'system') media.addEventListener('change', apply)
    return () => media.removeEventListener('change', apply)
  }, [theme])
  useLayoutEffect(() => {
    document.documentElement.lang = language
  }, [language])
  const value = useMemo(
    () => ({
      theme,
      language,
      character,
      setCharacter: (next: Character) => {
        setCharacter(next)
        save('trendcoffee.character', next)
      },
      setTheme: (next: Theme) => {
        setTheme(next)
        save('trendcoffee.theme', next)
      },
      setLanguage: (next: Language) => {
        setLanguage(next)
        save('trendcoffee.language', next)
      },
      t: (text: string) => translate(language, text),
    }),
    [theme, language, character],
  )
  return <PreferencesContext.Provider value={value}>{children}</PreferencesContext.Provider>
}
