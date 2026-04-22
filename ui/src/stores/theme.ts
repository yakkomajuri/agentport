import { create } from 'zustand'

type Theme = 'light' | 'dark'

interface ThemeState {
  theme: Theme
  toggle: () => void
}

function applyTheme(theme: Theme) {
  document.documentElement.setAttribute('data-theme', theme)
  localStorage.setItem('agent_port_theme', theme)
}

const stored = (localStorage.getItem('agent_port_theme') as Theme) || 'light'
applyTheme(stored)

export const useThemeStore = create<ThemeState>((set) => ({
  theme: stored,
  toggle: () =>
    set((s) => {
      const next = s.theme === 'light' ? 'dark' : 'light'
      applyTheme(next)
      return { theme: next }
    }),
}))
