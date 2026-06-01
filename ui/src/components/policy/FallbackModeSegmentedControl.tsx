import { TOOL_MODES } from '@/lib/toolModes'

/**
 * Segmented [Auto-execute] [Ask] [Deny] control for a tool's fallback mode
 * (ToolExecutionSetting.mode). Used both as the compact "Default" column control
 * and the larger "Fallback for <tool>" control in the expanded row.
 */
export function FallbackModeSegmentedControl({
  mode,
  disabled,
  onChange,
  size = 'md',
}: {
  mode: string
  disabled?: boolean
  onChange: (mode: string) => void
  size?: 'sm' | 'md'
}) {
  const pad = size === 'sm' ? '3px 8px' : '5px 12px'
  const fontSize = size === 'sm' ? 11 : 12
  return (
    <div
      role="group"
      style={{
        display: 'inline-flex',
        border: '1px solid var(--border)',
        borderRadius: 6,
        overflow: 'hidden',
        opacity: disabled ? 0.5 : 1,
      }}
    >
      {TOOL_MODES.map((m, i) => {
        const active = mode === m.mode
        const Icon = m.icon
        return (
          <button
            key={m.mode}
            type="button"
            disabled={disabled}
            aria-pressed={active}
            onClick={() => {
              if (!active && !disabled) onChange(m.mode)
            }}
            title={m.label}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 5,
              padding: pad,
              fontSize,
              fontWeight: active ? 600 : 400,
              border: 'none',
              borderLeft: i > 0 ? '1px solid var(--border)' : 'none',
              background: active ? m.bg : 'transparent',
              color: active ? m.color : 'var(--text-dim)',
              cursor: disabled ? 'not-allowed' : 'pointer',
              transition: 'background 100ms',
              whiteSpace: 'nowrap',
            }}
          >
            <Icon size={13} style={{ color: active ? m.color : 'var(--text-faint)' }} />
            {m.label}
          </button>
        )
      })}
    </div>
  )
}
