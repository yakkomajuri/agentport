import { Plus } from 'lucide-react'
import { ParamRow } from './ParamRow'
import type { DraftParam } from './types'

interface Props {
  title: string
  hint: string
  params: DraftParam[]
  pathParams: Set<string>
  focusedParam: string | null
  onParamChange: (param: DraftParam) => void
  onParamRemove: (id: string) => void
  onAdd?: () => void
}

export function ParamSection({
  title,
  hint,
  params,
  pathParams,
  focusedParam,
  onParamChange,
  onParamRemove,
  onAdd,
}: Props) {
  return (
    <div>
      <div
        style={{
          height: 28,
          display: 'flex',
          alignItems: 'center',
          gap: 8,
          padding: '0 14px 0 18px',
        }}
      >
        <span
          style={{
            fontSize: 10,
            fontWeight: 700,
            color: 'var(--text-dim)',
            textTransform: 'uppercase',
            letterSpacing: 0.5,
          }}
        >
          {title}
        </span>
        <span
          style={{
            fontSize: 11,
            color: 'var(--text-faint)',
            fontVariantNumeric: 'tabular-nums',
          }}
        >
          {params.length}
        </span>
        <span
          style={{
            fontSize: 11,
            color: 'var(--text-faint)',
            marginLeft: 4,
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
            flex: 1,
            minWidth: 0,
          }}
        >
          {hint}
        </span>
        {onAdd && (
          <button
            type="button"
            onClick={onAdd}
            aria-label={`Add ${title.toLowerCase()} param`}
            title={`Add ${title.toLowerCase()} param`}
            style={{
              width: 22,
              height: 22,
              borderRadius: 5,
              border: '1px solid var(--border)',
              background: 'var(--content-bg)',
              color: 'var(--text-dim)',
              display: 'inline-flex',
              alignItems: 'center',
              justifyContent: 'center',
              cursor: 'pointer',
              padding: 0,
              flexShrink: 0,
            }}
          >
            <Plus size={12} />
          </button>
        )}
      </div>

      {params.length > 0 && (
        <div style={{ paddingBottom: 4 }}>
          {params.map((param) => (
            <ParamRow
              key={param.id}
              param={param}
              pathLocked={pathParams.has(param.name) && param.location === 'path'}
              focused={focusedParam === param.name}
              onChange={onParamChange}
              onRemove={() => onParamRemove(param.id)}
            />
          ))}
        </div>
      )}
    </div>
  )
}
