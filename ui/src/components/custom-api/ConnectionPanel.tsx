import { ChevronDown, KeyRound, Link2 } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'

type AuthPreset = 'none' | 'bearer' | 'api_key' | 'custom'

interface Props {
  baseUrl: string
  tokenHeader: string
  tokenFormat: string
  testToken: string
  tokenLabel?: string
  tokenPlaceholder?: string
  onBaseUrlChange: (value: string) => void
  onTokenHeaderChange: (value: string) => void
  onTokenFormatChange: (value: string) => void
  onTestTokenChange: (value: string) => void
}

function presetFor(header: string, format: string): AuthPreset {
  if (!header && !format) return 'none'
  if (header === 'Authorization' && format === 'Bearer {token}') return 'bearer'
  if (header === 'X-API-Key' && format === '{token}') return 'api_key'
  return 'custom'
}

function presetLabel(preset: AuthPreset): string {
  if (preset === 'none') return 'No auth'
  if (preset === 'bearer') return 'Bearer'
  if (preset === 'api_key') return 'API key'
  return 'Custom'
}

export function ConnectionPanel({
  baseUrl,
  tokenHeader,
  tokenFormat,
  testToken,
  tokenLabel = 'Override token',
  tokenPlaceholder = 'Leave blank to use the installed token',
  onBaseUrlChange,
  onTokenHeaderChange,
  onTokenFormatChange,
  onTestTokenChange,
}: Props) {
  const headerInputRef = useRef<HTMLInputElement>(null)
  const [preset, setPreset] = useState<AuthPreset>(() => presetFor(tokenHeader, tokenFormat))
  const [open, setOpen] = useState(() => !baseUrl)

  useEffect(() => {
    setPreset(presetFor(tokenHeader, tokenFormat))
  }, [tokenHeader, tokenFormat])

  function handlePreset(next: AuthPreset) {
    setPreset(next)
    if (next === 'none') {
      onTokenHeaderChange('')
      onTokenFormatChange('')
      onTestTokenChange('')
    } else if (next === 'bearer') {
      onTokenHeaderChange('Authorization')
      onTokenFormatChange('Bearer {token}')
    } else if (next === 'api_key') {
      onTokenHeaderChange('X-API-Key')
      onTokenFormatChange('{token}')
    } else {
      window.requestAnimationFrame(() => headerInputRef.current?.focus())
    }
  }

  const baseHost = baseUrl ? prettyHost(baseUrl) : null

  return (
    <div
      style={{
        background: 'var(--surface)',
        border: '1px solid var(--border)',
        borderRadius: 10,
        overflow: 'hidden',
      }}
    >
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        style={{
          width: '100%',
          height: 40,
          border: 'none',
          background: 'transparent',
          display: 'flex',
          alignItems: 'center',
          gap: 12,
          padding: '0 16px',
          cursor: 'pointer',
          fontFamily: 'inherit',
          textAlign: 'left',
          color: 'var(--text)',
        }}
      >
        <Link2 size={13} style={{ color: 'var(--text-faint)', flexShrink: 0 }} />
        <span
          style={{
            fontSize: 11,
            fontWeight: 600,
            color: 'var(--text-faint)',
            textTransform: 'uppercase',
            letterSpacing: 0.3,
            flexShrink: 0,
          }}
        >
          Connection
        </span>
        <span
          style={{
            fontFamily: 'var(--font-mono)',
            fontSize: 12,
            color: baseHost ? 'var(--text)' : 'var(--text-faint)',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
            minWidth: 0,
            flex: 1,
          }}
        >
          {baseHost ?? 'no base URL'}
        </span>
        <AuthSummary preset={preset} hasToken={!!testToken} />
        <ChevronDown
          size={14}
          style={{
            color: 'var(--text-faint)',
            transform: open ? 'rotate(180deg)' : 'rotate(0deg)',
            transition: 'transform 120ms ease',
            flexShrink: 0,
          }}
        />
      </button>

      {open && (
        <div
          style={{
            padding: '14px 16px 16px',
            display: 'flex',
            flexDirection: 'column',
            gap: 14,
            borderTop: '1px solid var(--border)',
          }}
        >
          <Field label="Base URL">
            <input
              value={baseUrl}
              onChange={(event) => onBaseUrlChange(event.target.value)}
              placeholder="https://api.example.com"
              style={inputStyle}
            />
          </Field>

          <div>
            <div style={labelStyle}>Auth</div>
            <div style={{ display: 'flex', gap: 4, marginBottom: 8, flexWrap: 'wrap' }}>
              <PresetButton
                label="None"
                active={preset === 'none'}
                onClick={() => handlePreset('none')}
              />
              <PresetButton
                label="Bearer"
                active={preset === 'bearer'}
                onClick={() => handlePreset('bearer')}
              />
              <PresetButton
                label="API key"
                active={preset === 'api_key'}
                onClick={() => handlePreset('api_key')}
              />
              <PresetButton
                label="Custom"
                active={preset === 'custom'}
                onClick={() => handlePreset('custom')}
              />
            </div>
            {preset !== 'none' && (
              <div
                style={{
                  display: 'grid',
                  gridTemplateColumns: 'minmax(0, 1fr) minmax(0, 1fr)',
                  gap: 6,
                }}
              >
                <input
                  ref={headerInputRef}
                  value={tokenHeader}
                  onChange={(event) => onTokenHeaderChange(event.target.value)}
                  placeholder="Authorization"
                  style={{ ...inputStyle, fontFamily: 'var(--font-mono)' }}
                />
                <input
                  value={tokenFormat}
                  onChange={(event) => onTokenFormatChange(event.target.value)}
                  placeholder="Bearer {token}"
                  style={{ ...inputStyle, fontFamily: 'var(--font-mono)' }}
                />
              </div>
            )}
            {preset === 'none' && (
              <div
                style={{
                  fontSize: 11,
                  color: 'var(--text-faint)',
                  fontStyle: 'italic',
                }}
              >
                No Authorization header will be sent.
              </div>
            )}
          </div>

          {preset !== 'none' && (
            <Field label={tokenLabel}>
              <div style={{ position: 'relative' }}>
                <KeyRound
                  size={13}
                  style={{
                    position: 'absolute',
                    left: 10,
                    top: 10,
                    color: 'var(--text-faint)',
                    pointerEvents: 'none',
                  }}
                />
                <input
                  type="password"
                  value={testToken}
                  onChange={(event) => onTestTokenChange(event.target.value)}
                  placeholder={tokenPlaceholder}
                  style={{ ...inputStyle, paddingLeft: 30 }}
                />
              </div>
            </Field>
          )}
        </div>
      )}
    </div>
  )
}

