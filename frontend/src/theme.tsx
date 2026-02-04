import React, { createContext, useContext, useEffect, useMemo, useState } from 'react'

type ThemeMode = 'system' | 'light' | 'dark'

type ThemeContextValue = {
  mode: ThemeMode
  setMode: (mode: ThemeMode) => void
}

const ThemeContext = createContext<ThemeContextValue | null>(null)

const STORAGE_KEY = 'ui.theme'

function applyTheme(mode: ThemeMode) {
  const root = document.documentElement
  root.dataset.theme = mode

  if (mode === 'system') {
    // Let the browser/OS decide.
    root.style.removeProperty('color-scheme')
    return
  }
  root.style.colorScheme = mode
}

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const [mode, setMode] = useState<ThemeMode>(() => {
    const saved = localStorage.getItem(STORAGE_KEY)
    if (saved === 'light' || saved === 'dark' || saved === 'system') return saved
    return 'system'
  })

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, mode)
    applyTheme(mode)
  }, [mode])

  useEffect(() => {
    applyTheme(mode)
  }, [])

  const value = useMemo(() => ({ mode, setMode }), [mode])

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>
}

export function useTheme(): ThemeContextValue {
  const ctx = useContext(ThemeContext)
  if (!ctx) throw new Error('useTheme must be used within ThemeProvider')
  return ctx
}
