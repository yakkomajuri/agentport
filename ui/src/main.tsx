import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { PostHogProvider } from '@posthog/react'
import './index.css'
import App from './App'
import { PostHogAuthSync } from '@/analytics/PostHogAuthSync'
import { isPostHogEnabled, posthog } from '@/analytics/posthog'

// initialize theme before render
import './stores/theme'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <PostHogProvider client={posthog}>
      {isPostHogEnabled ? <PostHogAuthSync /> : null}
      <App />
    </PostHogProvider>
  </StrictMode>,
)
