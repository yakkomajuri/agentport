import { useState } from 'react'
import { Input } from '@/components/ui/input'

interface SchemaProperty {
  type?: string
  description?: string
  enum?: string[]
  items?: SchemaProperty
  properties?: Record<string, SchemaProperty>
  default?: unknown
}

interface SchemaFormProps {
  schema: Record<string, unknown> | undefined
  values: Record<string, unknown>
  rawMode: boolean
  rawJson: string
  onFieldChange: (field: string, value: unknown) => void
  onRawJsonChange: (json: string) => void
}

export function SchemaForm({
  schema,
  values,
  rawMode,
  rawJson,
  onFieldChange,
  onRawJsonChange,
}: SchemaFormProps) {
  const properties = schema?.properties as Record<string, SchemaProperty> | undefined
  const required = (schema?.required as string[]) ?? []
  const hasProperties = properties && Object.keys(properties).length > 0

  if (rawMode) {
    return (
      <RawTextarea
        value={rawJson}
        onChange={onRawJsonChange}
        placeholder={'{\n  \n}'}
      />
    )
  }

  if (!hasProperties) {
    return (
      <div
        style={{
          fontSize: 12,
          color: 'var(--text-faint)',
          padding: '10px 0',
          fontStyle: 'italic',
        }}
      >
        No parameters
      </div>
    )
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
      {Object.entries(properties).map(([name, prop]) => (
        <SchemaField
          key={name}
          name={name}
          property={prop}
          required={required.includes(name)}
          value={values[name]}
          onChange={(v) => onFieldChange(name, v)}
        />
      ))}
    </div>
  )
}

function SchemaField({
  name,
  property,
  required,
  value,
  onChange,
}: {
  name: string
  property: SchemaProperty
  required: boolean
  value: unknown
  onChange: (v: unknown) => void
}) {
  const type = property.type
  const hasEnum = property.enum && property.enum.length > 0

  return (
    <div>
      {/* Label row */}
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 4, marginBottom: 5 }}>
        <span
          style={{
            fontSize: 12,
            fontWeight: 500,
            color: 'var(--text)',
          }}
        >
          {name}
        </span>
        {required && (
          <span style={{ fontSize: 11, color: 'var(--red)', lineHeight: 1 }}>*</span>
        )}
        {property.type && (
          <span style={{ fontSize: 10, color: 'var(--text-faint)', marginLeft: 2 }}>
            {property.type}
          </span>
        )}
      </div>

      {/* Description */}
      {property.description && (
        <div
          style={{
            fontSize: 11,
            color: 'var(--text-faint)',
            marginBottom: 6,
            lineHeight: 1.4,
          }}
        >
          {property.description}
        </div>
      )}

      {/* Input control */}
      {type === 'boolean' ? (
        <BooleanToggle value={!!value} onChange={onChange} />
      ) : hasEnum ? (
        <EnumSelect
          options={property.enum!}
          value={typeof value === 'string' ? value : ''}
          onChange={onChange}
        />
      ) : type === 'object' || type === 'array' ? (
        <JsonTextarea
          value={typeof value === 'string' ? value : ''}
          onChange={onChange}
          placeholder={type === 'array' ? '[]' : '{}'}
        />
      ) : (
        <Input
          type={type === 'number' || type === 'integer' ? 'number' : 'text'}
          value={typeof value === 'string' || typeof value === 'number' ? String(value) : ''}
          onChange={(e) =>
            onChange(type === 'number' || type === 'integer' ? e.target.value : e.target.value)
          }
          placeholder={property.description ? undefined : name}
          style={{
            height: 30,
            fontSize: 12,
            fontFamily:
              type === 'number' || type === 'integer'
                ? '"SF Mono", "Fira Code", monospace'
                : 'inherit',
            background: 'var(--input-bg)',
            border: '1px solid var(--border)',
            color: 'var(--text)',
          }}
        />
      )}
    </div>
  )
}

