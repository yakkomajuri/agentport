import { Link } from 'react-router-dom'
import { TOOL_MODES } from '@/lib/toolModes'

interface ModeBadgeProps {
  mode: string | undefined
  integrationName: string
}

export function ModeBadge({ mode, integrationName }: ModeBadgeProps) {
  const config = TOOL_MODES.find((m) => m.mode === mode) ?? TOOL_MODES[1]
  const Icon = config.icon

  return (
    <Link
      to={`/integrations/${integrationName}`}
      title="Change in integration settings"
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: 5,
        padding: '3px 9px',
        borderRadius: 5,
        background: config.bg,
        color: config.color,
        fontSize: 11,
        fontWeight: 500,
        textDecoration: 'none',
        flexShrink: 0,
        whiteSpace: 'nowrap',
        border: `1px solid color-mix(in srgb, ${config.color} 25%, transparent)`,
      }}
    >
      <Icon size={11} />
      {config.label}
    </Link>
  )
}
