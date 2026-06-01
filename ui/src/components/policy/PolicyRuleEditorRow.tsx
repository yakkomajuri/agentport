import { useState } from 'react'
import { Plus, Trash2 } from 'lucide-react'
import type {
  RuleCondition,
  RuleEffect,
  RuleOperator,
  RuleWriteBody,
  ToolExecutionRule,
} from '@/api/client'
import { RULE_EFFECTS, RULE_LIMITS, RULE_OPERATORS } from '@/lib/policyRules'
import { ConditionValueChips } from './ConditionValueChips'

const inputStyle: React.CSSProperties = {
  height: 28,
  padding: '0 8px',
  border: '1px solid var(--border)',
  borderRadius: 5,
  background: 'var(--input-bg)',
  fontSize: 12,
  color: 'var(--text)',
  outline: 'none',
  fontFamily: 'inherit',
}

function emptyCondition(): RuleCondition {
  return { param_path: '', operator: 'contains', values: [] }
}

/**
 * Compact inline editor for a single rule. Used both for creating a new rule and
 * editing an existing one. Emits a RuleWriteBody on save; the parent persists it.
 */
export function PolicyRuleEditorRow({
  initial,
  saving,
  onSave,
  onCancel,
}: {
  initial: ToolExecutionRule | null
  saving: boolean
  onSave: (body: RuleWriteBody) => void
  onCancel: () => void
}) {
  const [name, setName] = useState(initial?.name ?? '')
  const [priority, setPriority] = useState(initial?.priority ?? 100)
  const [effect, setEffect] = useState<RuleEffect>(initial?.effect ?? 'require_approval')
  const [enabled, setEnabled] = useState(initial?.enabled ?? true)
  const [conditions, setConditions] = useState<RuleCondition[]>(
    initial?.conditions?.length ? initial.conditions.map((c) => ({ ...c })) : [emptyCondition()],
  )

  function patchCondition(i: number, patch: Partial<RuleCondition>) {
    setConditions((cs) => cs.map((c, idx) => (idx === i ? { ...c, ...patch } : c)))
  }

  const valid =
    name.trim().length > 0 &&
    conditions.every((c) => c.param_path.trim().length > 0 && c.values.length > 0)

  function handleSave() {
    if (!valid) return
    onSave({
      name: name.trim(),
      priority,
      effect,
      enabled,
      conditions: conditions.map((c, i) => ({
        param_path: c.param_path.trim(),
        operator: c.operator,
        values: c.values,
        position: i,
      })),
    })
  }

  return (
    <div
      style={{
        border: '1px solid var(--accent)',
        borderRadius: 8,
        padding: 12,
        background: 'var(--surface)',
        display: 'flex',
        flexDirection: 'column',
        gap: 10,
      }}
    >
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, alignItems: 'center' }}>
        <input
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Rule name"
          style={{ ...inputStyle, flex: 1, minWidth: 160 }}
        />
        <label
          style={{
            fontSize: 11,
            color: 'var(--text-dim)',
            display: 'flex',
            gap: 4,
            alignItems: 'center',
          }}
        >
          Priority
          <input
            type="number"
            value={priority}
            onChange={(e) => setPriority(Number(e.target.value))}
            style={{ ...inputStyle, width: 70 }}
          />
        </label>
        <label
          style={{
            fontSize: 11,
            color: 'var(--text-dim)',
            display: 'flex',
            gap: 5,
            alignItems: 'center',
          }}
        >
          <input type="checkbox" checked={enabled} onChange={(e) => setEnabled(e.target.checked)} />
          Enabled
        </label>
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <span style={{ fontSize: 11, color: 'var(--text-dim)' }}>Then</span>
        <div
          style={{
            display: 'inline-flex',
            border: '1px solid var(--border)',
            borderRadius: 6,
            overflow: 'hidden',
          }}
        >
          {RULE_EFFECTS.map((e, i) => {
            const active = effect === e.effect
            return (
              <button
                key={e.effect}
                type="button"
                onClick={() => setEffect(e.effect)}
                style={{
                  padding: '4px 12px',
                  fontSize: 12,
                  fontWeight: active ? 600 : 400,
                  border: 'none',
                  borderLeft: i > 0 ? '1px solid var(--border)' : 'none',
                  background: active ? e.color : 'transparent',
                  color: active ? '#fff' : 'var(--text-dim)',
                  cursor: 'pointer',
                }}
              >
                {e.label}
              </button>
            )
          })}
        </div>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        <span style={{ fontSize: 11, color: 'var(--text-dim)', fontWeight: 500 }}>
          Conditions <span style={{ color: 'var(--text-faint)' }}>(all must match)</span>
        </span>
        {conditions.map((c, i) => (
          <div key={i} style={{ display: 'flex', flexWrap: 'wrap', gap: 6, alignItems: 'center' }}>
            <input
              value={c.param_path}
              onChange={(e) => patchCondition(i, { param_path: e.target.value })}
              placeholder="param (e.g. to)"
              style={{ ...inputStyle, width: 120, fontFamily: '"SF Mono", monospace' }}
            />
            <select
              value={c.operator}
              onChange={(e) => patchCondition(i, { operator: e.target.value as RuleOperator })}
              style={{ ...inputStyle, width: 110 }}
            >
              {RULE_OPERATORS.map((o) => (
                <option key={o.operator} value={o.operator}>
                  {o.label}
                </option>
              ))}
            </select>
            <div
              style={{
                flex: 1,
                minWidth: 160,
                border: '1px solid var(--border)',
                borderRadius: 5,
                padding: '4px 6px',
                background: 'var(--input-bg)',
              }}
            >
              <ConditionValueChips
                values={c.values}
                editable
                onChange={(values) => patchCondition(i, { values })}
              />
            </div>
            {conditions.length > 1 && (
              <button
                type="button"
                onClick={() => setConditions((cs) => cs.filter((_, idx) => idx !== i))}
                aria-label="Remove condition"
                style={{
                  border: '1px solid var(--border)',
                  borderRadius: 5,
                  background: 'transparent',
                  cursor: 'pointer',
                  color: 'var(--text-faint)',
                  height: 28,
                  width: 28,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                }}
              >
                <Trash2 size={13} />
              </button>
            )}
          </div>
        ))}
        {conditions.length < RULE_LIMITS.maxConditionsPerRule && (
          <button
            type="button"
            onClick={() => setConditions((cs) => [...cs, emptyCondition()])}
            style={{
              alignSelf: 'flex-start',
              display: 'inline-flex',
              alignItems: 'center',
              gap: 4,
              fontSize: 11,
              color: 'var(--accent)',
              background: 'transparent',
              border: 'none',
              cursor: 'pointer',
              padding: 0,
            }}
          >
            <Plus size={12} /> Add condition
          </button>
        )}
      </div>

      <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
        <button
          type="button"
          onClick={onCancel}
          disabled={saving}
          style={{
            padding: '5px 12px',
            fontSize: 12,
            border: '1px solid var(--border)',
            borderRadius: 6,
            background: 'transparent',
            color: 'var(--text-dim)',
            cursor: 'pointer',
          }}
        >
          Cancel
        </button>
        <button
          type="button"
          onClick={handleSave}
          disabled={!valid || saving}
          style={{
            padding: '5px 14px',
            fontSize: 12,
            fontWeight: 600,
            border: 'none',
            borderRadius: 6,
            background: valid ? 'var(--accent)' : 'var(--border)',
            color: '#fff',
            cursor: valid && !saving ? 'pointer' : 'not-allowed',
            opacity: saving ? 0.6 : 1,
          }}
        >
          {saving ? 'Saving…' : 'Save rule'}
        </button>
      </div>
    </div>
  )
}
