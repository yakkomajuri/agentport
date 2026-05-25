import { useState } from 'react'
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
import type { CustomMcpIntegration } from '@/api/client'

interface Props {
  open: boolean
  onClose: () => void
  onCreated?: (created: CustomMcpIntegration) => void
}

export function AddCustomMcpDialog({ open, onClose, onCreated }: Props) {
  const create = useConnectionsStore((s) => s.createCustomMcp)
  const [name, setName] = useState('')
  const [url, setUrl] = useState('')
  const [authMethod, setAuthMethod] = useState<'none' | 'token' | 'oauth'>('none')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')

  function reset() {
    setName('')
    setUrl('')
    setAuthMethod('none')
    setError('')
  }

  function handleOpenChange(next: boolean) {
    if (!next) {
      onClose()
      reset()
    }
  }

  async function handleSubmit() {
    if (!name.trim()) {
      setError('Name is required')
      return
    }
    if (!url.trim()) {
      setError('URL is required')
      return
    }
    setError('')
    setSubmitting(true)
    try {
      const created = await create({
        name: name.trim(),
        url: url.trim(),
        auth_method: authMethod,
      })
      onCreated?.(created)
      onClose()
      reset()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to add integration')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent
        className="sm:max-w-md"
        style={{ background: 'var(--content-bg)', border: '1px solid var(--border)' }}
      >
        <DialogHeader>
          <DialogTitle style={{ fontSize: 16 }}>Add custom MCP server</DialogTitle>
        </DialogHeader>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 16, padding: '4px 0' }}>
          <div>
            <Label style={labelStyle}>Name</Label>
            <Input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="My MCP server"
              style={inputStyle}
              autoFocus
            />
          </div>

          <div>
            <Label style={labelStyle}>MCP URL</Label>
            <Input
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              placeholder="https://mcp.example.com/mcp"
              style={inputStyle}
            />
          </div>

          <div>
            <Label style={labelStyle}>Authentication</Label>
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
              <MethodButton
                label="None"
                active={authMethod === 'none'}
                onClick={() => setAuthMethod('none')}
              />
              <MethodButton
                label="Bearer token"
                active={authMethod === 'token'}
                onClick={() => setAuthMethod('token')}
              />
              <MethodButton
                label="OAuth"
                active={authMethod === 'oauth'}
                onClick={() => setAuthMethod('oauth')}
              />
            </div>
            <div style={hintStyle}>{AUTH_HINTS[authMethod]}</div>
          </div>

          {error && <p style={{ fontSize: 13, color: 'var(--red)', margin: 0 }}>{error}</p>}
        </div>

        <DialogFooter>
          <Button variant="outline" size="default" onClick={() => handleOpenChange(false)}>
            Cancel
          </Button>
          <Button size="default" onClick={handleSubmit} disabled={submitting}>
            {submitting ? 'Adding...' : 'Add'}
          </Button>
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

const AUTH_HINTS: Record<'none' | 'token' | 'oauth', string> = {
  none: 'The MCP server is reachable without credentials.',
  token: "You'll paste the token after this step, when you click Connect.",
  oauth:
    "We'll discover the server's OAuth endpoints when you connect. The server must support MCP " +
    'OAuth (RFC 9728 + dynamic client registration).',
}

const hintStyle: React.CSSProperties = {
  fontSize: 12,
  color: 'var(--text-faint)',
  marginTop: 8,
  lineHeight: 1.5,
}
