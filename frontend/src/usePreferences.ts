import { createContext, useContext } from 'react'

export type Theme = 'light' | 'dark' | 'system'
export type Language = 'vi' | 'en'
export type Character = 'avatar3d' | 'pet'

export const PreferencesContext = createContext<{
  theme: Theme
  language: Language
  character: Character
  setCharacter: (character: Character) => void
  setTheme: (theme: Theme) => void
  setLanguage: (language: Language) => void
  t: (text: string) => string
} | null>(null)

export function usePreferences() {
  const value = useContext(PreferencesContext)
  if (!value) throw new Error('PreferencesProvider is required')
  return value
}
