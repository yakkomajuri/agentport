import { ChevronRight, X } from 'lucide-react'
import { useState } from 'react'
import { useIsMobile } from '@/lib/useMediaQuery'
import type { DraftParam, ParamLocation } from './types'

const TYPES = ['string', 'integer', 'number', 'boolean', 'array', 'object']

interface Props {
  param: DraftParam
  pathLocked: boolean
  focused: boolean
  onChange: (param: DraftParam) => void
  onRemove: () => void
}

export function ParamRow({ param, pathLocked, focused, onChange, onRemove }: Props) {
  const [open, setOpen] = useState(false)
  const isMobile = useIsMobile()

  function patch(update: Partial<DraftParam>) {
    onChange({ ...param, ...update })
  }

  return (
    <div
      style={{
        background: focused ? 'var(--surface-selected)' : 'transparent',
        transition: 'background 200ms ease',
      }}
    >
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: isMobile
            ? '18px minmax(0, 1fr) 24px'
            : '18px minmax(140px, 1.4fr) 110px minmax(120px, 1fr) 24px',
          gap: 8,
          alignItems: 'center',
          padding: '7px 14px 7px 18px',
        }}
      >
        <button
          type="button"
          onClick={() => setOpen((v) => !v)}
          aria-label={open ? 'Collapse' : 'More options'}
          title={open ? 'Collapse' : 'More options'}
          style={chevronButtonStyle}
        >
          <ChevronRight
            size={12}
            style={{
              transform: open ? 'rotate(90deg)' : 'rotate(0deg)',
              transition: 'transform 120ms ease',
              color: 'var(--text-faint)',
            }}
          />
        </button>

        <input
          value={param.name}
          onChange={(event) => patch({ name: event.target.value })}
          disabled={pathLocked}
          placeholder="name"
          style={{
            ...nameInputStyle,
            color: pathLocked ? 'var(--text-dim)' : 'var(--text)',
          }}
        />

        {!isMobile && (
          <select
            value={param.type}
            onChange={(event) => patch({ type: event.target.value })}
            style={selectStyle}
          >
            {TYPES.map((type) => (
              <option key={type} value={type}>
                {type}
              </option>
            ))}
          </select>
        )}

        {!isMobile && (
          <input
            value={param.sample}
            onChange={(event) => patch({ sample: event.target.value })}
            placeholder="sample"
            style={{ ...inputStyle, fontFamily: 'var(--font-mono)' }}
          />
        )}

        <button
          type="button"
          onClick={onRemove}
          aria-label="Remove"
          title="Remove"
          disabled={pathLocked}
          style={{
            ...iconButtonStyle,
            color: pathLocked ? 'var(--text-faint)' : 'var(--text-dim)',
            opacity: pathLocked ? 0.4 : 1,
            cursor: pathLocked ? 'not-allowed' : 'pointer',
          }}
        >
          <X size={12} />
        </button>
      </div>

      {open && (
        <div
          style={{
            padding: '0 14px 12px 44px',
            display: 'grid',
            gridTemplateColumns: isMobile ? 'minmax(0, 1fr)' : 'minmax(0, 1.4fr) minmax(0, 1fr)',
            gap: 8,
            alignItems: 'start',
          }}
        >
          {isMobile && (
            <input
              value={param.sample}
              onChange={(event) => patch({ sample: event.target.value })}
              placeholder="Sample"
              style={inputStyle}
            />
          )}
          {isMobile && (
            <select
              value={param.type}
              onChange={(event) => patch({ type: event.target.value })}
              style={selectStyle}
            >
              {TYPES.map((type) => (
                <option key={type} value={type}>
                  {type}
                </option>
              ))}
            </select>
          )}
          <input
            value={param.description}
            onChange={(event) => patch({ description: event.target.value })}
            placeholder="Description (helps the agent know when to use this)"
            style={inputStyle}
          />
          {!pathLocked && (
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: 'minmax(0, 1fr) minmax(0, 1fr)',
                gap: 8,
              }}
            >
              <input
                value={param.defaultValue}
                onChange={(event) => patch({ defaultValue: event.target.value })}
                placeholder="Default"
                style={inputStyle}
              />
              <input
                value={param.enumText}
                onChange={(event) => patch({ enumText: event.target.value })}
                placeholder="Enum (a, b, c)"
                style={inputStyle}
              />
            </div>
          )}
          {!pathLocked && (
            <div
              style={{
                gridColumn: isMobile ? 'auto' : '1 / -1',
                display: 'flex',
                alignItems: 'center',
                gap: 16,
                flexWrap: 'wrap',
                marginTop: 2,
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <span style={miniLabelStyle}>Send as</span>
                <LocationToggle
                  value={param.location === 'path' ? 'body' : param.location}
                  onChange={(location) => patch({ location, orphaned: false })}
                />
              </div>
              <label
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: 6,
                  cursor: 'pointer',
                  color: 'var(--text-dim)',
                  fontSize: 12,
                }}
              >
                <input
                  type="checkbox"
                  checked={param.required}
                  onChange={(event) => patch({ required: event.target.checked })}
                />
                Required
              </label>
              {param.orphaned && (
                <span
                  style={{
                    fontSize: 11,
                    color: 'var(--badge-amber-text)',
                  }}
                >
                  was a path param — no longer in URL
                </span>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

function LocationToggle({
  value,
  onChange,
}: {
  value: ParamLocation
  onChange: (value: ParamLocation) => void
}) {
  const options: ParamLocation[] = ['query', 'body']
  return (
    <div
      style={{
        display: 'inline-flex',
        gap: 0,
        padding: 2,
        borderRadius: 6,
        background: 'var(--surface)',
        border: '1px solid var(--border)',
      }}
    >
      {options.map((opt) => (
        <button
          type="button"
          key={opt}
          onClick={() => onChange(opt)}
          style={{
            height: 22,
            padding: '0 10px',
            borderRadius: 4,
            border: 'none',
            background: value === opt ? 'var(--content-bg)' : 'transparent',
            color: value === opt ? 'var(--text)' : 'var(--text-dim)',
            fontSize: 11,
            fontWeight: 600,
            cursor: 'pointer',
            fontFamily: 'inherit',
            boxShadow: value === opt ? 'var(--card-shadow)' : 'none',
          }}
        >
          {opt}
        </button>
      ))}
    </div>
  )
}

const miniLabelStyle: React.CSSProperties = {
  fontSize: 10,
  fontWeight: 600,
  color: 'var(--text-faint)',
  textTransform: 'uppercase',
  letterSpacing: 0.4,
}

const chevronButtonStyle: React.CSSProperties = {
  width: 18,
  height: 18,
  border: 'none',
  borderRadius: 4,
  background: 'transparent',
  display: 'inline-flex',
  alignItems: 'center',
  justifyContent: 'center',
  cursor: 'pointer',
  padding: 0,
}

const iconButtonStyle: React.CSSProperties = {
  width: 22,
  height: 22,
  border: 'none',
  borderRadius: 4,
  background: 'transparent',
  display: 'inline-flex',
  alignItems: 'center',
  justifyContent: 'center',
  padding: 0,
}

const inputStyle: React.CSSProperties = {
  width: '100%',
  minWidth: 0,
  height: 28,
  border: '1px solid var(--border)',
  borderRadius: 5,
  background: 'var(--input-bg)',
  color: 'var(--text)',
  fontSize: 12,
  fontFamily: 'inherit',
  outline: 'none',
  padding: '0 8px',
}

const nameInputStyle: React.CSSProperties = {
  ...inputStyle,
  fontFamily: 'var(--font-mono)',
  fontWeight: 500,
  background: 'transparent',
  border: '1px solid transparent',
  padding: '0 6px',
}

const selectStyle: React.CSSProperties = {
  ...inputStyle,
  appearance: 'none',
  WebkitAppearance: 'none',
  paddingRight: 20,
  fontFamily: 'var(--font-mono)',
  color: 'var(--text-dim)',
  cursor: 'pointer',
}
