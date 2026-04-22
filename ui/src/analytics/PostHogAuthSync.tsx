import { useEffect } from 'react'
import { usePostHog } from '@posthog/react'
import { useAuthStore } from '@/stores/auth'

export function PostHogAuthSync() {
  const posthog = usePostHog()
  const token = useAuthStore((s) => s.token)
  const fetchMe = useAuthStore((s) => s.fetchMe)

  useEffect(() => {
    if (!posthog || !token) return

    let cancelled = false

    async function syncIdentity() {
      await fetchMe()

      if (cancelled) return

      const email = useAuthStore.getState().email
      if (email) {
        posthog.identify(email, { email })
      }
    }

    void syncIdentity()

    return () => {
      cancelled = true
    }
  }, [fetchMe, posthog, token])

  return null
}