function BooleanToggle({
  value,
  onChange,
}: {
  value: boolean
  onChange: (v: boolean) => void
}) {
  return (
    <div style={{ display: 'flex', gap: 4 }}>
      {[true, false].map((opt) => (
        <button
          key={String(opt)}
          onClick={() => onChange(opt)}
          style={{
            padding: '3px 14px',
            borderRadius: 5,
            border: '1px solid var(--border)',
            fontSize: 12,
            fontFamily: '"SF Mono", "Fira Code", monospace',
            cursor: 'pointer',
            background: value === opt ? 'var(--accent)' : 'var(--input-bg)',
            color: value === opt ? 'var(--content-bg)' : 'var(--text-dim)',
            fontWeight: value === opt ? 600 : 400,
            transition: 'background 120ms, color 120ms',
          }}
        >
          {String(opt)}
        </button>
      ))}
    </div>
  )
}

function EnumSelect({
  options,
  value,
  onChange,
}: {
  options: string[]
  value: string
  onChange: (v: string) => void
}) {
  return (
    <div style={{ position: 'relative' }}>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        style={{
          width: '100%',
          height: 30,
          padding: '0 28px 0 10px',
          border: '1px solid var(--border)',
          borderRadius: 6,
          background: 'var(--input-bg)',
          fontSize: 12,
          fontFamily: 'inherit',
          color: value ? 'var(--text)' : 'var(--text-faint)',
          outline: 'none',
          appearance: 'none',
          cursor: 'pointer',
        }}
      >
        <option value="">Choose…</option>
        {options.map((opt) => (
          <option key={opt} value={opt}>
            {opt}
          </option>
        ))}
      </select>
      <svg
        width="10"
        height="10"
        viewBox="0 0 10 10"
        fill="none"
        style={{
          position: 'absolute',
          right: 9,
          top: '50%',
          transform: 'translateY(-50%)',
          pointerEvents: 'none',
          color: 'var(--text-faint)',
        }}
      >
        <path
          d="M2 3.5L5 6.5L8 3.5"
          stroke="currentColor"
          strokeWidth="1.4"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
    </div>
  )
}

function JsonTextarea({
  value,
  onChange,
  placeholder,
}: {
  value: string
  onChange: (v: string) => void
  placeholder: string
}) {
  const [invalid, setInvalid] = useState(false)

  function handleBlur() {
    if (!value.trim()) {
      setInvalid(false)
      return
    }
    try {
      JSON.parse(value)
      setInvalid(false)
    } catch {
      setInvalid(true)
    }
  }

  return (
    <div>
      <textarea
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onBlur={handleBlur}
        placeholder={placeholder}
        rows={4}
        style={{
          width: '100%',
          padding: '6px 10px',
          border: `1px solid ${invalid ? 'var(--red)' : 'var(--border)'}`,
          borderRadius: 6,
          background: 'var(--input-bg)',
          fontSize: 11,
          fontFamily: '"SF Mono", "Fira Code", monospace',
          color: 'var(--text)',
          outline: 'none',
          resize: 'vertical',
          lineHeight: 1.5,
          boxSizing: 'border-box',
          transition: 'border-color 120ms',
        }}
      />
      {invalid && (
        <div style={{ fontSize: 11, color: 'var(--red)', marginTop: 3 }}>Invalid JSON</div>
      )}
    </div>
  )
}

function RawTextarea({
  value,
  onChange,
  placeholder,
}: {
  value: string
  onChange: (v: string) => void
  placeholder: string
}) {
  const [invalid, setInvalid] = useState(false)

  function handleBlur() {
    if (!value.trim()) {
      setInvalid(false)
      return
    }
    try {
      JSON.parse(value)
      setInvalid(false)
    } catch {
      setInvalid(true)
    }
  }

  return (
    <div>
      <textarea
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onBlur={handleBlur}
        placeholder={placeholder}
        rows={8}
        style={{
          width: '100%',
          padding: '8px 10px',
          border: `1px solid ${invalid ? 'var(--red)' : 'var(--border)'}`,
          borderRadius: 6,
          background: 'var(--input-bg)',
          fontSize: 11,
          fontFamily: '"SF Mono", "Fira Code", monospace',
          color: 'var(--text)',
          outline: 'none',
          resize: 'vertical',
          lineHeight: 1.6,
          boxSizing: 'border-box',
          transition: 'border-color 120ms',
        }}
      />
      {invalid && (
        <div style={{ fontSize: 11, color: 'var(--red)', marginTop: 3 }}>Invalid JSON</div>
      )}
    </div>
  )
}
