import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { CheckCircle2 } from 'lucide-react'
import { Button } from '@/components/ui/button'

export default function OAuthSuccessPage() {
  const [searchParams] = useSearchParams()
  const redirectUrl = searchParams.get('redirect') ?? ''
  const clientName = searchParams.get('client') ?? ''
  const [callbackFired, setCallbackFired] = useState(false)

  // Fire the redirect in a hidden iframe to deliver the auth code
  // to the MCP client without navigating away from this page
  useEffect(() => {
    if (!redirectUrl || callbackFired) return
    setCallbackFired(true)
  }, [redirectUrl, callbackFired])

  const displayName = clientName || 'the app'

  return (
    <div style={pageStyle}>
      <div style={cardStyle}>
        <div style={{ textAlign: 'center', marginBottom: 24 }}>
          <div style={iconContainerStyle}>
            <CheckCircle2 size={24} style={{ color: '#fff' }} />
          </div>
          <h1 style={headingStyle}>Connected successfully</h1>
          <p style={subtitleStyle}>AgentPort</p>
        </div>

        {clientName && (
          <div style={sectionStyle}>
            <Row label="Client" value={clientName} />
          </div>
        )}

        <p style={messageStyle}>
          Authorization is complete. You can return to {displayName} or close this window.
        </p>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginTop: 4 }}>
          <Button
            variant="outline"
            onClick={() => window.close()}
            style={{ width: '100%', height: 38, fontSize: 13 }}
          >
            Close window
          </Button>
        </div>

        {/* Hidden iframe to deliver the auth code to the MCP client */}
        {redirectUrl && callbackFired && (
          <iframe src={redirectUrl} style={{ display: 'none' }} title="OAuth callback" sandbox="" />
        )}
      </div>
      <p style={footerStyle}>AgentPort</p>
    </div>
  )
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div style={{ display: 'flex', gap: 16, alignItems: 'baseline', fontSize: 13 }}>
      <span style={rowLabelStyle}>{label}</span>
      <span style={{ color: 'var(--text)', fontSize: 13 }}>{value}</span>
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

const iconContainerStyle: React.CSSProperties = {
  width: 44,
  height: 44,
  borderRadius: 22,
  background: 'var(--green)',
  display: 'inline-flex',
  alignItems: 'center',
  justifyContent: 'center',
  marginBottom: 14,
}

const headingStyle: React.CSSProperties = {
  fontSize: 15,
  fontWeight: 600,
  color: 'var(--text)',
  margin: '0 0 4px',
}

const subtitleStyle: React.CSSProperties = {
  fontSize: 12,
  color: 'var(--text-faint)',
  margin: 0,
}

const sectionStyle: React.CSSProperties = {
  display: 'flex',
  flexDirection: 'column',
  gap: 8,
  padding: '14px 16px',
  background: 'var(--surface)',
  borderRadius: 8,
  border: '1px solid var(--border)',
  marginBottom: 16,
}

const rowLabelStyle: React.CSSProperties = {
  width: 64,
  flexShrink: 0,
  fontSize: 11,
  fontWeight: 500,
  color: 'var(--text-faint)',
  textTransform: 'uppercase',
  letterSpacing: '0.03em',
}

const messageStyle: React.CSSProperties = {
  fontSize: 13,
  lineHeight: 1.6,
  color: 'var(--text-dim)',
  textAlign: 'center',
  margin: '0 0 16px',
}

const footerStyle: React.CSSProperties = {
  marginTop: 16,
  fontSize: 11,
  color: 'var(--text-faint)',
  letterSpacing: '0.04em',
}
