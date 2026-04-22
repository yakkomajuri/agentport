import { useEffect, useRef, useState } from 'react'
import { Check, Copy, ShieldCheck } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { api, ApiError, type TotpSetupResponse } from '@/api/client'
import { CodeInput } from './CodeInput'

type Step = 'scan' | 'recovery' | 'verify'

interface TotpSetupDialogProps {
  open: boolean
  onClose: () => void
  onEnabled: () => void
}

export function TotpSetupDialog({ open, onClose, onEnabled }: TotpSetupDialogProps) {
  const [step, setStep] = useState<Step>('scan')
  const [setupData, setSetupData] = useState<TotpSetupResponse | null>(null)
  const [code, setCode] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [secretRevealed, setSecretRevealed] = useState(false)
  const [codesAcknowledged, setCodesAcknowledged] = useState(false)
  const loadedOnceRef = useRef(false)

  useEffect(() => {
    if (!open) {
      // Reset on close so a re-open starts fresh.
      setStep('scan')
      setCode('')
      setError('')
      setSecretRevealed(false)
      setCodesAcknowledged(false)
      setSetupData(null)
      loadedOnceRef.current = false
      return
    }
    if (loadedOnceRef.current) return
    loadedOnceRef.current = true
    setLoading(true)
    api.totp
      .setup()
      .then((data) => setSetupData(data))
      .catch((e) => setError(e instanceof Error ? e.message : 'Failed to start setup'))
      .finally(() => setLoading(false))
  }, [open])

  if (!open) return null

  async function onVerify(submitted: string) {
    setLoading(true)
    setError('')
    try {
      await api.totp.enable(submitted)
      onEnabled()
      onClose()
    } catch (e) {
      if (e instanceof ApiError) {
        setError(e.message)
      } else {
        setError('Could not verify the code — try again')
      }
      setCode('')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={backdropStyle} onClick={onClose}>
      <div style={panelStyle} onClick={(e) => e.stopPropagation()}>
        <div style={headerStyle}>
          <div style={headerIconStyle}>
            <ShieldCheck size={16} />
          </div>
          <div style={{ flex: 1 }}>
            <div style={headerTitleStyle}>Set up two-factor authentication</div>
            <div style={headerSubtitleStyle}>{subtitleForStep(step)}</div>
          </div>
          <StepPills step={step} />
        </div>

        <div style={bodyStyle}>
          {step === 'scan' && (
            <ScanStep
              data={setupData}
              loading={loading && !setupData}
              secretRevealed={secretRevealed}
              onRevealSecret={() => setSecretRevealed(true)}
              onContinue={() => setStep('recovery')}
              error={error}
            />
          )}

          {step === 'recovery' && setupData && (
            <RecoveryStep
              codes={setupData.recovery_codes}
              acknowledged={codesAcknowledged}
              onAcknowledge={setCodesAcknowledged}
              onBack={() => setStep('scan')}
              onContinue={() => setStep('verify')}
            />
          )}

          {step === 'verify' && (
            <VerifyStep
              code={code}
              onCode={(c) => {
                setCode(c)
                if (error) setError('')
              }}
              onSubmit={onVerify}
              loading={loading}
              error={error}
              onBack={() => setStep('recovery')}
            />
          )}
        </div>
      </div>
    </div>
  )
}

function subtitleForStep(step: Step): string {
  if (step === 'scan') return 'Scan the QR code in your authenticator app'
  if (step === 'recovery') return 'Save these recovery codes before you turn two-factor on'
  return 'Enter the 6-digit code your app shows right now'
}

function StepPills({ step }: { step: Step }) {
  const order: Step[] = ['scan', 'recovery', 'verify']
  const activeIdx = order.indexOf(step)
  return (
    <div style={{ display: 'flex', gap: 6 }}>
      {order.map((s, i) => (
        <span
          key={s}
          style={{
            width: 20,
            height: 3,
            borderRadius: 2,
            background: i <= activeIdx ? 'var(--text-dim)' : 'var(--border)',
            transition: 'background 150ms',
          }}
        />
      ))}
    </div>
  )
}

// ── Scan step ──

function ScanStep({
  data,
  loading,
  secretRevealed,
  onRevealSecret,
  onContinue,
  error,
}: {
  data: TotpSetupResponse | null
  loading: boolean
  secretRevealed: boolean
  onRevealSecret: () => void
  onContinue: () => void
  error: string
}) {
  const [copied, setCopied] = useState(false)

  async function copySecret() {
    if (!data) return
    await navigator.clipboard.writeText(data.secret)
    setCopied(true)
    setTimeout(() => setCopied(false), 1500)
  }

  if (loading) {
    return <div style={{ color: 'var(--text-faint)', fontSize: 13 }}>Generating secret…</div>
  }
  if (error && !data) {
    return <p style={{ fontSize: 13, color: 'var(--red)', margin: 0 }}>{error}</p>
  }
  if (!data) return null

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      <div style={qrTileStyle}>
        <div style={qrImageWrapStyle}>
          <img src={data.qr_data_url} alt="TOTP QR code" style={{ width: 176, height: 176 }} />
        </div>
        <div style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', gap: 10 }}>
          <div>
            <div style={microLabelStyle}>App</div>
            <div style={{ fontSize: 13, color: 'var(--text)' }}>
              Use Google Authenticator, 1Password, Authy, or any TOTP app.
            </div>
          </div>

          <div>
            <div style={microLabelStyle}>Can&rsquo;t scan?</div>
            {secretRevealed ? (
              <button
                onClick={copySecret}
                style={secretPillStyle}
                onMouseEnter={(e) => (e.currentTarget.style.background = 'var(--surface-hover)')}
                onMouseLeave={(e) => (e.currentTarget.style.background = 'var(--surface)')}
              >
                <span style={secretTextStyle}>{data.secret}</span>
                {copied ? <Check size={12} /> : <Copy size={12} />}
              </button>
            ) : (
              <button onClick={onRevealSecret} style={linkButtonStyle}>
                Show the setup key
              </button>
            )}
          </div>
        </div>
      </div>

      <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
        <Button size="sm" onClick={onContinue}>
          I&rsquo;ve scanned it
        </Button>
      </div>
    </div>
  )
}

