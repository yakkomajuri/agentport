import type { Tool } from '@/api/client'

/** Derived "Policy" column display: "Default only" vs "Conditional". */
export function ToolPolicySummaryBadge({ tool }: { tool: Tool }) {
  const conditional = (tool.policy_enabled_rule_count ?? 0) > 0
  const label = conditional ? 'Conditional' : 'Default only'
  return (
    <span
      style={{
        fontSize: 11,
        fontWeight: 500,
        color: conditional ? 'var(--text)' : 'var(--text-faint)',
        padding: '2px 8px',
        borderRadius: 5,
        border: '1px solid var(--border)',
        background: conditional ? 'var(--surface)' : 'transparent',
        whiteSpace: 'nowrap',
      }}
    >
      {label}
    </span>
  )
}
