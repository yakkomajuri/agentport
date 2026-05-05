import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Check, Info } from 'lucide-react'
import type { BundledIntegration } from '@/api/client'

interface Props {
  integration: BundledIntegration
  isInstalled: boolean
  onConnect: () => void
}

export function IntegrationCard({ integration, isInstalled, onConnect }: Props) {
  const navigate = useNavigate()
  const slug = integration.id
  const logo = LOGOS[integration.id]
  const unavailable = integration.available === false
  const [tooltipVisible, setTooltipVisible] = useState(false)

  return (
    <div
      onClick={() => !unavailable && navigate(`/integrations/${encodeURIComponent(slug)}`)}
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 14,
        padding: '14px 16px',
        border: '1px solid var(--border)',
        borderRadius: 8,
        background: 'var(--card-bg)',
        cursor: unavailable ? 'default' : 'pointer',
        boxShadow: 'var(--card-shadow)',
        transition: 'box-shadow 150ms, border-color 150ms',
      }}
      onMouseEnter={(e) => {
        if (unavailable) return
        e.currentTarget.style.boxShadow = 'var(--card-shadow-hover)'
        e.currentTarget.style.borderColor = 'var(--border-strong)'
      }}
      onMouseLeave={(e) => {
        if (unavailable) return
        e.currentTarget.style.boxShadow = 'var(--card-shadow)'
        e.currentTarget.style.borderColor = 'var(--border)'
      }}
    >
      <div
        style={{
          width: 40,
          height: 40,
          borderRadius: 8,
          border: '1px solid var(--border)',
          background: 'var(--surface)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          fontSize: 18,
          fontWeight: 600,
          flexShrink: 0,
          opacity: unavailable ? 0.4 : 1,
        }}
      >
        {logo ? (
          <img
            src={logo.src}
            alt={integration.name}
            style={{
              width: 22,
              height: 22,
              objectFit: 'contain',
              filter: logo.darkInvert ? 'var(--logo-invert-filter)' : undefined,
            }}
          />
        ) : (
          integration.name.charAt(0).toUpperCase()
        )}
      </div>
      <div style={{ flex: 1, minWidth: 0, opacity: unavailable ? 0.4 : 1 }}>
        <div style={{ fontSize: 15, fontWeight: 500, color: 'var(--text)' }}>
          {integration.name}
        </div>
      </div>
      <div
        style={{ flexShrink: 0 }}
        onClick={(e) => {
          e.stopPropagation()
          if (!unavailable && !isInstalled) onConnect()
        }}
      >
        {isInstalled ? (
          <span
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: 5,
              fontSize: 12,
              fontWeight: 500,
              color: 'var(--green-dim)',
            }}
          >
            <Check size={13} strokeWidth={2.5} />
            Connected
          </span>
        ) : unavailable ? (
          <div style={{ position: 'relative' }}>
            <button
              onMouseEnter={() => setTooltipVisible(true)}
              onMouseLeave={() => setTooltipVisible(false)}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                justifyContent: 'center',
                width: 30,
                height: 30,
                borderRadius: 6,
                background: 'var(--surface)',
                color: 'var(--text)',
                border: '1px solid var(--border-strong)',
                cursor: 'help',
              }}
            >
              <Info size={14} />
            </button>
            {tooltipVisible && integration.available_reason && (
              <div
                style={{
                  position: 'absolute',
                  right: 0,
                  bottom: 'calc(100% + 8px)',
                  width: 'min(300px, calc(100vw - 40px))',
                  padding: '10px 12px',
                  borderRadius: 6,
                  background: 'var(--card-bg)',
                  border: '1px solid var(--border-strong)',
                  boxShadow: '0 4px 16px rgba(0,0,0,0.2)',
                  fontSize: 11,
                  color: 'var(--text)',
                  lineHeight: 1.6,
                  zIndex: 10,
                  pointerEvents: 'none',
                  overflowWrap: 'break-word',
                  wordBreak: 'break-word',
                }}
              >
                {integration.available_reason}
              </div>
            )}
          </div>
        ) : (
          <button
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              padding: '0 14px',
              height: 30,
              borderRadius: 6,
              fontSize: 12,
              fontWeight: 500,
              background: 'transparent',
              color: 'var(--text-dim)',
              border: '1px solid var(--border)',
              cursor: 'pointer',
              transition: 'background 150ms, border-color 150ms, color 150ms',
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.background = 'var(--accent)'
              e.currentTarget.style.borderColor = 'var(--accent)'
              e.currentTarget.style.color = 'var(--content-bg)'
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.background = 'transparent'
              e.currentTarget.style.borderColor = 'var(--border)'
              e.currentTarget.style.color = 'var(--text-dim)'
            }}
          >
            Connect
          </button>
        )}
      </div>
    </div>
  )
}

