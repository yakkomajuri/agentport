import { ChevronDown, ChevronRight, X } from 'lucide-react'
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
          alignItems: 'end',
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

        <FieldShell label="Name">
          <input
            value={param.name}
            onChange={(event) => patch({ name: event.target.value })}
            disabled={pathLocked}
            style={{
              ...inputStyle,
              fontFamily: 'var(--font-mono)',
              fontWeight: 500,
              color: pathLocked ? 'var(--text-dim)' : 'var(--text)',
              cursor: pathLocked ? 'not-allowed' : 'text',
            }}
          />
        </FieldShell>

        {!isMobile && (
          <SelectField label="Type" value={param.type} onChange={(type) => patch({ type })} />
        )}

        {!isMobile && (
          <FieldShell label="Default value for testing">
            <input
              value={param.sample}
              onChange={(event) => patch({ sample: event.target.value })}
              style={{ ...inputStyle, fontFamily: 'var(--font-mono)' }}
            />
          </FieldShell>
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
            <FieldShell label="Default value for testing">
              <input
                value={param.sample}
                onChange={(event) => patch({ sample: event.target.value })}
                style={{ ...inputStyle, fontFamily: 'var(--font-mono)' }}
              />
            </FieldShell>
          )}
          {isMobile && (
            <SelectField label="Type" value={param.type} onChange={(type) => patch({ type })} />
          )}
          <FieldShell label="Description">
            <input
              value={param.description}
              onChange={(event) => patch({ description: event.target.value })}
              style={inputStyle}
            />
          </FieldShell>
          {!pathLocked && (
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: 'minmax(0, 1fr) minmax(0, 1fr)',
                gap: 8,
              }}
            >
              <FieldShell label="Default">
                <input
                  value={param.defaultValue}
                  onChange={(event) => patch({ defaultValue: event.target.value })}
                  style={inputStyle}
                />
              </FieldShell>
              <FieldShell label="Enum values">
                <input
                  value={param.enumText}
                  onChange={(event) => patch({ enumText: event.target.value })}
                  style={inputStyle}
                />
              </FieldShell>
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

function FieldShell({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label style={fieldShellStyle}>
      <span style={fieldLabelStyle}>{label}</span>
      {children}
    </label>
  )
}

function SelectField({
  label,
  value,
  onChange,
}: {
  label: string
  value: string
  onChange: (value: string) => void
}) {
  return (
    <FieldShell label={label}>
      <span style={selectShellStyle}>
        <select
          value={value}
          onChange={(event) => onChange(event.target.value)}
          style={selectStyle}
        >
          {TYPES.map((type) => (
            <option key={type} value={type}>
              {type}
            </option>
          ))}
        </select>
        <ChevronDown size={13} aria-hidden="true" style={selectIconStyle} />
      </span>
    </FieldShell>
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

const fieldShellStyle: React.CSSProperties = {
  display: 'grid',
  gap: 4,
  minWidth: 0,
}

const fieldLabelStyle: React.CSSProperties = {
  fontSize: 10,
  fontWeight: 700,
  color: 'var(--text-faint)',
  textTransform: 'uppercase',
  letterSpacing: 0.4,
  lineHeight: 1,
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

const selectShellStyle: React.CSSProperties = {
  position: 'relative',
  display: 'block',
  minWidth: 0,
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

const selectIconStyle: React.CSSProperties = {
  position: 'absolute',
  right: 8,
  top: '50%',
  transform: 'translateY(-50%)',
  color: 'var(--text-faint)',
  pointerEvents: 'none',
}
