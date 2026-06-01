import { ArrowLeft, Plug } from 'lucide-react'
import { Button } from '@/components/ui/button'

interface Props {
  installing: boolean
  showInstall: boolean
  error: string
  onInstall: () => void
  onBack: () => void
}

export function IntegrationHeader({ installing, showInstall, error, onInstall, onBack }: Props) {
  return (
    <div
      style={{
        height: 44,
        padding: '0 16px 0 8px',
        borderBottom: '1px solid var(--border)',
        background: 'var(--content-bg)',
        display: 'flex',
        alignItems: 'center',
        gap: 10,
        flexShrink: 0,
      }}
    >
      <button
        type="button"
        onClick={onBack}
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: 6,
          height: 28,
          padding: '0 10px 0 6px',
          borderRadius: 6,
          border: 'none',
          background: 'transparent',
          color: 'var(--text-dim)',
          fontSize: 12,
          fontFamily: 'inherit',
          cursor: 'pointer',
        }}
      >
        <ArrowLeft size={13} />
        Integrations
      </button>

      <span style={{ flex: 1 }} />

      {error && (
        <span
          style={{
            color: 'var(--red)',
            fontSize: 11,
            fontWeight: 500,
            maxWidth: 280,
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
          }}
          title={error}
        >
          {error}
        </span>
      )}

      {showInstall && (
        <Button size="sm" onClick={onInstall} disabled={installing}>
          <Plug size={13} />
          <span style={{ marginLeft: 5 }}>{installing ? 'Installing…' : 'Install'}</span>
        </Button>
      )}
    </div>
  )
}
