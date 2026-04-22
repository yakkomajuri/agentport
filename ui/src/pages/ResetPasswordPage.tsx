import { useState, type FormEvent } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { api } from '@/api/client'

export default function ResetPasswordPage() {
  const [searchParams] = useSearchParams()
  const token = searchParams.get('token') || ''
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [done, setDone] = useState(false)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    setError('')

    if (password !== confirmPassword) {
      setError('Passwords do not match')
      return
    }
    if (password.length < 6) {
      setError('Password must be at least 6 characters')
      return
    }

    setLoading(true)
    try {
      await api.auth.resetPassword(token, password)
      setDone(true)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Something went wrong')
    } finally {
      setLoading(false)
    }
  }

  if (!token) {
    return (
      <div style={pageStyle}>
        <div style={cardStyle}>
          <p style={{ fontSize: 13, color: 'var(--text)', textAlign: 'center' }}>
            Invalid reset link. Please request a new one.
          </p>
          <p
            style={{ fontSize: 12, color: 'var(--text-faint)', textAlign: 'center', marginTop: 12 }}
          >
            <Link to="/forgot-password" style={{ color: 'var(--blue)', textDecoration: 'none' }}>
              Request new reset link
            </Link>
          </p>
        </div>
      </div>
    )
  }

  return (
    <div style={pageStyle}>
      <div style={cardStyle}>
        <div style={{ textAlign: 'center', marginBottom: 24 }}>
          <h1 style={{ fontSize: 16, fontWeight: 600, color: 'var(--text)', margin: 0 }}>
            Set a new password
          </h1>
        </div>

        {done ? (
          <>
            <p style={{ fontSize: 13, color: 'var(--text)', textAlign: 'center' }}>
              Your password has been reset.
            </p>
            <p
              style={{
                fontSize: 12,
                color: 'var(--text-faint)',
                textAlign: 'center',
                marginTop: 12,
              }}
            >
              <Link to="/login" style={{ color: 'var(--blue)', textDecoration: 'none' }}>
                Sign in
              </Link>
            </p>
          </>
        ) : (
          <form onSubmit={onSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
            <div>
              <Label htmlFor="password" style={labelStyle}>
                New password
              </Label>
              <Input
                id="password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                minLength={6}
                autoFocus
                style={inputStyle}
              />
            </div>
            <div>
              <Label htmlFor="confirm-password" style={labelStyle}>
                Confirm password
              </Label>
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

            <Button type="submit" disabled={loading} style={{ width: '100%', marginTop: 4 }}>
              {loading ? 'Resetting...' : 'Reset password'}
            </Button>
          </form>
        )}
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
  maxWidth: 380,
  padding: 'clamp(24px, 5vw, 32px)',
  background: 'var(--content-bg)',
  border: '1px solid var(--border)',
  borderRadius: 10,
  boxSizing: 'border-box',
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
