import type { RuleWriteBody, ToolExecutionRule } from '@/api/client'
import { FallbackModeSegmentedControl } from './FallbackModeSegmentedControl'
import { PolicyRulesTable } from './PolicyRulesTable'

/**
 * The expanded policy editor for a single tool: the "Fallback for <tool>"
 * segmented control plus the conditional rules table.
 */
export function ToolPolicyExpandedRow({
  toolName,
  fallbackMode,
  rules,
  rulesLoading,
  savingRule,
  fallbackUpdating,
  onSetFallback,
  onCreateRule,
  onUpdateRule,
  onDeleteRule,
  onToggleRule,
}: {
  toolName: string
  fallbackMode: string
  rules: ToolExecutionRule[]
  rulesLoading: boolean
  savingRule: boolean
  fallbackUpdating: boolean
  onSetFallback: (mode: string) => void
  onCreateRule: (body: RuleWriteBody) => Promise<void>
  onUpdateRule: (ruleId: string, body: RuleWriteBody) => Promise<void>
  onDeleteRule: (ruleId: string) => Promise<void>
  onToggleRule: (rule: ToolExecutionRule) => void
}) {
  return (
    <div
      style={{
        margin: '4px 0 8px',
        padding: 16,
        border: '1px solid var(--border)',
        borderRadius: 10,
        background: 'var(--content-bg)',
        display: 'flex',
        flexDirection: 'column',
        gap: 16,
      }}
    >
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--text)' }}>
          Fallback for{' '}
          <span style={{ fontFamily: '"SF Mono", monospace', fontWeight: 500 }}>{toolName}</span>
        </span>
        <span style={{ fontSize: 11, color: 'var(--text-faint)' }}>
          Used when no rule below matches.
        </span>
        <FallbackModeSegmentedControl
          mode={fallbackMode}
          disabled={fallbackUpdating}
          onChange={onSetFallback}
        />
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--text)' }}>Rules</span>
        <PolicyRulesTable
          rules={rules}
          loading={rulesLoading}
          saving={savingRule}
          onCreate={onCreateRule}
          onUpdate={onUpdateRule}
          onDelete={onDeleteRule}
          onToggle={onToggleRule}
        />
      </div>
    </div>
  )
}