function AuthSummary({ preset, hasToken }: { preset: AuthPreset; hasToken: boolean }) {
  const isNone = preset === 'none'
  return (
    <span
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: 6,
        padding: '2px 8px',
        height: 22,
        borderRadius: 99,
        border: '1px solid var(--border)',
        background: 'var(--content-bg)',
        color: 'var(--text-dim)',
        fontSize: 11,
        fontWeight: 500,
        flexShrink: 0,
      }}
    >
      <span>{presetLabel(preset)}</span>
      {!isNone && (
        <span
          style={{
            width: 4,
            height: 4,
            borderRadius: '50%',
            background: hasToken ? 'var(--green)' : 'var(--text-faint)',
            opacity: hasToken ? 1 : 0.6,
          }}
          title={hasToken ? 'Test token set' : 'No test token'}
        />
      )}
    </span>
  )
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label style={{ minWidth: 0, display: 'block' }}>
      <div style={labelStyle}>{label}</div>
      {children}
    </label>
  )
}

function PresetButton({
  label,
  active,
  onClick,
}: {
  label: string
  active: boolean
  onClick: () => void
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      style={{
        height: 24,
        padding: '0 10px',
        borderRadius: 99,
        border: `1px solid ${active ? 'var(--border-strong)' : 'transparent'}`,
        background: active ? 'var(--content-bg)' : 'transparent',
        color: active ? 'var(--text)' : 'var(--text-dim)',
        fontSize: 11,
        fontWeight: 500,
        cursor: 'pointer',
        fontFamily: 'inherit',
      }}
    >
      {label}
    </button>
  )
}

function prettyHost(url: string): string {
  try {
    const u = new URL(url)
    return `${u.host}${u.pathname.replace(/\/$/, '')}`
  } catch {
    return url.replace(/^https?:\/\//, '')
  }
}

const labelStyle: React.CSSProperties = {
  display: 'block',
  marginBottom: 6,
  fontSize: 10,
  fontWeight: 600,
  color: 'var(--text-faint)',
  textTransform: 'uppercase',
  letterSpacing: 0.4,
}

const inputStyle: React.CSSProperties = {
  width: '100%',
  height: 32,
  border: '1px solid var(--border)',
  borderRadius: 6,
  background: 'var(--input-bg)',
  color: 'var(--text)',
  fontSize: 13,
  fontFamily: 'inherit',
  outline: 'none',
  padding: '0 10px',
  minWidth: 0,
}