// ── Verify step ──

function VerifyStep({
  code,
  onCode,
  onSubmit,
  loading,
  error,
  onBack,
}: {
  code: string
  onCode: (value: string) => void
  onSubmit: (value: string) => void
  loading: boolean
  error: string
  onBack: () => void
}) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      <div style={{ display: 'flex', justifyContent: 'center', padding: '12px 0 4px' }}>
        <CodeInput
          value={code}
          onChange={onCode}
          onComplete={onSubmit}
          hasError={!!error}
          disabled={loading}
        />
      </div>

      <div style={{ minHeight: 18 }}>
        {error && <span style={{ fontSize: 12, color: 'var(--red)' }}>{error}</span>}
      </div>

      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <Button variant="ghost" size="sm" onClick={onBack} disabled={loading}>
          Back
        </Button>
        <Button size="sm" onClick={() => onSubmit(code)} disabled={code.length < 6 || loading}>
          {loading ? 'Verifying…' : 'Verify'}
        </Button>
      </div>
    </div>
  )
}

// ── Recovery step ──

function RecoveryStep({
  codes,
  acknowledged,
  onAcknowledge,
  onBack,
  onContinue,
}: {
  codes: string[]
  acknowledged: boolean
  onAcknowledge: (v: boolean) => void
  onBack: () => void
  onContinue: () => void
}) {
  const [copied, setCopied] = useState(false)

  async function copyAll() {
    await navigator.clipboard.writeText(codes.join('\n'))
    setCopied(true)
    setTimeout(() => setCopied(false), 1500)
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <div style={codeGridStyle}>
        {codes.map((c, i) => (
          <div key={c} style={codeRowStyle}>
            <span style={codeIndexStyle}>{String(i + 1).padStart(2, '0')}</span>
            <span style={codeMonoStyle}>{c}</span>
          </div>
        ))}
      </div>

      <div style={recoveryHintStyle}>
        Each code works once. Save them now. If you close this flow before verification, two-factor
        stays off and you can restart setup later.
      </div>

      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <button
          onClick={copyAll}
          style={smallPillButtonStyle}
          onMouseEnter={(e) => (e.currentTarget.style.background = 'var(--surface-hover)')}
          onMouseLeave={(e) => (e.currentTarget.style.background = 'var(--surface)')}
        >
          {copied ? <Check size={12} /> : <Copy size={12} />}
          {copied ? 'Copied' : 'Copy all'}
        </button>

        <label style={checkboxLabelStyle}>
          <input
            type="checkbox"
            checked={acknowledged}
            onChange={(e) => onAcknowledge(e.target.checked)}
            style={{ accentColor: 'var(--text-dim)' }}
          />
          I&rsquo;ve saved these codes somewhere safe
        </label>
      </div>

      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <Button variant="ghost" size="sm" onClick={onBack}>
          Back
        </Button>
        <Button size="sm" onClick={onContinue} disabled={!acknowledged}>
          Continue
        </Button>
      </div>
    </div>
  )
}

