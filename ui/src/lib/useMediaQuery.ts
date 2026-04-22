import { useCallback, useSyncExternalStore } from 'react'

export function useMediaQuery(query: string): boolean {
  const subscribe = useCallback(
    (onChange: () => void) => {
      const mql = window.matchMedia(query)
      mql.addEventListener('change', onChange)
      return () => mql.removeEventListener('change', onChange)
    },
    [query],
  )

  return useSyncExternalStore(
    subscribe,
    () => window.matchMedia(query).matches,
    () => false,
  )
}

// Viewports ≤ 768px are treated as mobile. This matches the tablet-down
// breakpoint used throughout the layout and all pages for responsive tweaks.
export function useIsMobile(): boolean {
  return useMediaQuery('(max-width: 768px)')
}
