import { Code, Plug } from 'lucide-react'
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog'

interface Props {
  open: boolean
  onClose: () => void
  onPickMcp: () => void
  onPickApi: () => void
}

export function NewIntegrationChooser({ open, onClose, onPickMcp, onPickApi }: Props) {
  return (
    <Dialog open={open} onOpenChange={(next) => !next && onClose()}>
      <DialogContent className="sm:max-w-[520px]">
        <DialogHeader>
          <DialogTitle>New integration</DialogTitle>
          <p
            style={{
              margin: '4px 0 0',
              fontSize: 12,
              color: 'var(--text-dim)',
              lineHeight: 1.5,
            }}
          >
            Choose what you're connecting.
          </p>
        </DialogHeader>

        <div
          style={{
            display: 'grid',
            gridTemplateColumns: '1fr 1fr',
            gap: 10,
            paddingTop: 4,
          }}
        >
          <ChoiceCard
            icon={<Plug size={18} />}
            label="MCP server"
            hint="Add a remote MCP endpoint by URL."
            onClick={onPickMcp}
          />
          <ChoiceCard
            icon={<Code size={18} />}
            label="Custom API"
            hint="Wrap a REST endpoint as agent tools."
            onClick={onPickApi}
          />
        </div>
      </DialogContent>
    </Dialog>
  )
}

function ChoiceCard({
  icon,
  label,
  hint,
  onClick,
}: {
  icon: React.ReactNode
  label: string
  hint: string
  onClick: () => void
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      style={{
        textAlign: 'left',
        padding: '16px',
        borderRadius: 10,
        border: '1px solid var(--border)',
        background: 'var(--surface)',
        color: 'var(--text)',
        cursor: 'pointer',
        fontFamily: 'inherit',
        display: 'flex',
        flexDirection: 'column',
        gap: 10,
        transition: 'background 120ms ease, border-color 120ms ease',
      }}
      onMouseEnter={(e) => {
        e.currentTarget.style.background = 'var(--surface-hover)'
        e.currentTarget.style.borderColor = 'var(--border-strong)'
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.background = 'var(--surface)'
        e.currentTarget.style.borderColor = 'var(--border)'
      }}
    >
      <span
        style={{
          width: 32,
          height: 32,
          borderRadius: 7,
          background: 'var(--content-bg)',
          border: '1px solid var(--border)',
          display: 'inline-flex',
          alignItems: 'center',
          justifyContent: 'center',
          color: 'var(--text-dim)',
        }}
      >
        {icon}
      </span>
      <div>
        <div
          style={{
            fontSize: 13,
            fontWeight: 600,
            color: 'var(--text)',
            marginBottom: 3,
          }}
        >
          {label}
        </div>
        <div
          style={{
            fontSize: 12,
            color: 'var(--text-dim)',
            lineHeight: 1.4,
          }}
        >
          {hint}
        </div>
      </div>
    </button>
  )
}