// ── Styles ──

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
  width: 520,
  maxWidth: '100%',
  maxHeight: 'calc(100dvh - 48px)',
  background: 'var(--content-bg)',
  border: '1px solid var(--border)',
  borderRadius: 12,
  boxShadow: 'var(--shadow-md, 0 10px 30px rgba(0,0,0,0.12))',
  display: 'flex',
  flexDirection: 'column',
  overflow: 'hidden',
}

const headerStyle: React.CSSProperties = {
  display: 'flex',
  alignItems: 'center',
  gap: 12,
  padding: '16px 20px',
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
  letterSpacing: '-0.005em',
}

const headerSubtitleStyle: React.CSSProperties = {
  fontSize: 12,
  color: 'var(--text-faint)',
  marginTop: 2,
}

const bodyStyle: React.CSSProperties = {
  padding: '20px 20px 18px',
  overflowY: 'auto',
}

const qrTileStyle: React.CSSProperties = {
  display: 'flex',
  gap: 20,
  padding: 16,
  background: 'var(--surface)',
  border: '1px solid var(--border)',
  borderRadius: 10,
}

const qrImageWrapStyle: React.CSSProperties = {
  background: 'white',
  padding: 8,
  borderRadius: 6,
  border: '1px solid var(--border)',
  flexShrink: 0,
}

const microLabelStyle: React.CSSProperties = {
  fontSize: 10,
  fontWeight: 600,
  textTransform: 'uppercase',
  letterSpacing: 0.4,
  color: 'var(--text-faint)',
  marginBottom: 4,
}

const linkButtonStyle: React.CSSProperties = {
  background: 'none',
  border: 'none',
  padding: 0,
  cursor: 'pointer',
  fontSize: 12,
  fontWeight: 500,
  color: 'var(--text-dim)',
  textDecoration: 'underline',
  textUnderlineOffset: 2,
}

const secretPillStyle: React.CSSProperties = {
  display: 'inline-flex',
  alignItems: 'center',
  gap: 8,
  padding: '6px 10px',
  background: 'var(--surface)',
  border: '1px solid var(--border)',
  borderRadius: 6,
  cursor: 'pointer',
  color: 'var(--text-dim)',
  transition: 'background 150ms',
}

const secretTextStyle: React.CSSProperties = {
  fontSize: 12,
  fontFamily: 'var(--font-mono, monospace)',
  letterSpacing: '0.04em',
  color: 'var(--text)',
  wordBreak: 'break-all',
}

const codeGridStyle: React.CSSProperties = {
  display: 'grid',
  gridTemplateColumns: 'repeat(2, minmax(0, 1fr))',
  gap: 6,
  padding: 12,
  border: '1px solid var(--border)',
  borderRadius: 8,
  background: 'var(--surface)',
}

const codeRowStyle: React.CSSProperties = {
  display: 'flex',
  alignItems: 'baseline',
  gap: 10,
  padding: '6px 10px',
}

const codeIndexStyle: React.CSSProperties = {
  fontSize: 10,
  fontFamily: 'var(--font-mono, monospace)',
  color: 'var(--text-faint)',
  letterSpacing: '0.04em',
}

const codeMonoStyle: React.CSSProperties = {
  fontSize: 13,
  fontFamily: 'var(--font-mono, monospace)',
  color: 'var(--text)',
  letterSpacing: '0.05em',
}

const recoveryHintStyle: React.CSSProperties = {
  fontSize: 12,
  color: 'var(--text-faint)',
  lineHeight: 1.5,
}

const smallPillButtonStyle: React.CSSProperties = {
  display: 'inline-flex',
  alignItems: 'center',
  gap: 6,
  padding: '5px 10px',
  background: 'var(--surface)',
  border: '1px solid var(--border)',
  borderRadius: 6,
  fontSize: 12,
  fontWeight: 500,
  color: 'var(--text-dim)',
  cursor: 'pointer',
  transition: 'background 120ms',
}

const checkboxLabelStyle: React.CSSProperties = {
  display: 'inline-flex',
  alignItems: 'center',
  gap: 8,
  fontSize: 12,
  color: 'var(--text-dim)',
  cursor: 'pointer',
  userSelect: 'none',
}
