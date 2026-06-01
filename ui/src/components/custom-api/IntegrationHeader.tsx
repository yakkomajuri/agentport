import { ArrowLeft, RotateCcw, Save } from 'lucide-react'
import { Button } from '@/components/ui/button'

interface Props {
  dirty: boolean
  saving: boolean
  isNew: boolean
  error: string
  onSave: () => void
  onDiscard: () => void
  onBack: () => void
}

export function IntegrationHeader({
  dirty,
  saving,
  isNew,
  error,
  onSave,
  onDiscard,
  onBack,
}: Props) {
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

      {dirty && (
        <span
          aria-label="Unsaved changes"
          title="Unsaved changes"
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: 6,
            color: 'var(--text-faint)',
            fontSize: 11,
            fontStyle: 'italic',
          }}
        >
          <span
            style={{
              width: 6,
              height: 6,
              borderRadius: '50%',
              background: 'var(--amber)',
            }}
          />
          unsaved
        </span>
      )}

      <Button
        variant="ghost"
        size="sm"
        onClick={onDiscard}
        disabled={!dirty || saving}
        title="Discard"
      >
        <RotateCcw size={13} />
        <span style={{ marginLeft: 5 }}>Discard</span>
      </Button>
      <Button size="sm" onClick={onSave} disabled={saving || (!dirty && !isNew)}>
        <Save size={13} />
        <span style={{ marginLeft: 5 }}>{saving ? 'Saving…' : 'Save'}</span>
      </Button>
    </div>
  )
}
