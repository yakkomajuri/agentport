import { ChevronRight, Play, Trash2 } from 'lucide-react'
import { useState } from 'react'
import { useIsMobile } from '@/lib/useMediaQuery'
import { ParamSection } from './ParamSection'
import { RequestLine } from './RequestLine'
import { RequestPreview } from './RequestPreview'
import { ResponsePanel } from './ResponsePanel'
import type { DraftParam, DraftTool, ParamLocation } from './types'

interface Props {
  tool: DraftTool
  pathParams: string[]
  requestPreview: string
  onChange: (tool: DraftTool) => void
  onRemove: () => void
  onRun: () => void
}

export function ToolCard({ tool, pathParams, requestPreview, onChange, onRemove, onRun }: Props) {
  const isMobile = useIsMobile()

  function patch(update: Partial<DraftTool>) {
    onChange({ ...tool, ...update })
  }

  function updateParam(param: DraftParam) {
    patch({ params: tool.params.map((item) => (item.id === param.id ? param : item)) })
  }

  function removeParam(id: string) {
    patch({ params: tool.params.filter((item) => item.id !== id) })
  }

  function addParam(location: ParamLocation) {
    const sameLoc = tool.params.filter((p) => p.location === location).length
    patch({
      params: [
        ...tool.params,
        {
          id: crypto.randomUUID(),
          name: `param_${sameLoc + 1}`,
          type: 'string',
          description: '',
          required: false,
          defaultValue: '',
          enumText: '',
          items: '',
          location,
          sample: '',
        },
      ],
      expanded: true,
    })
  }

  const pathParamSet = new Set(pathParams)
  const pathParamItems = tool.params.filter((p) => p.location === 'path')
  const queryParams = tool.params.filter((p) => p.location === 'query')
  const bodyParams = tool.params.filter((p) => p.location === 'body')
  const [focusedParam, setFocusedParam] = useTemporaryFocus()

  return (
    <div
      style={{
        border: '1px solid var(--border)',
        borderRadius: 10,
        background: 'var(--card-bg)',
        boxShadow: 'var(--card-shadow)',
        overflow: 'hidden',
      }}
    >
      {/* Headline */}
      <div
        style={{
          display: 'flex',
          alignItems: tool.expanded ? 'flex-start' : 'center',
          gap: 10,
          padding: tool.expanded ? '12px 12px 8px 10px' : '10px 12px',
        }}
      >
        <button
          type="button"
          onClick={() => patch({ expanded: !tool.expanded })}
          aria-label={tool.expanded ? 'Collapse' : 'Expand'}
          title={tool.expanded ? 'Collapse' : 'Expand'}
          style={{
            ...iconButtonStyle,
            background: 'transparent',
            border: 'none',
            marginTop: tool.expanded ? 2 : 0,
          }}
        >
          <ChevronRight
            size={14}
            style={{
              transform: tool.expanded ? 'rotate(90deg)' : 'rotate(0deg)',
              transition: 'transform 120ms ease',
              color: 'var(--text-dim)',
            }}
          />
        </button>

        {tool.expanded ? (
          <div style={{ flex: 1, minWidth: 0 }}>
            <input
              value={tool.name}
              onChange={(event) => patch({ name: event.target.value })}
              placeholder="tool_name"
              spellCheck={false}
              style={{
                width: '100%',
                border: 'none',
                outline: 'none',
                background: 'transparent',
                color: 'var(--text)',
                fontSize: 14,
                fontWeight: 600,
                fontFamily: 'var(--font-mono)',
                padding: 0,
              }}
            />
            <input
              value={tool.description}
              onChange={(event) => patch({ description: event.target.value })}
              placeholder="What does this tool do? (the agent sees this)"
              style={{
                width: '100%',
                border: 'none',
                outline: 'none',
                background: 'transparent',
                color: 'var(--text-dim)',
                fontSize: 12,
                fontFamily: 'inherit',
                padding: '3px 0 0',
              }}
            />
          </div>
        ) : (
          <CollapsedSummary
            method={tool.method}
            name={tool.name}
            path={tool.path}
            description={tool.description}
            isMobile={isMobile}
          />
        )}

        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 4,
            flexShrink: 0,
            marginTop: tool.expanded ? 2 : 0,
          }}
        >
          <button
            type="button"
            onClick={onRun}
            disabled={tool.running}
            style={{
              height: 28,
              borderRadius: 6,
              border: '1px solid var(--border)',
              background: 'var(--content-bg)',
              color: 'var(--text)',
              display: 'inline-flex',
              alignItems: 'center',
              gap: 5,
              justifyContent: 'center',
              cursor: tool.running ? 'wait' : 'pointer',
              padding: '0 10px',
              fontFamily: 'inherit',
              fontSize: 12,
              fontWeight: 600,
            }}
          >
            <Play size={12} />
            <span>{tool.running ? 'Running…' : 'Run'}</span>
          </button>
          <button
            type="button"
            onClick={onRemove}
            aria-label="Remove tool"
            title="Remove tool"
            style={{
              ...iconButtonStyle,
              color: 'var(--text-dim)',
            }}
          >
            <Trash2 size={12} />
          </button>
        </div>
      </div>

      {tool.expanded && (
        <>
          <div style={{ padding: '0 12px 12px' }}>
            <RequestLine
              method={tool.method}
              path={tool.path}
              pathParams={pathParams}
              onMethodChange={(method) => patch({ method })}
              onPathChange={(path) => patch({ path })}
              onParamFocus={setFocusedParam}
            />
          </div>

          <div
            style={{
              borderTop: '1px solid var(--border)',
              background: 'var(--content-bg)',
              padding: '8px 0',
              display: 'flex',
              flexDirection: 'column',
              gap: 4,
            }}
          >
            <ParamSection
              title="Path"
              hint={
                pathParams.length === 0 ? 'add {name} tokens to your URL' : 'derived from the URL'
              }
              params={pathParamItems}
              pathParams={pathParamSet}
              focusedParam={focusedParam}
              onParamChange={updateParam}
              onParamRemove={removeParam}
            />
            <ParamSection
              title="Query"
              hint="appended to the URL"
              params={queryParams}
              pathParams={pathParamSet}
              focusedParam={focusedParam}
              onParamChange={updateParam}
              onParamRemove={removeParam}
              onAdd={() => addParam('query')}
            />
            <ParamSection
              title="Body"
              hint="sent as JSON"
              params={bodyParams}
              pathParams={pathParamSet}
              focusedParam={focusedParam}
              onParamChange={updateParam}
              onParamRemove={removeParam}
              onAdd={() => addParam('body')}
            />
          </div>

          <div style={{ borderTop: '1px solid var(--border)', paddingTop: 12 }}>
            <RequestPreview preview={requestPreview} />
          </div>
        </>
      )}

      <ResponsePanel result={tool.result} />
    </div>
  )
}

