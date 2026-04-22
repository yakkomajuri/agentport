import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuthStore } from '@/stores/auth'
import { useEmailVerificationStore } from '@/stores/emailVerification'

const ERROR_MESSAGES: Record<string, string> = {
  invalid_state: 'Your Google sign-in link has expired. Please try again.',
  missing_code: 'Google did not return an authorization code. Please try again.',
  token_exchange_failed: 'Google sign-in failed during token exchange. Please try again.',
  missing_profile: 'Google did not return the expected profile. Please try again.',
  signups_disabled: 'New sign-ups are disabled on this server. Ask an admin to create your account.',
  not_on_waitlist: 'Email not on waitlist.',
  self_hosted_org_exists:
    'This server already has an organization. Sign in with the existing owner account.',
  account_disabled: 'Your account is disabled. Contact an administrator.',
  access_denied: 'You denied access on the Google consent screen.',
  login_failed: 'Google sign-in failed. Please try again.',
}

function parseHash(hash: string): Record<string, string> {
  const fragment = hash.startsWith('#') ? hash.slice(1) : hash
  const out: Record<string, string> = {}
  if (!fragment) return out
  for (const part of fragment.split('&')) {
    const [k, v = ''] = part.split('=')
    if (k) out[decodeURIComponent(k)] = decodeURIComponent(v)
  }
  return out
}

export default function GoogleCallbackPage() {
  const navigate = useNavigate()
  const setAuth = useAuthStore((s) => s.setAuth)
  const clearPendingVerification = useEmailVerificationStore((s) => s.clearPendingVerification)
  const [errorCode, setErrorCode] = useState<string | null>(null)

  useEffect(() => {
    const params = parseHash(window.location.hash)
    const token = params.access_token
    const hashError = params.error
    const queryError = new URLSearchParams(window.location.search).get('google_error')
    const error = hashError || queryError

    if (error) {
      setErrorCode(error)
      return
    }
    if (!token) {
      setErrorCode('login_failed')
      return
    }

    // Clear the token from the URL so it isn't exposed to history/back button.
    window.history.replaceState(null, '', '/login/google/callback')
    clearPendingVerification()
    setAuth(token)
    navigate('/integrations', { replace: true })
  }, [setAuth, clearPendingVerification, navigate])

  if (errorCode) {
    return (
      <div style={wrapperStyle}>
        <div style={cardStyle}>
          <h1 style={headingStyle}>Google sign-in failed</h1>
          <p style={bodyStyle}>{ERROR_MESSAGES[errorCode] ?? 'Please try again.'}</p>
          <Link to="/login" style={linkStyle}>
            Back to sign in
          </Link>
        </div>
      </div>
    )
  }

  return (
    <div style={wrapperStyle}>
      <p style={bodyStyle}>Signing you in…</p>
    </div>
  )
}

const wrapperStyle: React.CSSProperties = {
  minHeight: '100dvh',
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  background: 'var(--bg)',
  padding: '24px 16px',
  boxSizing: 'border-box',
}

const cardStyle: React.CSSProperties = {
  width: '100%',
  maxWidth: 380,
  padding: 32,
  background: 'var(--content-bg)',
  border: '1px solid var(--border)',
  borderRadius: 12,
  textAlign: 'center',
}

const headingStyle: React.CSSProperties = {
  fontSize: 20,
  fontWeight: 700,
  color: 'var(--text)',
  margin: '0 0 8px',
}

const bodyStyle: React.CSSProperties = {
  fontSize: 14,
  color: 'var(--text-dim)',
  margin: '0 0 16px',
}

const linkStyle: React.CSSProperties = {
  fontSize: 13,
  color: 'var(--blue)',
  textDecoration: 'none',
}
