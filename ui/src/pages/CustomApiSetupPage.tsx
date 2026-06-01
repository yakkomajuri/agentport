import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ArrowLeft, ArrowRight, Globe, KeyRound } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { useConnectionsStore } from '@/stores/connections'

type AuthPreset = 'none' | 'bearer' | 'api_key' | 'custom'

interface PresetConfig {
  id: AuthPreset
  label: string
  hint: string
  header: string
  format: string
}

const PRESETS: PresetConfig[] = [
  {
    id: 'none',
    label: 'None',
    hint: 'No Authorization header',
    header: '',
    format: '',
  },
  {
    id: 'bearer',
    label: 'Bearer token',
    hint: 'Authorization: Bearer <token>',
    header: 'Authorization',
    format: 'Bearer {token}',
  },
  {
    id: 'api_key',
    label: 'API key header',
    hint: 'X-API-Key: <token>',
    header: 'X-API-Key',
    format: '{token}',
  },
  {
    id: 'custom',
    label: 'Custom',
    hint: 'Bring your own header',
    header: '',
    format: '',
  },
]

export default function CustomApiSetupPage() {
  const navigate = useNavigate()
  const createCustomApi = useConnectionsStore((s) => s.createCustomApi)

  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [baseUrl, setBaseUrl] = useState('')
  const [preset, setPreset] = useState<AuthPreset>('bearer')
  const [tokenHeader, setTokenHeader] = useState('Authorization')
  const [tokenFormat, setTokenFormat] = useState('Bearer {token}')
  const [token, setToken] = useState('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  const formatPreview = useMemo(() => buildAuthPreview(tokenFormat), [tokenFormat])

  function handlePreset(next: AuthPreset) {
    setPreset(next)
    const cfg = PRESETS.find((p) => p.id === next)
    if (cfg && next !== 'custom') {
      setTokenHeader(cfg.header)
      setTokenFormat(cfg.format)
    } else if (next === 'custom') {
      if (tokenHeader === 'Authorization' && tokenFormat === 'Bearer {token}') {
        setTokenHeader('')
        setTokenFormat('')
      }
    }
  }

  async function handleSubmit(event: { preventDefault: () => void }) {
    event.preventDefault()
    setError('')

    if (!name.trim()) {
      setError('Give this integration a name')
      return
    }
    if (!baseUrl.trim()) {
      setError('Base URL is required')
      return
    }
    if (preset !== 'none') {
      if (!tokenHeader.trim()) {
        setError('Auth header is required')
        return
      }
      if (!tokenFormat.includes('{token}')) {
        setError('Auth format must include {token}')
        return
      }
    }

    setSaving(true)
    try {
      const created = await createCustomApi({
        name: name.trim(),
        description: description.trim() || null,
        base_url: baseUrl.trim(),
        token_header: tokenHeader.trim(),
        token_format: tokenFormat,
        tools: [],
      })
      navigate(`/integrations/custom-api/${created.id}`, {
        replace: true,
        state: { installToken: preset === 'none' ? '' : token },
      })
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create integration')
      setSaving(false)
    }
  }

  return (
    <div
      style={{
        flex: 1,
        overflow: 'auto',
        background: 'var(--bg)',
        padding: '40px 20px 80px',
      }}
    >
      <div style={{ maxWidth: 560, margin: '0 auto' }}>
        <button
          type="button"
          onClick={() => navigate('/integrations')}
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: 6,
            border: 'none',
            background: 'transparent',
            color: 'var(--text-dim)',
            fontSize: 12,
            cursor: 'pointer',
            padding: '0 0 16px',
            fontFamily: 'inherit',
          }}
        >
          <ArrowLeft size={13} />
          Integrations
        </button>

        <form
          onSubmit={handleSubmit}
          style={{
            background: 'var(--content-bg)',
            border: '1px solid var(--border)',
            borderRadius: 12,
            boxShadow: 'var(--card-shadow)',
            overflow: 'hidden',
          }}
        >
          {/* Title block */}
          <div
            style={{
              padding: '24px 28px 20px',
              borderBottom: '1px solid var(--border)',
            }}
          >
            <h1
              style={{
                margin: 0,
                fontSize: 17,
                fontWeight: 600,
                color: 'var(--text)',
                lineHeight: 1.3,
              }}
            >
              New API integration
            </h1>
            <p
              style={{
                margin: '4px 0 0',
                fontSize: 13,
                color: 'var(--text-dim)',
                lineHeight: 1.5,
              }}
            >
              Create a new integration from an API.
            </p>
          </div>

          {/* Form fields */}
          <div style={{ padding: '20px 28px 8px' }}>
            <Field label="Name" hint="Shown to you and to the agent" htmlFor="name">
              <input
                id="name"
                value={name}
                onChange={(event) => setName(event.target.value)}
                placeholder="e.g. Stripe API"
                autoFocus
                style={inputStyle}
              />
            </Field>

            <Field label="Description" optional htmlFor="description">
              <input
                id="description"
                value={description}
                onChange={(event) => setDescription(event.target.value)}
                placeholder="Payment processing API"
                style={inputStyle}
              />
            </Field>

            <Field
              label="Base URL"
              hint="Everything before the path. No trailing slash."
              htmlFor="base-url"
            >
              <div style={{ position: 'relative' }}>
                <Globe
                  size={13}
                  style={{
                    position: 'absolute',
                    left: 11,
                    top: 11,
                    color: 'var(--text-faint)',
                    pointerEvents: 'none',
                  }}
                />
                <input
                  id="base-url"
                  value={baseUrl}
                  onChange={(event) => setBaseUrl(event.target.value)}
                  placeholder="https://api.example.com"
                  spellCheck={false}
                  style={{
                    ...inputStyle,
                    paddingLeft: 32,
                    fontFamily: 'var(--font-mono)',
                    fontSize: 12.5,
                  }}
                />
              </div>
            </Field>

            <Field label="Authentication">
              <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                <div
                  style={{
                    display: 'grid',
                    gridTemplateColumns: 'repeat(2, 1fr)',
                    gap: 8,
                  }}
                >
                  {PRESETS.map((p) => (
                    <PresetCard
                      key={p.id}
                      preset={p}
                      active={preset === p.id}
                      onClick={() => handlePreset(p.id)}
                    />
                  ))}
                </div>

                {preset === 'custom' && (
                  <div
                    style={{
                      display: 'grid',
                      gridTemplateColumns: 'minmax(0, 1fr) minmax(0, 1.2fr)',
                      gap: 8,
                      paddingTop: 4,
                    }}
                  >
                    <SubField label="Header">
                      <input
                        value={tokenHeader}
                        onChange={(event) => setTokenHeader(event.target.value)}
                        placeholder="X-Api-Token"
                        style={{ ...inputStyle, fontFamily: 'var(--font-mono)' }}
                      />
                    </SubField>
                    <SubField label="Format">
                      <input
                        value={tokenFormat}
                        onChange={(event) => setTokenFormat(event.target.value)}
                        placeholder="Bearer {token}"
                        style={{ ...inputStyle, fontFamily: 'var(--font-mono)' }}
                      />
                    </SubField>
                  </div>
                )}

                {preset !== 'none' && (
                  <AuthPreview headerName={tokenHeader} formatted={formatPreview} />
                )}
              </div>
            </Field>

            {preset !== 'none' && (
              <Field label="Token" htmlFor="token">
                <div style={{ position: 'relative' }}>
                  <KeyRound
                    size={13}
                    style={{
                      position: 'absolute',
                      left: 11,
                      top: 11,
                      color: 'var(--text-faint)',
                      pointerEvents: 'none',
                    }}
                  />
                  <input
                    id="token"
                    type="password"
                    value={token}
                    onChange={(event) => setToken(event.target.value)}
                    placeholder="sk_live_…"
                    autoComplete="off"
                    spellCheck={false}
                    style={{
                      ...inputStyle,
                      paddingLeft: 32,
                      fontFamily: 'var(--font-mono)',
                      fontSize: 12.5,
                    }}
                  />
                </div>
              </Field>
            )}
          </div>

          {/* Error + actions */}
          {error && (
            <div
              style={{
                margin: '0 28px',
                padding: '8px 12px',
                borderRadius: 6,
                background: 'var(--badge-red-bg)',
                color: 'var(--badge-red-text)',
                fontSize: 12,
                fontWeight: 500,
              }}
            >
              {error}
            </div>
          )}

          <div
            style={{
              padding: '20px 28px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              gap: 12,
              borderTop: '1px solid var(--border)',
              background: 'var(--surface)',
            }}
          >
            <span
              style={{
                fontSize: 11,
                color: 'var(--text-faint)',
                display: 'inline-flex',
                alignItems: 'center',
                gap: 6,
              }}
            >
              <Step n={1} active /> Connect
              <span style={{ color: 'var(--border-strong)' }}>—</span>
              <Step n={2} /> Add tools
            </span>
            <div style={{ display: 'flex', gap: 8 }}>
              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={() => navigate('/integrations')}
                disabled={saving}
              >
                Cancel
              </Button>
              <Button type="submit" size="sm" disabled={saving}>
                <span>{saving ? 'Creating…' : 'Next'}</span>
                {!saving && <ArrowRight size={13} style={{ marginLeft: 6 }} />}
              </Button>
            </div>
          </div>
        </form>
      </div>
    </div>
  )
}

