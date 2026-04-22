import { useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { Button } from '@/components/ui/button'
import { GoogleLoginButton } from '@/components/GoogleLoginButton'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { api } from '@/api/client'
import { useMediaQuery } from '@/lib/useMediaQuery'
import { useAuthStore } from '@/stores/auth'
import { useEmailVerificationStore } from '@/stores/emailVerification'
import { useThemeStore } from '@/stores/theme'

export default function SignupPage() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const { theme } = useThemeStore()
  const setAuth = useAuthStore((s) => s.setAuth)
  const clearPendingVerification = useEmailVerificationStore((s) => s.clearPendingVerification)
  const startPendingVerification = useEmailVerificationStore((s) => s.startPendingVerification)
  const isDesktop = useMediaQuery('(min-width: 900px)')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const redirect = searchParams.get('redirect')
  const loginHref = redirect ? `/login?redirect=${encodeURIComponent(redirect)}` : '/login'

  async function onSubmit(e: { preventDefault(): void }) {
    e.preventDefault()
    if (password !== confirmPassword) {
      setError('Passwords do not match')
      return
    }
    setError('')
    setLoading(true)
    try {
      const registration = await api.auth.register(email, password)
      if (registration.email_verification_required && registration.verification_token) {
        startPendingVerification({
          email: registration.email,
          verificationToken: registration.verification_token,
          resendAvailableAt: registration.resend_available_at,
          redirect,
        })
        navigate('/verify-email')
        return
      }

      const res = await api.auth.login(email, password)
      clearPendingVerification()
      setAuth(res.access_token)
      navigate(redirect || '/integrations')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Registration failed')
    } finally {
      setLoading(false)
    }
  }

  const formContent = (
    <div style={formInnerStyle}>
      <div style={{ marginBottom: 28 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
          <img
            src={theme === 'dark' ? '/logos/agentport-dark-mode.png' : '/logos/agentport-light-mode.png'}
            alt="AgentPort"
            style={{ height: 22, width: 'auto' }}
          />
          <span style={{ fontFamily: "'Space Grotesk', sans-serif", fontSize: 18, fontWeight: 600, color: 'var(--text)', letterSpacing: 0.3 }}>
            AgentPort
          </span>
        </div>
        <h1 style={{ fontSize: isDesktop ? 26 : 24, fontWeight: 700, color: 'var(--text)', margin: 0, marginBottom: 6 }}>
          Create an account
        </h1>
        <p style={{ fontSize: 14, color: 'var(--text-dim)', margin: 0 }}>
          Start managing your agent integrations
        </p>
      </div>

      <div style={{ marginBottom: 16 }}>
        <GoogleLoginButton label="Sign up with Google" />
      </div>

      <div style={dividerStyle}>
        <span style={dividerLineStyle} />
        <span style={dividerLabelStyle}>or</span>
        <span style={dividerLineStyle} />
      </div>

      <form onSubmit={onSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
        <div>
          <Label htmlFor="email" style={labelStyle}>Email</Label>
          <Input
            id="email"
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
            autoFocus
            style={inputStyle}
          />
        </div>
        <div>
          <Label htmlFor="password" style={labelStyle}>Password</Label>
          <Input
            id="password"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            minLength={6}
            style={inputStyle}
          />
        </div>
        <div>
          <Label htmlFor="confirm-password" style={labelStyle}>Confirm password</Label>
          <Input
            id="confirm-password"
            type="password"
            value={confirmPassword}
            onChange={(e) => setConfirmPassword(e.target.value)}
            required
            minLength={6}
            style={inputStyle}
          />
        </div>

        {error && <p style={{ fontSize: 12, color: 'var(--red)', margin: 0 }}>{error}</p>}

        <Button type="submit" disabled={loading} style={{ width: '100%', marginTop: 4, height: 40 }}>
          {loading ? 'Creating account...' : 'Create account'}
        </Button>
      </form>

      <p style={{ fontSize: 12, color: 'var(--text-faint)', textAlign: 'center', margin: '16px 0 0' }}>
        Already have an account?{' '}
        <Link to={loginHref} style={linkStyle}>Sign in</Link>
      </p>
    </div>
  )

  if (!isDesktop) {
    return (
      <div style={mobilePageStyle}>
        <div style={mobileCardStyle}>{formContent}</div>
      </div>
    )
  }

  return (
    <div style={{ display: 'flex', height: '100vh', overflow: 'hidden' }}>
      <div style={formPanelStyle}>{formContent}</div>
      <div style={promoPanelStyle}>
        <div style={{ textAlign: 'center' }}>
          <p style={promoLineStyle}>
            <span style={{ color: 'var(--text)', fontWeight: 700 }}>More power</span>
            <span style={{ color: 'var(--text-faint)' }}> for your agents</span>
          </p>
          <p style={promoLineStyle}>
            <span style={{ color: 'var(--text-faint)' }}>More control </span>
            <span style={{ color: 'var(--text)', fontWeight: 700 }}>for you</span>
          </p>
        </div>
      </div>
    </div>
  )
}

const mobilePageStyle: React.CSSProperties = {
  minHeight: '100dvh',
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  background: 'var(--bg)',
  padding: '24px 16px',
  boxSizing: 'border-box',
}

const mobileCardStyle: React.CSSProperties = {
  width: '100%',
  maxWidth: 400,
  padding: 'clamp(24px, 5vw, 40px)',
  background: 'var(--content-bg)',
  border: '1px solid var(--border)',
  borderRadius: 12,
  boxSizing: 'border-box',
}

const formPanelStyle: React.CSSProperties = {
  flex: '0 0 55%',
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  background: 'var(--content-bg)',
  borderRight: '1px solid var(--border)',
  padding: '48px 32px',
  overflowY: 'auto',
}

const formInnerStyle: React.CSSProperties = {
  width: '100%',
  maxWidth: 380,
}

const promoPanelStyle: React.CSSProperties = {
  flex: 1,
  display: 'flex',
  flexDirection: 'column',
  alignItems: 'center',
  justifyContent: 'center',
  background: 'var(--bg)',
  padding: 48,
  position: 'relative',
}

const promoLineStyle: React.CSSProperties = {
  fontSize: 22,
  fontWeight: 400,
  lineHeight: 1.5,
  margin: 0,
  whiteSpace: 'nowrap',
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
  fontSize: 13,
}

const linkStyle: React.CSSProperties = {
  color: 'var(--blue)',
  textDecoration: 'none',
}

const dividerStyle: React.CSSProperties = {
  display: 'flex',
  alignItems: 'center',
  gap: 12,
  margin: '0 0 16px',
}

const dividerLineStyle: React.CSSProperties = {
  flex: 1,
  height: 1,
  background: 'var(--border)',
}

const dividerLabelStyle: React.CSSProperties = {
  fontSize: 11,
  color: 'var(--text-faint)',
  textTransform: 'uppercase',
  letterSpacing: 0.6,
}
