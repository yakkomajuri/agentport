import { useState } from 'react'
import { Loader2, Pencil, Plus, Trash2 } from 'lucide-react'
import type { RuleWriteBody, ToolExecutionRule } from '@/api/client'
import { effectColor, effectLabel, operatorLabel, RULE_LIMITS } from '@/lib/policyRules'
import { ConditionValueChips } from './ConditionValueChips'
import { PolicyRuleEditorRow } from './PolicyRuleEditorRow'

const headerCell: React.CSSProperties = {
  fontSize: 10,
  fontWeight: 600,
  textTransform: 'uppercase',
  letterSpacing: 0.4,
  color: 'var(--text-faint)',
  padding: '4px 8px',
  textAlign: 'left',
}

const cell: React.CSSProperties = {
  fontSize: 12,
  color: 'var(--text)',
  padding: '8px',
  verticalAlign: 'top',
}

export function PolicyRulesTable({
  rules,
  loading,
  saving,
  onCreate,
  onUpdate,
  onDelete,
  onToggle,
}: {
  rules: ToolExecutionRule[]
  loading: boolean
  saving: boolean
  onCreate: (body: RuleWriteBody) => Promise<void>
  onUpdate: (ruleId: string, body: RuleWriteBody) => Promise<void>
  onDelete: (ruleId: string) => Promise<void>
  onToggle: (rule: ToolExecutionRule) => void
}) {
  // null = nothing being edited; 'new' = creating; otherwise a ruleId
  const [editing, setEditing] = useState<string | null>(null)

  async function handleSave(body: RuleWriteBody) {
    if (editing === 'new') {
      await onCreate(body)
    } else if (editing) {
      await onUpdate(editing, body)
    }
    setEditing(null)
  }

  if (loading) {
    return (
      <div style={{ padding: 16, display: 'flex', justifyContent: 'center' }}>
        <Loader2
          size={15}
          style={{ animation: 'spin 1s linear infinite', color: 'var(--text-faint)' }}
        />
      </div>
    )
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
      {rules.length > 0 && (
        <div style={{ overflowX: 'auto', border: '1px solid var(--border)', borderRadius: 8 }}>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr style={{ borderBottom: '1px solid var(--border)' }}>
                <th style={{ ...headerCell, width: 64 }}>Priority</th>
                <th style={headerCell}>Rule name</th>
                <th style={headerCell}>If param</th>
                <th style={headerCell}>Operator</th>
                <th style={headerCell}>Values</th>
                <th style={{ ...headerCell, width: 60 }}>Then</th>
                <th style={{ ...headerCell, width: 110 }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {rules.map((rule) => {
                if (editing === rule.id) {
                  return (
                    <tr key={rule.id}>
                      <td colSpan={7} style={{ padding: 8 }}>
                        <PolicyRuleEditorRow
                          initial={rule}
                          saving={saving}
                          onSave={handleSave}
                          onCancel={() => setEditing(null)}
                        />
                      </td>
                    </tr>
                  )
                }
                const first = rule.conditions[0]
                const extra = rule.conditions.length - 1
                return (
                  <tr
                    key={rule.id}
                    style={{
                      borderTop: '1px solid var(--border)',
                      opacity: rule.enabled ? 1 : 0.55,
                    }}
                  >
                    <td style={{ ...cell, fontFamily: '"SF Mono", monospace' }}>{rule.priority}</td>
                    <td style={{ ...cell, fontWeight: 500 }}>{rule.name}</td>
                    <td style={{ ...cell, fontFamily: '"SF Mono", monospace' }}>
                      {first?.param_path ?? '—'}
                    </td>
                    <td style={cell}>{first ? operatorLabel(first.operator) : '—'}</td>
                    <td style={cell}>
                      {first ? <ConditionValueChips values={first.values} /> : '—'}
                      {extra > 0 && (
                        <span style={{ fontSize: 10, color: 'var(--text-faint)' }}>
                          +{extra} more condition{extra > 1 ? 's' : ''}
                        </span>
                      )}
                    </td>
                    <td style={cell}>
                      <span
                        style={{ color: effectColor(rule.effect), fontWeight: 600, fontSize: 11 }}
                      >
                        {effectLabel(rule.effect)}
                      </span>
                    </td>
                    <td style={cell}>
                      <div style={{ display: 'flex', gap: 4, alignItems: 'center' }}>
                        <button
                          type="button"
                          onClick={() => setEditing(rule.id)}
                          aria-label="Edit rule"
                          title="Edit"
                          style={iconBtn}
                        >
                          <Pencil size={13} />
                        </button>
                        <button
                          type="button"
                          onClick={() => onToggle(rule)}
                          aria-label={rule.enabled ? 'Disable rule' : 'Enable rule'}
                          title={rule.enabled ? 'Disable' : 'Enable'}
                          style={{
                            ...iconBtn,
                            fontSize: 10,
                            width: 'auto',
                            padding: '0 6px',
                            color: 'var(--text-dim)',
                          }}
                        >
                          {rule.enabled ? 'On' : 'Off'}
                        </button>
                        <button
                          type="button"
                          onClick={() => onDelete(rule.id)}
                          aria-label="Delete rule"
                          title="Delete"
                          style={{ ...iconBtn, color: 'var(--red, #ff3b30)' }}
                        >
                          <Trash2 size={13} />
                        </button>
                      </div>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}

      {editing === 'new' ? (
        <PolicyRuleEditorRow
          initial={null}
          saving={saving}
          onSave={handleSave}
          onCancel={() => setEditing(null)}
        />
      ) : (
        <button
          type="button"
          disabled={rules.length >= RULE_LIMITS.maxRulesPerTool}
          onClick={() => setEditing('new')}
          style={{
            alignSelf: 'flex-start',
            display: 'inline-flex',
            alignItems: 'center',
            gap: 5,
            fontSize: 12,
            fontWeight: 500,
            color:
              rules.length >= RULE_LIMITS.maxRulesPerTool ? 'var(--text-faint)' : 'var(--accent)',
            background: 'transparent',
            border: '1px solid var(--border)',
            borderRadius: 6,
            padding: '5px 10px',
            cursor: rules.length >= RULE_LIMITS.maxRulesPerTool ? 'not-allowed' : 'pointer',
          }}
        >
          <Plus size={13} /> Add rule
        </button>
      )}
      {rules.length === 0 && editing !== 'new' && (
        <span style={{ fontSize: 12, color: 'var(--text-faint)' }}>
          No rules yet. Calls use the fallback above.
        </span>
      )}
    </div>
  )
}

const iconBtn: React.CSSProperties = {
  display: 'inline-flex',
  alignItems: 'center',
  justifyContent: 'center',
  height: 26,
  width: 26,
  border: '1px solid var(--border)',
  borderRadius: 5,
  background: 'transparent',
  cursor: 'pointer',
  color: 'var(--text-dim)',
}