export const LOGOS: Record<string, { src: string; darkInvert?: boolean }> = {
  airtable: { src: '/logos/airtable.png' },
  axiom: { src: '/logos/axiom.png', darkInvert: true },
  amplitude: { src: '/logos/amplitude.svg' },
  apify: { src: '/logos/apify.svg' },
  asana: { src: '/logos/asana.svg' },
  atlassian: { src: '/logos/atlassian.png' },
  attio: { src: '/logos/attio.png', darkInvert: true },
  box: { src: '/logos/box.svg' },
  buildkite: { src: '/logos/buildkite.png' },
  calendly: { src: '/logos/calendly.jpg' },
  canva: { src: '/logos/canva.svg' },
  close: { src: '/logos/close.svg' },
  cloudflare: { src: '/logos/cloudflare.png' },
  cloudinary: { src: '/logos/cloudinary.png' },
  contentful: { src: '/logos/contentful.svg' },
  datadog: { src: '/logos/datadog.svg' },
  docusign: { src: '/logos/docusign.png' },
  dropbox: { src: '/logos/dropbox.svg' },
  egnyte: { src: '/logos/egnyte.svg' },
  exa: { src: '/logos/exa.png' },
  figma: { src: '/logos/figma.svg' },
  fireflies: { src: '/logos/fireflies.svg' },
  github: { src: '/logos/github.svg', darkInvert: true },
  gmail: { src: '/logos/gmail.png' },
  granola: { src: '/logos/granola.svg' },
  google_calendar: { src: '/logos/google_calendar.png' },
  gitlab: { src: '/logos/gitlab.svg' },
  grafana: { src: '/logos/grafana.svg' },
  heroku: { src: '/logos/heroku.svg' },
  huggingface: { src: '/logos/huggingface.svg' },
  hubspot: { src: '/logos/hubspot.svg' },
  indeed: { src: '/logos/indeed.svg' },
  intercom: { src: '/logos/intercom.png' },
  launchdarkly: { src: '/logos/launchdarkly.svg', darkInvert: true },
  linear: { src: '/logos/linear.svg', darkInvert: true },
  mercury: { src: '/logos/mercury.png', darkInvert: true },
  mixpanel: { src: '/logos/mixpanel.png' },
  monday: { src: '/logos/monday.svg' },
  neon: { src: '/logos/neon.png' },
  netlify: { src: '/logos/netlify.png' },
  notion: { src: '/logos/notion.svg', darkInvert: true },
  pagerduty: { src: '/logos/pagerduty.svg' },
  paypal: { src: '/logos/paypal.svg' },
  plaid: { src: '/logos/plaid.svg' },
  planetscale: { src: '/logos/planetscale.svg', darkInvert: true },
  posthog: { src: '/logos/posthog.svg' },
  prisma: { src: '/logos/prisma.svg', darkInvert: true },
  ramp: { src: '/logos/ramp.jpg' },
  resend: { src: '/logos/resend.svg', darkInvert: true },
  render: { src: '/logos/render.svg', darkInvert: true },
  sanity: { src: '/logos/sanity.svg', darkInvert: true },
  semgrep: { src: '/logos/semgrep.png' },
  sentry: { src: '/logos/sentry.svg', darkInvert: true },
  shopify: { src: '/logos/shopify.svg' },
  slack: { src: '/logos/slack.svg' },
  square: { src: '/logos/square.png', darkInvert: true },
  stripe: { src: '/logos/stripe.svg' },
  stytch: { src: '/logos/stytch.svg', darkInvert: true },
  supabase: { src: '/logos/supabase.svg' },
  tally: { src: '/logos/tally.svg' },
  telnyx: { src: '/logos/telnyx.png' },
  thoughtspot: { src: '/logos/thoughtspot.png' },
  twilio: { src: '/logos/twilio.svg' },
  vercel: { src: '/logos/vercel.svg', darkInvert: true },
  webflow: { src: '/logos/webflow.svg' },
  wix: { src: '/logos/wix.png', darkInvert: true },
  zapier: { src: '/logos/zapier.svg' },
}