function Field({
  label,
  hint,
  optional,
  htmlFor,
  children,
}: {
  label: string
  hint?: string
  optional?: boolean
  htmlFor?: string
  children: React.ReactNode
}) {
  return (
    <div style={{ paddingBottom: 18 }}>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 8, marginBottom: 6 }}>
        <label
          htmlFor={htmlFor}
          style={{
            fontSize: 11,
            fontWeight: 700,
            color: 'var(--text)',
            textTransform: 'uppercase',
            letterSpacing: 0.5,
          }}
        >
          {label}
        </label>
        {optional && (
          <span
            style={{
              fontSize: 10,
              fontWeight: 600,
              color: 'var(--text-faint)',
              textTransform: 'uppercase',
              letterSpacing: 0.4,
            }}
          >
            optional
          </span>
        )}
        {hint && (
          <span
            style={{
              fontSize: 11,
              color: 'var(--text-faint)',
              marginLeft: 'auto',
              textAlign: 'right',
            }}
          >
            {hint}
          </span>
        )}
      </div>
      {children}
    </div>
  )
}

function SubField({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label style={{ display: 'block', minWidth: 0 }}>
      <div
        style={{
          fontSize: 10,
          fontWeight: 600,
          color: 'var(--text-faint)',
          textTransform: 'uppercase',
          letterSpacing: 0.4,
          marginBottom: 5,
        }}
      >
        {label}
      </div>
      {children}
    </label>
  )
}

