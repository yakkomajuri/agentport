import { useEffect, useState } from 'react'
import { KeyRound } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { CodeInput } from './CodeInput'

interface TotpCodeDialogProps {
  open: boolean
  title: string
  description: string
  confirmLabel: string
  onClose: () => void
  onSubmit: (code: string) => Promise<void>
}

export function TotpCodeDialog({
  open,
  title,
  description,
  confirmLabel,
  onClose,
  onSubmit,
}: TotpCodeDialogProps) {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [code, setCode] = useState('')
  const [useRecovery, setUseRecovery] = useState(false)
  const [recoveryCode, setRecoveryCode] = useState('')

  useEffect(() => {
    if (!open) {
      setLoading(false)
      setError('')
      setCode('')
      setUseRecovery(false)
      setRecoveryCode('')
    }
  }, [open])

  if (!open) return null

  async function handleSubmit(submitted?: string) {
    const nextCode = submitted ?? (useRecovery ? recoveryCode.trim() : code)

    if (useRecovery) {
      if (!nextCode) {
        setError('Enter a recovery code to continue')
        return
      }
    } else if (nextCode.length < 6) {
      setError('Enter the 6-digit code from your authenticator')
      return
    }

    setLoading(true)
    setError('')
    try {
      await onSubmit(nextCode)
      onClose()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not verify the code')
      setCode('')
      setRecoveryCode('')
    } finally {
      setLoading(false)
    }
  }

  function dismiss() {
    if (!loading) onClose()
  }

  return (
    <div style={backdropStyle} onClick={dismiss}>
      <div style={panelStyle} onClick={(e) => e.stopPropagation()}>
        <div style={headerStyle}>
          <div style={headerIconStyle}>
            <KeyRound size={16} />
          </div>
          <div>
            <div style={headerTitleStyle}>{title}</div>
            <div style={headerSubtitleStyle}>{description}</div>
          </div>
        </div>

        <div style={bodyStyle}>
          {useRecovery ? (
            <input
              autoFocus
              value={recoveryCode}
              onChange={(e) => {
                setRecoveryCode(e.target.value)
                if (error) setError('')
              }}
              placeholder="xxxxx-xxxxx"
              aria-label="Recovery code"
              disabled={loading}
              style={recoveryInputStyle(!!error)}
            />
          ) : (
            <div style={{ display: 'flex', justifyContent: 'center', padding: '4px 0' }}>
              <CodeInput
                value={code}
                onChange={(value) => {
                  setCode(value)
                  if (error) setError('')
                }}
                onComplete={(value) => void handleSubmit(value)}
                disabled={loading}
                hasError={!!error}
              />
            </div>
          )}

          <div style={{ minHeight: 18 }}>
            {error && <span style={{ fontSize: 12, color: 'var(--red)' }}>{error}</span>}
          </div>

          <button
            onClick={() => {
              setUseRecovery((value) => !value)
              setCode('')
              setRecoveryCode('')
              setError('')
            }}
            style={switchButtonStyle}
            disabled={loading}
          >
            {useRecovery ? 'Use authenticator code' : 'Use a recovery code'}
          </button>
        </div>

        <div style={footerStyle}>
          <Button variant="ghost" size="sm" onClick={dismiss} disabled={loading}>
            Cancel
          </Button>
          <Button size="sm" onClick={() => void handleSubmit()} disabled={loading}>
            {loading ? 'Checking…' : confirmLabel}
          </Button>
        </div>
      </div>
    </div>
  )
}

const backdropStyle: React.CSSProperties = {
  position: 'fixed',
  inset: 0,
  background: 'color-mix(in srgb, black 24%, transparent)',
  backdropFilter: 'blur(2px)',
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  zIndex: 100,
  padding: 16,
}

const panelStyle: React.CSSProperties = {
  width: 420,
  maxWidth: '100%',
  background: 'var(--content-bg)',
  border: '1px solid var(--border)',
  borderRadius: 12,
  boxShadow: 'var(--shadow-md, 0 10px 30px rgba(0,0,0,0.12))',
  overflow: 'hidden',
}

const headerStyle: React.CSSProperties = {
  display: 'flex',
  alignItems: 'flex-start',
  gap: 12,
  padding: '16px 18px',
  borderBottom: '1px solid var(--border)',
}

const headerIconStyle: React.CSSProperties = {
  width: 32,
  height: 32,
  borderRadius: 8,
  border: '1px solid var(--border)',
  background: 'var(--surface)',
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  color: 'var(--text-dim)',
  flexShrink: 0,
}

const headerTitleStyle: React.CSSProperties = {
  fontSize: 14,
  fontWeight: 600,
  color: 'var(--text)',
}

const headerSubtitleStyle: React.CSSProperties = {
  fontSize: 12,
  color: 'var(--text-faint)',
  lineHeight: 1.5,
  marginTop: 3,
}

const bodyStyle: React.CSSProperties = {
  padding: '18px',
  display: 'flex',
  flexDirection: 'column',
  gap: 10,
}

const footerStyle: React.CSSProperties = {
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'space-between',
  padding: '0 18px 18px',
  gap: 12,
}

const switchButtonStyle: React.CSSProperties = {
  alignSelf: 'flex-start',
  background: 'none',
  border: 'none',
  padding: 0,
  fontSize: 12,
  fontWeight: 500,
  color: 'var(--text-faint)',
  cursor: 'pointer',
  textDecoration: 'underline',
  textUnderlineOffset: 2,
}

function recoveryInputStyle(hasError: boolean): React.CSSProperties {
  return {
    width: '100%',
    height: 40,
    padding: '0 12px',
    fontSize: 14,
    fontFamily: 'var(--font-mono, monospace)',
    letterSpacing: '0.06em',
    background: 'var(--surface)',
    border: `1px solid ${hasError ? 'var(--red)' : 'var(--border)'}`,
    borderRadius: 8,
    color: 'var(--text)',
    outline: 'none',
    boxSizing: 'border-box',
  }
}
