import { useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { ExternalLink } from 'lucide-react'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { useConnectionsStore } from '@/stores/connections'
import { api, ApiError } from '@/api/client'
import type { BundledIntegration } from '@/api/client'
import { LOGOS } from '@/components/connections/logos'

interface LimitError {
  message: string
  limit: number
}

function asLimitError(err: unknown): LimitError | null {
  if (!(err instanceof ApiError) || err.status !== 402) return null
  const body = err.body
  if (typeof body !== 'object' || body === null) return null
  const detail = (body as { detail?: unknown }).detail
  if (typeof detail !== 'object' || detail === null) return null
  const d = detail as { error?: unknown; message?: unknown; limit?: unknown }
  if (d.error !== 'free_tier_limit') return null
  return {
    message: typeof d.message === 'string' ? d.message : 'Free plan limit reached.',
    limit: typeof d.limit === 'number' ? d.limit : 5,
  }
}

interface Props {
  integration: BundledIntegration | null
  open: boolean
  reauth?: boolean
  onClose: () => void
}

export function ConnectDialog({ integration, open, reauth = false, onClose }: Props) {
  const location = useLocation()
  const navigate = useNavigate()
  const install = useConnectionsStore((s) => s.install)
  const defaultMethod =
    integration?.auth.find((a) => a.method === 'oauth' || a.method === 'token')?.method ?? 'oauth'
  const [authMethod, setAuthMethod] = useState<'oauth' | 'token'>(
    defaultMethod as 'oauth' | 'token',
  )
  const [token, setToken] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [limitError, setLimitError] = useState<LimitError | null>(null)

  function navigateToIntegrationDetail(integrationId: string) {
    const detailPath = `/integrations/${encodeURIComponent(integrationId)}`
    if (location.pathname !== detailPath) {
      navigate(detailPath)
    }
  }

  function handleOpenChange(next: boolean) {
    if (!next) {
      onClose()
      setToken('')
      setError('')
      setLimitError(null)
    }
  }

  async function handleSubmit() {
    if (!integration) return
    setLoading(true)
    setError('')
    setLimitError(null)
    try {
      if (!reauth) {
        await install({
          integration_id: integration.id,
          auth_method: authMethod,
          token: authMethod === 'token' ? token : undefined,
        })
      }

      if (authMethod === 'oauth') {
        try {
          const { authorization_url } = await api.oauth.start(integration.id)
          window.open(authorization_url, '_blank')
        } catch (oauthErr) {
          if (!reauth) {
            await useConnectionsStore.getState().remove(integration.id)
          }
          throw oauthErr
        }
      } else if (authMethod === 'token' && reauth) {
        await api.installed.update(integration.id, token)
      }

      onClose()
      setToken('')
      if (authMethod === 'token') {
        navigateToIntegrationDetail(integration.id)
      }
    } catch (err) {
      const limit = asLimitError(err)
      if (limit) {
        setLimitError(limit)
      } else {
        setError(
          err instanceof Error
            ? err.message
            : reauth
              ? 'Failed to re-authenticate'
              : 'Failed to connect',
        )
      }
    } finally {
      setLoading(false)
    }
  }

  function handleUpgrade() {
    onClose()
    setToken('')
    setError('')
    setLimitError(null)
    navigate('/settings/billing')
  }

  if (!integration) return null

  const supportsOAuth = integration.auth.some((a) => a.method === 'oauth')
  const supportsToken = integration.auth.some((a) => a.method === 'token')
  const tokenAuth = integration.auth.find((a) => a.method === 'token')
  const logo = LOGOS[integration.id]

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent
        className="sm:max-w-md"
        style={{ background: 'var(--content-bg)', border: '1px solid var(--border)' }}
      >
        <DialogHeader>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <div
              style={{
                width: 48,
                height: 48,
                borderRadius: 10,
                border: '1px solid var(--border)',
                background: 'var(--surface)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                flexShrink: 0,
                fontSize: 22,
              }}
            >
              {logo ? (
                <img
                  src={logo.src}
                  alt={integration.name}
                  style={{
                    width: 28,
                    height: 28,
                    objectFit: 'contain',
                    filter: logo.darkInvert ? 'var(--logo-invert-filter)' : undefined,
                  }}
                />
              ) : (
                integration.name.charAt(0).toUpperCase()
              )}
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
              <DialogTitle style={{ fontSize: 16 }}>
                {reauth ? 'Re-authenticate' : 'Connect'} {integration.name}
              </DialogTitle>
              {integration.docs_url && (
                <a
                  href={integration.docs_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  style={{
                    fontSize: 13,
                    color: '#3b82f6',
                    textDecoration: 'none',
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: 4,
                  }}
                  onMouseEnter={(e) => (e.currentTarget.style.textDecoration = 'underline')}
                  onMouseLeave={(e) => (e.currentTarget.style.textDecoration = 'none')}
                >
                  View docs
                  <ExternalLink size={11} />
                </a>
              )}
            </div>
          </div>
        </DialogHeader>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 16, padding: '4px 0' }}>
          {limitError && (
            <div
              style={{
                padding: 12,
                borderRadius: 8,
                border: '1px solid var(--border)',
                background: 'var(--surface)',
                display: 'flex',
                flexDirection: 'column',
                gap: 6,
              }}
            >
              <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text)' }}>
                You&rsquo;ve reached the Free plan limit
              </div>
              <div style={{ fontSize: 12, color: 'var(--text-dim)', lineHeight: 1.5 }}>
                {limitError.message}
              </div>
            </div>
          )}

          {(supportsOAuth || supportsToken) && (
            <div>
              <Label style={labelStyle}>Auth method</Label>
              <div style={{ display: 'flex', gap: 8 }}>
                {supportsOAuth && (
                  <MethodButton
                    label="OAuth"
                    active={authMethod === 'oauth'}
                    onClick={() => setAuthMethod('oauth')}
                  />
                )}
                {supportsToken && (
                  <MethodButton
                    label="API Token"
                    active={authMethod === 'token'}
                    onClick={() => setAuthMethod('token')}
                  />
                )}
              </div>
            </div>
          )}

          {authMethod === 'token' && (
            <div>
              <Label style={labelStyle}>{tokenAuth?.label ?? 'API Token'}</Label>
              <Input
                type="password"
                value={token}
                onChange={(e) => setToken(e.target.value)}
                placeholder="Paste token..."
                style={inputStyle}
              />
            </div>
          )}

          {error && <p style={{ fontSize: 13, color: 'var(--red)', margin: 0 }}>{error}</p>}
        </div>

        <DialogFooter>
          <Button variant="outline" size="default" onClick={onClose}>
            Cancel
          </Button>
          {limitError ? (
            <Button size="default" onClick={handleUpgrade}>
              Upgrade to Plus
            </Button>
          ) : (
            <Button size="default" onClick={handleSubmit} disabled={loading}>
              {loading
                ? reauth
                  ? 'Re-authenticating...'
                  : 'Connecting...'
                : reauth
                  ? 'Re-authenticate'
                  : 'Connect'}
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

function MethodButton({
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
        padding: '8px 16px',
        borderRadius: 6,
        border: `1px solid ${active ? 'var(--accent)' : 'var(--border)'}`,
        background: active ? 'var(--surface-selected)' : 'var(--content-bg)',
        color: active ? 'var(--text)' : 'var(--text-dim)',
        fontSize: 13,
        fontWeight: 500,
        cursor: 'pointer',
        fontFamily: 'inherit',
      }}
    >
      {label}
    </button>
  )
}

const labelStyle: React.CSSProperties = {
  fontSize: 13,
  fontWeight: 500,
  color: 'var(--text-dim)',
  marginBottom: 8,
  display: 'block',
}

const inputStyle: React.CSSProperties = {
  background: 'var(--input-bg)',
  border: '1px solid var(--border)',
  color: 'var(--text)',
  fontSize: 14,
}