function CollapsedSummary({
  method,
  name,
  path,
  description,
  isMobile,
}: {
  method: string
  name: string
  path: string
  description: string
  isMobile: boolean
}) {
  return (
    <div style={{ flex: 1, minWidth: 0, display: 'flex', alignItems: 'center', gap: 10 }}>
      <MethodTag method={method} />
      <span
        style={{
          color: 'var(--text)',
          fontFamily: 'var(--font-mono)',
          fontSize: 13,
          fontWeight: 600,
          flexShrink: 0,
        }}
      >
        {name || 'untitled'}
      </span>
      <span
        style={{
          color: 'var(--text-faint)',
          fontFamily: 'var(--font-mono)',
          fontSize: 12,
          overflow: 'hidden',
          textOverflow: 'ellipsis',
          whiteSpace: 'nowrap',
          minWidth: 0,
          flex: 1,
        }}
      >
        {path || '/'}
      </span>
      {!isMobile && description && (
        <span
          style={{
            color: 'var(--text-dim)',
            fontSize: 12,
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
            maxWidth: '30%',
            flexShrink: 0,
          }}
        >
          {description}
        </span>
      )}
    </div>
  )
}

function MethodTag({ method }: { method: string }) {
  return (
    <span
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        justifyContent: 'center',
        height: 20,
        minWidth: 46,
        padding: '0 6px',
        borderRadius: 4,
        background: methodBg(method),
        color: methodText(method),
        fontFamily: 'var(--font-mono)',
        fontSize: 10,
        fontWeight: 700,
        letterSpacing: 0.4,
        flexShrink: 0,
      }}
    >
      {method}
    </span>
  )
}

function methodBg(method: string): string {
  if (method === 'GET') return 'var(--badge-green-bg)'
  if (method === 'POST') return 'var(--badge-blue-bg)'
  if (method === 'DELETE') return 'var(--badge-red-bg)'
  if (method === 'PATCH') return 'var(--badge-purple-bg)'
  return 'var(--badge-amber-bg)'
}

function methodText(method: string): string {
  if (method === 'GET') return 'var(--badge-green-text)'
  if (method === 'POST') return 'var(--badge-blue-text)'
  if (method === 'DELETE') return 'var(--badge-red-text)'
  if (method === 'PATCH') return 'var(--badge-purple-text)'
  return 'var(--badge-amber-text)'
}

function useTemporaryFocus(): [string | null, (name: string) => void] {
  const [focused, setFocused] = useState<string | null>(null)
  function focus(name: string) {
    setFocused(name)
    window.setTimeout(() => setFocused(null), 1600)
  }
  return [focused, focus]
}

const iconButtonStyle: React.CSSProperties = {
  width: 26,
  height: 26,
  border: '1px solid var(--border)',
  borderRadius: 5,
  background: 'var(--content-bg)',
  display: 'inline-flex',
  alignItems: 'center',
  justifyContent: 'center',
  cursor: 'pointer',
  padding: 0,
}
