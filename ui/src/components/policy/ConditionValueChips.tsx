import { useState } from 'react'
import { X } from 'lucide-react'
import { RULE_LIMITS } from '@/lib/policyRules'

/**
 * Renders a condition's values as chips. When `editable`, supports adding values
 * (type + Enter or comma) and removing them (× on each chip).
 */
export function ConditionValueChips({
  values,
  editable = false,
  onChange,
}: {
  values: string[]
  editable?: boolean
  onChange?: (values: string[]) => void
}) {
  const [draft, setDraft] = useState('')

  function commit() {
    const trimmed = draft.trim()
    if (!trimmed || !onChange) {
      setDraft('')
      return
    }
    if (values.includes(trimmed) || values.length >= RULE_LIMITS.maxValuesPerCondition) {
      setDraft('')
      return
    }
    onChange([...values, trimmed.slice(0, RULE_LIMITS.maxValueLength)])
    setDraft('')
  }

  function remove(v: string) {
    onChange?.(values.filter((x) => x !== v))
  }

  return (
    <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: 4 }}>
      {values.map((v) => (
        <span
          key={v}
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: 4,
            fontSize: 11,
            fontFamily: '"SF Mono", "Fira Code", monospace',
            padding: '2px 6px',
            borderRadius: 4,
            background: 'var(--surface)',
            border: '1px solid var(--border)',
            color: 'var(--text)',
          }}
        >
          {v}
          {editable && (
            <button
              type="button"
              onClick={() => remove(v)}
              aria-label={`Remove ${v}`}
              style={{
                display: 'inline-flex',
                border: 'none',
                background: 'transparent',
                padding: 0,
                cursor: 'pointer',
                color: 'var(--text-faint)',
              }}
            >
              <X size={11} />
            </button>
          )}
        </span>
      ))}
      {editable && (
        <input
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' || e.key === ',') {
              e.preventDefault()
              commit()
            } else if (e.key === 'Backspace' && !draft && values.length) {
              remove(values[values.length - 1])
            }
          }}
          onBlur={commit}
          placeholder="add value…"
          style={{
            flex: 1,
            minWidth: 90,
            border: 'none',
            outline: 'none',
            background: 'transparent',
            fontSize: 11,
            fontFamily: '"SF Mono", "Fira Code", monospace',
            color: 'var(--text)',
          }}
        />
      )}
    </div>
  )
}
