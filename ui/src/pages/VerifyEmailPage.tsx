import { useEffect, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { ApiError, api, type VerificationEmailRateLimitedDetail } from '@/api/client'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { useAuthStore } from '@/stores/auth'
import { useEmailVerificationStore } from '@/stores/emailVerification'

function formatCountdown(ms: number): string {
  const totalSeconds = Math.ceil(ms / 1000)
  const minutes = Math.floor(totalSeconds / 60)
  const seconds = totalSeconds % 60
  return `${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`
}

function getRateLimitDetail(err: unknown): VerificationEmailRateLimitedDetail | null {
  if (!(err instanceof ApiError)) return null
  if (typeof err.body !== 'object' || err.body === null || !('detail' in err.body)) return null

  const detail = err.body.detail
  if (typeof detail !== 'object' || detail === null) return null
  if (detail.error !== 'verification_email_rate_limited') return null

  return detail as VerificationEmailRateLimitedDetail
}

export default function VerifyEmailPage() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const token = searchParams.get('token') || ''
  const pending = useEmailVerificationStore((s) => s.pending)
  const clearPendingVerification = useEmailVerificationStore((s) => s.clearPendingVerification)
  const updateResendAvailableAt = useEmailVerificationStore((s) => s.updateResendAvailableAt)
  const setAuth = useAuthStore((s) => s.setAuth)

  const [code, setCode] = useState('')
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const [verifyingLink, setVerifyingLink] = useState(Boolean(token))
  const [submitting, setSubmitting] = useState(false)
  const [resending, setResending] = useState(false)
  const [now, setNow] = useState(Date.now())

  const resendAvailableAt = pending?.resendAvailableAt
    ? Date.parse(pending.resendAvailableAt)
    : null
  const resendRemainingMs = resendAvailableAt === null ? 0 : Math.max(0, resendAvailableAt - now)
  const resendLocked = resendRemainingMs > 0

  useEffect(() => {
    if (!resendLocked) return

    const intervalId = window.setInterval(() => {
      setNow(Date.now())
    }, 1000)

    return () => {
      window.clearInterval(intervalId)
    }
  }, [resendLocked])

  useEffect(() => {
    if (!token) return

    let cancelled = false

    async function run() {
      setVerifyingLink(true)
      setError('')
      setMessage('')

      try {
        const res = await api.auth.verifyEmail(token)
        if (cancelled) return

        if (pending?.verificationToken && pending.email === res.email) {
          const auth = await api.auth.verifyEmailCode('', pending.verificationToken)
          if (cancelled) return

          if (auth.access_token) {
            clearPendingVerification()
            setAuth(auth.access_token)
            navigate(pending.redirect || '/integrations', { replace: true })
            return
          }
        }

        setMessage(res.message)
      } catch (err) {
        if (cancelled) return
        setError(err instanceof Error ? err.message : 'Verification failed')
      } finally {
        if (!cancelled) {
          setVerifyingLink(false)
        }
      }
    }

    void run()
    return () => {
      cancelled = true
    }
  }, [token, pending, clearPendingVerification, navigate, setAuth])

  async function onSubmit(e: { preventDefault(): void }) {
    e.preventDefault()
    if (!pending?.verificationToken) {
      setError('Your verification session expired. Sign in again to continue.')
      return
    }

    setSubmitting(true)
    setError('')
    setMessage('')

    try {
      const res = await api.auth.verifyEmailCode(code, pending.verificationToken)
      clearPendingVerification()
      if (res.access_token) {
        setAuth(res.access_token)
        navigate(pending.redirect || '/integrations', { replace: true })
        return
      }
      setMessage(res.message)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Verification failed')
    } finally {
      setSubmitting(false)
    }
  }

  async function onResend() {
    if (!pending?.verificationToken || resendLocked) return

    setResending(true)
    setError('')
    setMessage('')

    try {
      const res = await api.auth.resendVerificationCode(pending.verificationToken)
      updateResendAvailableAt(res.resend_available_at)
      setMessage(res.message)
      setCode('')
    } catch (err) {
      const detail = getRateLimitDetail(err)
      if (detail?.resend_available_at) {
        updateResendAvailableAt(detail.resend_available_at)
      }
      setError(err instanceof Error ? err.message : 'Failed to resend verification email')
    } finally {
      setNow(Date.now())
      setResending(false)
    }
  }

  if (!token && !pending) {
    return (
      <div style={pageStyle}>
        <div style={cardStyle}>
          <h1 style={titleStyle}>Verify your email</h1>
          <p style={bodyStyle}>
            Your verification session has expired. Sign in again to get a new code.
          </p>
          <p style={linkRowStyle}>
            <Link to="/login" style={linkStyle}>
              Back to sign in
            </Link>
          </p>
        </div>
      </div>
    )
  }

  if (token) {
    return (
      <div style={pageStyle}>
        <div style={cardStyle}>
          <h1 style={titleStyle}>Verify your email</h1>
          {verifyingLink && <p style={bodyStyle}>Verifying your email...</p>}
          {!verifyingLink && message && <p style={successStyle}>{message}</p>}
          {!verifyingLink && error && <p style={errorStyle}>{error}</p>}
          {!verifyingLink && (
            <p style={linkRowStyle}>
              <Link to="/login" style={linkStyle}>
                Back to sign in
              </Link>
            </p>
          )}
        </div>
      </div>
    )
  }

  return (
    <div style={pageStyle}>
      <div style={cardStyle}>
        <h1 style={titleStyle}>Enter your verification code</h1>
        <p style={bodyStyle}>
          We sent a 6-digit code to{' '}
          <strong style={{ color: 'var(--text)' }}>{pending?.email}</strong>.
        </p>

        <form onSubmit={onSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          <div>
            <Label htmlFor="verification-code" style={labelStyle}>
              Verification code
            </Label>
            <Input
              id="verification-code"
              inputMode="numeric"
              autoComplete="one-time-code"
              maxLength={6}
              placeholder="123456"
              value={code}
              onChange={(e) => setCode(e.target.value)}
              required
              style={inputStyle}
            />
          </div>

          {message && <p style={successStyle}>{message}</p>}
          {error && <p style={errorStyle}>{error}</p>}

          <Button type="submit" disabled={submitting} style={{ width: '100%', height: 40 }}>
            {submitting ? 'Verifying...' : 'Verify email'}
          </Button>
        </form>

        <div style={secondaryActionsStyle}>
          <Button
            type="button"
            variant="outline"
            onClick={onResend}
            disabled={resending || resendLocked}
            style={{ width: '100%', height: 38 }}
          >
            {resending
              ? 'Sending...'
              : resendLocked
                ? `Send again in ${formatCountdown(resendRemainingMs)}`
                : 'Send email again'}
          </Button>
          <p style={linkRowStyle}>
            <Link to="/login" style={linkStyle}>
              Use a different email
            </Link>
          </p>
        </div>
      </div>
    </div>
  )
}

const pageStyle: React.CSSProperties = {
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
  maxWidth: 400,
  padding: 'clamp(24px, 5vw, 32px)',
  background: 'var(--content-bg)',
  border: '1px solid var(--border)',
  borderRadius: 12,
  boxShadow: 'var(--shadow-sm)',
  boxSizing: 'border-box',
}

const titleStyle: React.CSSProperties = {
  fontSize: 22,
  fontWeight: 700,
  color: 'var(--text)',
  margin: '0 0 10px',
}

const bodyStyle: React.CSSProperties = {
  fontSize: 13,
  lineHeight: 1.6,
  color: 'var(--text-faint)',
  margin: '0 0 20px',
}

const labelStyle: React.CSSProperties = {
  fontSize: 12,
  fontWeight: 500,
  color: 'var(--text-dim)',
  marginBottom: 6,
  display: 'block',
}

const inputStyle: React.CSSProperties = {
  background: 'var(--input-bg)',
  border: '1px solid var(--border)',
  color: 'var(--text)',
  fontSize: 18,
  letterSpacing: '0.3em',
  textAlign: 'center',
  fontVariantNumeric: 'tabular-nums',
}

const secondaryActionsStyle: React.CSSProperties = {
  display: 'flex',
  flexDirection: 'column',
  gap: 10,
  marginTop: 16,
}

const successStyle: React.CSSProperties = {
  fontSize: 12,
  color: 'var(--text)',
  margin: 0,
}

const errorStyle: React.CSSProperties = {
  fontSize: 12,
  color: 'var(--red)',
  margin: 0,
}

const linkRowStyle: React.CSSProperties = {
  fontSize: 12,
  color: 'var(--text-faint)',
  textAlign: 'center',
  margin: 0,
}

const linkStyle: React.CSSProperties = {
  color: 'var(--blue)',
  textDecoration: 'none',
}
