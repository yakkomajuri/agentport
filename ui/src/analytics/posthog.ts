import posthog from 'posthog-js'

const posthogProjectToken = 'phc_o9LvxygZagFKt6J9UcJmzf4Ldrj2cFZx8mKMoAtuuUpb'

const posthogHost = import.meta.env.VITE_PUBLIC_POSTHOG_HOST ?? 'https://us.i.posthog.com'

export const isPostHogEnabled = true

if (isPostHogEnabled) {
  posthog.init(posthogProjectToken, {
    api_host: posthogHost,
    defaults: '2026-01-30',
    person_profiles: 'identified_only',
  })
}

export { posthog }
