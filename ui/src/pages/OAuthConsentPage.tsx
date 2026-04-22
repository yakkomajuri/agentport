import { useEffect, useState } from 'react'
import { useSearchParams, useNavigate, Navigate } from 'react-router-dom'
import { Loader2, ShieldCheck, ShieldX } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { api } from '@/api/client'
import { useAuthStore } from '@/stores/auth'

interface SessionInfo {
  client_id: string
  client_name: string | null
  redirect_uri: string
  scope: string | null
  resource: string | null
  expires_at: number
}

export default function OAuthConsentPage() {
  const [searchParams] = useSearchParams()
  const sessionToken = searchParams.get('session') ?? ''
  const token = useAuthStore((s) => s.token)

  const [session, setSession] = useState<SessionInfo | null>(null)
  const [loading, setLoading] = useState(true)
  const navigate = useNavigate()
  const [acting, setActing] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!sessionToken || !token) return
    api.oauthConsent
      .getSession(sessionToken)
      .then(setSession)
      .catch((e) =>
        setError(e instanceof Error ? e.message : 'Failed to load authorization request'),
      )
      .finally(() => setLoading(false))
  }, [sessionToken, token])

  if (!token) {
    return (
      <Navigate
        to={`/login?redirect=${encodeURIComponent(`/oauth/authorize?session=${sessionToken}`)}`}
        replace
      />
    )
  }

  if (!sessionToken) {
    return (
      <div style={pageStyle}>
        <div style={cardStyle}>
          <ShieldX
            size={28}
            style={{ color: 'var(--red)', margin: '0 auto 12px', display: 'block' }}
          />
          <p style={{ fontSize: 14, color: 'var(--red)', textAlign: 'center', margin: 0 }}>
            Missing authorization session.
          </p>
        </div>
      </div>
    )
  }

  async function act(action: 'approve' | 'deny') {
    setActing(true)
    setError('')
    try {
      const { redirect_url } =
        action === 'approve'
          ? await api.oauthConsent.approve(sessionToken)
          : await api.oauthConsent.deny(sessionToken)
      if (action === 'approve') {
        const params = new URLSearchParams({ redirect: redirect_url })
        if (clientLabel && clientLabel !== '—') params.set('client', clientLabel)
        navigate(`/oauth/success?${params.toString()}`)
      } else {
        window.location.href = redirect_url
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Action failed')
      setActing(false)
    }
  }

  const scopes = session?.scope ? session.scope.split(' ').filter(Boolean) : []
  const clientLabel = session?.client_name || session?.client_id || '—'
  const isExpired = session && session.expires_at < Date.now() / 1000

  return (
    <div style={pageStyle}>
      <div style={cardStyle}>
        <div style={{ textAlign: 'center', marginBottom: 24 }}>
          <ShieldCheck
            size={28}
            style={{ color: 'var(--accent)', margin: '0 auto 10px', display: 'block' }}
          />
          <h1 style={{ fontSize: 15, fontWeight: 600, color: 'var(--text)', margin: '0 0 4px' }}>
            Authorize access
          </h1>
          <p style={{ fontSize: 12, color: 'var(--text-faint)', margin: 0 }}>AgentPort</p>
        </div>

        {loading && (
          <div style={{ textAlign: 'center', padding: '32px 0', color: 'var(--text-faint)' }}>
            <Loader2 size={20} style={{ animation: 'spin 1s linear infinite' }} />
          </div>
        )}

        {error && !session && (
          <p style={{ fontSize: 13, color: 'var(--red)', textAlign: 'center', margin: '0 0 16px' }}>
            {error}
          </p>
        )}

        {session && !isExpired && (
          <>
            <div style={sectionStyle}>
              <Row label="Client" value={clientLabel} mono={!session.client_name} />
              {session.resource && <Row label="Resource" value={session.resource} mono />}
            </div>

            {scopes.length > 0 && (
              <div style={sectionStyle}>
                <div style={sectionLabelStyle}>Requested scopes</div>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginTop: 6 }}>
                  {scopes.map((s) => (
                    <span key={s} style={scopeTagStyle}>
                      {s}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {error && (
              <p style={{ fontSize: 12, color: 'var(--red)', margin: '0 0 12px' }}>{error}</p>
            )}

            <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginTop: 8 }}>
              <Button
                onClick={() => act('approve')}
                disabled={acting}
                style={{ width: '100%', height: 40, fontSize: 14, fontWeight: 600 }}
              >
                {acting ? (
                  <Loader2
                    size={14}
                    style={{ animation: 'spin 1s linear infinite', marginRight: 6 }}
                  />
                ) : (
                  <ShieldCheck size={14} style={{ marginRight: 6 }} />
                )}
                {acting ? 'Authorizing...' : 'Allow access'}
              </Button>
              <Button
                onClick={() => act('deny')}
                disabled={acting}
                variant="outline"
                style={{
                  width: '100%',
                  height: 38,
                  fontSize: 13,
                  color: 'var(--red)',
                  borderColor: 'color-mix(in srgb, var(--red) 30%, transparent)',
                }}
              >
                Deny
              </Button>
            </div>
          </>
        )}

        {session && isExpired && (
          <p
            style={{
              fontSize: 13,
              color: 'var(--text-faint)',
              textAlign: 'center',
              margin: '8px 0 0',
            }}
          >
            This authorization request has expired.
          </p>
        )}
      </div>
      <p style={footerStyle}>AgentPort</p>
    </div>
  )
}

function Row({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <div style={{ display: 'flex', gap: 16, alignItems: 'baseline', fontSize: 13 }}>
      <span
        style={{
          width: 64,
          flexShrink: 0,
          fontSize: 11,
          fontWeight: 500,
          color: 'var(--text-faint)',
          textTransform: 'uppercase',
          letterSpacing: '0.03em',
        }}
      >
        {label}
      </span>
      <span
        style={{
          color: 'var(--text)',
          fontFamily: mono ? 'var(--font-mono, monospace)' : undefined,
          fontSize: mono ? 12 : 13,
          wordBreak: 'break-all',
        }}
      >
        {value}
      </span>
    </div>
  )
}

const pageStyle: React.CSSProperties = {
  minHeight: '100dvh',
  display: 'flex',
  flexDirection: 'column',
  alignItems: 'center',
  justifyContent: 'center',
  background: 'var(--bg)',
  padding: '24px 16px',
  boxSizing: 'border-box',
}

const cardStyle: React.CSSProperties = {
  width: '100%',
  maxWidth: 420,
  padding: 'clamp(24px, 5vw, 36px)',
  background: 'var(--content-bg)',
  border: '1px solid var(--border)',
  borderRadius: 12,
  boxShadow: 'var(--shadow-sm)',
  boxSizing: 'border-box',
}

const sectionStyle: React.CSSProperties = {
  display: 'flex',
  flexDirection: 'column',
  gap: 8,
  padding: '14px 16px',
  background: 'var(--surface)',
  borderRadius: 8,
  border: '1px solid var(--border)',
  marginBottom: 12,
}

const sectionLabelStyle: React.CSSProperties = {
  fontSize: 11,
  fontWeight: 500,
  color: 'var(--text-faint)',
  textTransform: 'uppercase',
  letterSpacing: '0.03em',
}

const scopeTagStyle: React.CSSProperties = {
  fontSize: 11,
  fontWeight: 500,
  padding: '2px 8px',
  borderRadius: 4,
  background: 'var(--badge-gray-bg)',
  color: 'var(--badge-gray-text)',
  fontFamily: 'var(--font-mono, monospace)',
}

const footerStyle: React.CSSProperties = {
  marginTop: 16,
  fontSize: 11,
  color: 'var(--text-faint)',
  letterSpacing: '0.04em',
}
