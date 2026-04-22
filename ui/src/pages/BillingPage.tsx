import { useEffect, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { Check } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { api, ApiError, type SubscriptionResponse } from '@/api/client'
import { useIsMobile } from '@/lib/useMediaQuery'

const FREE_FEATURES = ['Up to 5 integrations', '10k tool calls / month']

const PLUS_FEATURES = [
  'Unlimited integrations',
  '100k tool calls / month ($1 / 5k additional calls)',
  'Custom integration builder',
  'Priority support',
]

const ENTERPRISE_FEATURES = [
  'Teams',
  'Team-level policy management',
  'Profiles',
  'Integrate with internal services',
  'Self-host enterprise version',
  'SSO / SAML',
]

export default function BillingPage() {
  const navigate = useNavigate()
  const isMobile = useIsMobile()
  const [searchParams, setSearchParams] = useSearchParams()
  const [sub, setSub] = useState<SubscriptionResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [pending, setPending] = useState<'checkout' | 'portal' | null>(null)
  const [error, setError] = useState('')
  const [banner, setBanner] = useState<string | null>(null)

  useEffect(() => {
    api.billing
      .getSubscription()
      .then(setSub)
      .catch((e: unknown) => {
        if (e instanceof ApiError && e.status === 404) {
          navigate('/settings', { replace: true })
          return
        }
        setError(e instanceof Error ? e.message : 'Could not load billing')
      })
      .finally(() => setLoading(false))
  }, [navigate])

  useEffect(() => {
    const checkout = searchParams.get('checkout')
    if (checkout === 'success') {
      setBanner("You're on AgentPort Plus — thanks for subscribing!")
      searchParams.delete('checkout')
      setSearchParams(searchParams, { replace: true })
    } else if (checkout === 'cancel') {
      setBanner('Checkout canceled.')
      searchParams.delete('checkout')
      setSearchParams(searchParams, { replace: true })
    }
  }, [searchParams, setSearchParams])

  async function startCheckout() {
    setPending('checkout')
    setError('')
    try {
      const { url } = await api.billing.createCheckout()
      window.location.href = url
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not start checkout')
      setPending(null)
    }
  }

  async function openPortal() {
    setPending('portal')
    setError('')
    try {
      const { url } = await api.billing.openPortal()
      window.location.href = url
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not open billing portal')
      setPending(null)
    }
  }

  const isPlus = sub?.tier === 'plus'
  const mailto = sub
    ? `mailto:${sub.enterprise_contact_email}?subject=${encodeURIComponent(
        'AgentPort Enterprise',
      )}`
    : '#'

  return (
    <>
      <div
        style={{
          height: 44,
          display: 'flex',
          alignItems: 'center',
          padding: `0 ${isMobile ? 14 : 20}px`,
          borderBottom: '1px solid var(--border)',
          background: 'var(--content-bg)',
          flexShrink: 0,
        }}
      >
        <span style={{ fontSize: 13, fontWeight: 500, color: 'var(--text)' }}>Billing</span>
      </div>

      <div
        style={{
          flex: 1,
          overflowY: 'auto',
          padding: isMobile ? '20px 14px 40px' : '32px 40px',
          maxWidth: 960,
          width: '100%',
        }}
      >
        {banner && (
          <div
            style={{
              padding: '10px 14px',
              border: '1px solid var(--border)',
              borderRadius: 8,
              background: 'var(--surface)',
              fontSize: 13,
              color: 'var(--text)',
              marginBottom: 16,
            }}
          >
            {banner}
          </div>
        )}

        {error && (
          <div style={{ fontSize: 12, color: 'var(--red)', marginBottom: 16 }}>{error}</div>
        )}

        {loading ? (
          <div style={{ fontSize: 13, color: 'var(--text-faint)' }}>Loading…</div>
        ) : sub ? (
          <>
            <SectionLabel>Current plan</SectionLabel>
            <CurrentPlanPanel sub={sub} onManage={openPortal} pending={pending === 'portal'} />

            <SectionLabel>Plans</SectionLabel>
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: isMobile ? '1fr' : 'repeat(3, 1fr)',
                gap: 12,
                marginBottom: 32,
              }}
            >
              <PlanCard
                name="Free"
                price="$0"
                cadence=""
                features={FREE_FEATURES}
                current={!isPlus}
              />
              <PlanCard
                name="Plus"
                price="$12"
                cadence="/ month"
                features={PLUS_FEATURES}
                current={isPlus}
                cta={
                  isPlus ? (
                    <Button size="sm" onClick={openPortal} disabled={pending !== null}>
                      {pending === 'portal' ? 'Opening…' : 'Manage billing'}
                    </Button>
                  ) : (
                    <Button size="sm" onClick={startCheckout} disabled={pending !== null}>
                      {pending === 'checkout' ? 'Starting…' : 'Upgrade'}
                    </Button>
                  )
                }
                highlight
              />
              <PlanCard
                name="Enterprise"
                price="Custom"
                cadence=""
                features={ENTERPRISE_FEATURES}
                cta={
                  <a href={mailto} style={{ textDecoration: 'none' }}>
                    <Button size="sm" variant="outline">
                      Contact us
                    </Button>
                  </a>
                }
              />
            </div>
          </>
        ) : null}
      </div>
    </>
  )
}

