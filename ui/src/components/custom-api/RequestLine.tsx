const METHODS = ['GET', 'POST', 'PUT', 'PATCH', 'DELETE']

interface Props {
  method: string
  path: string
  pathParams: string[]
  onMethodChange: (method: string) => void
  onPathChange: (path: string) => void
  onParamFocus: (name: string) => void
}

export function RequestLine({
  method,
  path,
  pathParams,
  onMethodChange,
  onPathChange,
  onParamFocus,
}: Props) {
  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'stretch',
        height: 36,
        borderRadius: 7,
        border: '1px solid var(--border)',
        background: 'var(--input-bg)',
        overflow: 'hidden',
        minWidth: 0,
      }}
    >
      <div
        style={{
          position: 'relative',
          width: 84,
          flexShrink: 0,
          borderRight: '1px solid var(--border)',
        }}
      >
        <select
          value={method}
          onChange={(event) => onMethodChange(event.target.value)}
          style={{
            width: '100%',
            height: '100%',
            appearance: 'none',
            WebkitAppearance: 'none',
            border: 'none',
            outline: 'none',
            background: methodTint(method),
            color: methodColor(method),
            fontSize: 12,
            fontWeight: 700,
            fontFamily: 'var(--font-mono)',
            letterSpacing: 0.4,
            padding: '0 8px',
            textAlign: 'center',
            cursor: 'pointer',
          }}
        >
          {METHODS.map((item) => (
            <option key={item} value={item}>
              {item}
            </option>
          ))}
        </select>
      </div>

      <input
        value={path}
        onChange={(event) => onPathChange(event.target.value)}
        placeholder="/v1/items/{id}"
        spellCheck={false}
        style={{
          flex: 1,
          minWidth: 0,
          border: 'none',
          outline: 'none',
          background: 'transparent',
          color: 'var(--text)',
          fontFamily: 'var(--font-mono)',
          fontSize: 13,
          padding: '0 12px',
        }}
      />

      {pathParams.length > 0 && (
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 4,
            padding: '0 8px',
            borderLeft: '1px solid var(--border)',
            background: 'var(--surface)',
            flexShrink: 0,
            maxWidth: '45%',
            overflow: 'hidden',
          }}
        >
          {pathParams.map((param) => (
            <button
              type="button"
              key={param}
              onClick={() => onParamFocus(param)}
              title={`Jump to ${param}`}
              style={{
                border: '1px solid var(--badge-blue-dot)',
                background: 'var(--badge-blue-bg)',
                color: 'var(--badge-blue-text)',
                borderRadius: 4,
                height: 20,
                padding: '0 6px',
                fontSize: 11,
                fontWeight: 600,
                fontFamily: 'var(--font-mono)',
                cursor: 'pointer',
                whiteSpace: 'nowrap',
                lineHeight: 1,
              }}
            >
              {param}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}

function methodTint(method: string): string {
  if (method === 'GET') return 'var(--badge-green-bg)'
  if (method === 'POST') return 'var(--badge-blue-bg)'
  if (method === 'DELETE') return 'var(--badge-red-bg)'
  if (method === 'PATCH') return 'var(--badge-purple-bg)'
  return 'var(--badge-amber-bg)'
}

function methodColor(method: string): string {
  if (method === 'GET') return 'var(--badge-green-text)'
  if (method === 'POST') return 'var(--badge-blue-text)'
  if (method === 'DELETE') return 'var(--badge-red-text)'
  if (method === 'PATCH') return 'var(--badge-purple-text)'
  return 'var(--badge-amber-text)'
}