function PresetCard({
  preset,
  active,
  onClick,
}: {
  preset: PresetConfig
  active: boolean
  onClick: () => void
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      style={{
        position: 'relative',
        textAlign: 'left',
        padding: '11px 12px',
        borderRadius: 8,
        border: `1px solid ${active ? 'var(--text)' : 'var(--border)'}`,
        background: active ? 'var(--content-bg)' : 'var(--surface)',
        cursor: 'pointer',
        fontFamily: 'inherit',
        transition: 'border-color 120ms ease, background 120ms ease',
        boxShadow: active ? '0 0 0 1px var(--text) inset' : 'none',
      }}
    >
      <div
        style={{
          fontSize: 12,
          fontWeight: 600,
          color: 'var(--text)',
          marginBottom: 3,
        }}
      >
        {preset.label}
      </div>
      <div
        style={{
          fontSize: 11,
          color: 'var(--text-dim)',
          fontFamily: preset.id === 'custom' ? 'inherit' : 'var(--font-mono)',
          overflow: 'hidden',
          textOverflow: 'ellipsis',
          whiteSpace: 'nowrap',
        }}
      >
        {preset.hint}
      </div>
    </button>
  )
}

function AuthPreview({ headerName, formatted }: { headerName: string; formatted: string }) {
  if (!headerName.trim() || !formatted) return null
  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 8,
        padding: '8px 12px',
        borderRadius: 6,
        background: 'var(--code-bg)',
        color: 'var(--code-text)',
        fontFamily: 'var(--font-mono)',
        fontSize: 12,
        minWidth: 0,
        overflow: 'hidden',
      }}
    >
      <KeyRound size={12} style={{ color: 'var(--text-faint)', flexShrink: 0 }} />
      <span style={{ color: 'var(--syn-tag)', flexShrink: 0 }}>{headerName}</span>
      <span style={{ color: 'var(--syn-comment)', flexShrink: 0 }}>:</span>
      <span
        style={{
          color: 'var(--syn-string)',
          overflow: 'hidden',
          textOverflow: 'ellipsis',
          whiteSpace: 'nowrap',
          minWidth: 0,
        }}
      >
        {formatted}
      </span>
    </div>
  )
}

function Step({ n, active }: { n: number; active?: boolean }) {
  return (
    <span
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        justifyContent: 'center',
        width: 16,
        height: 16,
        borderRadius: '50%',
        background: active ? 'var(--text)' : 'transparent',
        color: active ? 'var(--content-bg)' : 'var(--text-faint)',
        border: active ? 'none' : '1px solid var(--border-strong)',
        fontSize: 10,
        fontWeight: 700,
        fontFamily: 'var(--font-mono)',
        marginRight: 4,
      }}
    >
      {n}
    </span>
  )
}

function buildAuthPreview(format: string): string {
  if (!format) return ''
  return format.replace('{token}', 'sk_•••••')
}

const inputStyle: React.CSSProperties = {
  width: '100%',
  height: 36,
  border: '1px solid var(--border)',
  borderRadius: 7,
  background: 'var(--input-bg)',
  color: 'var(--text)',
  fontSize: 13,
  fontFamily: 'inherit',
  outline: 'none',
  padding: '0 11px',
  minWidth: 0,
}