function CurrentPlanPanel({
  sub,
  onManage,
  pending,
}: {
  sub: SubscriptionResponse
  onManage: () => void
  pending: boolean
}) {
  const tierLabel = sub.tier === 'plus' ? 'AgentPort Plus' : 'AgentPort Free'
  const renewalDate = sub.current_period_end
    ? new Date(sub.current_period_end).toLocaleDateString(undefined, {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
      })
    : null

  return (
    <div style={panelStyle}>
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 16 }}>
        <div>
          <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--text)' }}>{tierLabel}</div>
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 8,
              marginTop: 6,
              fontSize: 12,
              color: 'var(--text-dim)',
            }}
          >
            <span>{statusLabel(sub)}</span>
            {renewalDate && sub.tier === 'plus' && (
              <>
                <span style={{ color: 'var(--text-faint)' }}>·</span>
                <span>
                  {sub.cancel_at_period_end ? 'Ends' : 'Renews'} {renewalDate}
                </span>
              </>
            )}
          </div>
        </div>
        {sub.tier === 'plus' && (
          <Button size="sm" variant="outline" onClick={onManage} disabled={pending}>
            {pending ? 'Opening…' : 'Manage'}
          </Button>
        )}
      </div>
    </div>
  )
}

function PlanCard({
  name,
  price,
  cadence,
  features,
  current,
  cta,
  highlight,
}: {
  name: string
  price: string
  cadence: string
  features: string[]
  current?: boolean
  cta?: React.ReactNode
  highlight?: boolean
}) {
  return (
    <div
      style={{
        padding: 18,
        border: `1px solid ${highlight ? 'var(--text-dim)' : 'var(--border)'}`,
        borderRadius: 10,
        background: 'var(--content-bg)',
        display: 'flex',
        flexDirection: 'column',
        gap: 12,
      }}
    >
      <div>
        <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text)' }}>{name}</div>
        <div style={{ marginTop: 4, display: 'flex', alignItems: 'baseline', gap: 4 }}>
          <span style={{ fontSize: 22, fontWeight: 600, color: 'var(--text)' }}>{price}</span>
          {cadence && (
            <span style={{ fontSize: 12, color: 'var(--text-faint)' }}>{cadence}</span>
          )}
        </div>
      </div>

      <ul style={{ listStyle: 'none', padding: 0, margin: 0, display: 'flex', flexDirection: 'column', gap: 6 }}>
        {features.map((f) => (
          <li
            key={f}
            style={{
              display: 'flex',
              alignItems: 'flex-start',
              gap: 8,
              fontSize: 12,
              color: 'var(--text-dim)',
            }}
          >
            <Check size={12} style={{ marginTop: 3, color: 'var(--text-faint)', flexShrink: 0 }} />
            <span>{f}</span>
          </li>
        ))}
      </ul>

      <div style={{ marginTop: 'auto' }}>
        {current ? (
          <span
            style={{
              fontSize: 11,
              fontWeight: 500,
              color: 'var(--text-faint)',
              textTransform: 'uppercase',
              letterSpacing: 0.5,
            }}
          >
            Current plan
          </span>
        ) : (
          cta
        )}
      </div>
    </div>
  )
}

function statusLabel(sub: SubscriptionResponse): string {
  if (sub.status === 'past_due') return 'Payment failed — update card'
  if (sub.status === 'canceled') return 'Canceled'
  if (sub.status === 'incomplete') return 'Incomplete'
  if (sub.cancel_at_period_end) return 'Canceling at period end'
  if (sub.status === 'trialing') return 'Trialing'
  return 'Active'
}

function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <div
      style={{
        fontSize: 10,
        fontWeight: 600,
        textTransform: 'uppercase',
        letterSpacing: 0.6,
        color: 'var(--text-faint)',
        marginBottom: 10,
      }}
    >
      {children}
    </div>
  )
}

const panelStyle: React.CSSProperties = {
  padding: 16,
  border: '1px solid var(--border)',
  borderRadius: 10,
  background: 'var(--content-bg)',
  marginBottom: 32,
}
