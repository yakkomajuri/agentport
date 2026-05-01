import { Loader2, Terminal } from 'lucide-react'
import { Button } from '@/components/ui/button'
import type { ToolCallSuccess, ToolCallApprovalRequired, ToolCallDenied } from '@/api/client'

export type PlaygroundResult =
  | { status: 'ok'; data: ToolCallSuccess }
  | { status: 'approval_required'; data: ToolCallApprovalRequired }
  | { status: 'denied'; data: ToolCallDenied }
  | { status: 'error'; message: string }

interface ResponsePanelProps {
  result: PlaygroundResult | null
  running: boolean
  awaitingApproval: boolean
  durationMs: number | null
  onOpenDrawer: () => void
  onCancelPolling: () => void
}

export function ResponsePanel({
  result,
  running,
  awaitingApproval,
  durationMs,
  onOpenDrawer,
  onCancelPolling,
}: ResponsePanelProps) {
  // Idle
  if (!result && !running) {
    return (
      <div
        style={{
          flex: 1,
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          gap: 10,
          color: 'var(--text-faint)',
          userSelect: 'none',
        }}
      >
        <Terminal size={22} style={{ opacity: 0.4 }} />
        <span style={{ fontSize: 12 }}>Run a tool to see its response</span>
      </div>
    )
  }

  // Derive status row
  type DotKind = 'spin' | 'amber-spin' | 'amber' | 'green' | 'red'
  let dot: DotKind
  let label: string

  if (running) {
    dot = 'spin'
    label = 'Running…'
  } else if (awaitingApproval) {
    dot = 'amber-spin'
    label = 'Awaiting approval…'
  } else if (result?.status === 'approval_required') {
    dot = 'amber'
    label = 'Approval required'
  } else if (result?.status === 'ok' && !result.data.isError) {
    dot = 'green'
    label = 'Completed'
  } else if (result?.status === 'ok' && result.data.isError) {
    dot = 'amber'
    label = 'Tool error'
  } else if (result?.status === 'denied') {
    dot = 'red'
    label = 'Denied'
  } else {
    dot = 'red'
    label = 'Error'
  }

  const dotColorMap: Record<DotKind, string> = {
    spin: 'var(--text-faint)',
    'amber-spin': 'var(--amber)',
    amber: 'var(--amber)',
    green: 'var(--green)',
    red: 'var(--red)',
  }
  const dotColor = dotColorMap[dot]
  const isSpinning = dot === 'spin' || dot === 'amber-spin'
  const showDuration =
    !running && !awaitingApproval && durationMs !== null && result?.status === 'ok'

  const approvalData = result?.status === 'approval_required' ? result.data : null
  const showApprovalActions =
    !running && (awaitingApproval || result?.status === 'approval_required')

  return (
    <div style={{ display: 'flex', flexDirection: 'column' }}>
      {/* ── Status row — persistent, transitions in-place ── */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 8,
          paddingBottom: 12,
          borderBottom: '1px solid var(--border)',
        }}
      >
        {isSpinning ? (
          <Loader2
            size={13}
            style={{ animation: 'spin 1s linear infinite', color: dotColor, flexShrink: 0 }}
          />
        ) : (
          <span
            style={{
              width: 7,
              height: 7,
              borderRadius: '50%',
              background: dotColor,
              flexShrink: 0,
              boxShadow: `0 0 0 2px color-mix(in srgb, ${dotColor} 20%, transparent)`,
            }}
          />
        )}
        <span
          style={{
            fontSize: 12,
            fontFamily: '"SF Mono", "Fira Code", monospace',
            fontWeight: 500,
            color: 'var(--text)',
          }}
        >
          {label}
        </span>
        {showDuration && (
          <span
            style={{
              marginLeft: 'auto',
              fontSize: 10,
              fontFamily: '"SF Mono", "Fira Code", monospace',
              color: 'var(--text-faint)',
              background: 'var(--surface)',
              border: '1px solid var(--border)',
              padding: '1px 6px',
              borderRadius: 4,
            }}
          >
            {durationMs! < 1000 ? `${durationMs}ms` : `${(durationMs! / 1000).toFixed(2)}s`}
          </span>
        )}
      </div>

      {/* ── Approval actions ── */}
      {showApprovalActions && (
        <div style={{ paddingTop: 12, display: 'flex', flexDirection: 'column', gap: 10 }}>
          <p style={{ fontSize: 12, color: 'var(--text-dim)', margin: 0, lineHeight: 1.5 }}>
            {awaitingApproval
              ? 'Polling for approval every 2 seconds. Approve in the drawer and the call will auto-retry.'
              : (approvalData?.message ?? 'Approval required before this tool can run.')}
          </p>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            <Button size="sm" onClick={onOpenDrawer}>
              Open in playground
            </Button>
            {approvalData && (
              <Button
                size="sm"
                variant="outline"
                onClick={() =>
                  window.open(approvalData.approval_url, '_blank', 'noopener,noreferrer')
                }
              >
                Open in new tab
              </Button>
            )}
            {awaitingApproval && (
              <Button
                size="sm"
                variant="outline"
                onClick={onCancelPolling}
                style={{ color: 'var(--text-dim)' }}
              >
                Cancel
              </Button>
            )}
          </div>
        </div>
      )}

      {/* ── Result content — appended below for terminal states ── */}
      {!running && result?.status === 'ok' && (
        <div style={{ marginTop: 16 }}>
          <ContentBlocks blocks={result.data.content} />
        </div>
      )}

      {!running && result?.status === 'denied' && (
        <p
          style={{
            marginTop: 10,
            fontSize: 12,
            color: 'var(--text-dim)',
            lineHeight: 1.5,
            margin: '10px 0 0',
          }}
        >
          {result.data.message}
        </p>
      )}

      {!running && result?.status === 'error' && (
        <p
          style={{
            marginTop: 10,
            fontSize: 12,
            color: 'var(--text-dim)',
            lineHeight: 1.5,
            margin: '10px 0 0',
          }}
        >
          {result.message}
        </p>
      )}
    </div>
  )
}

// ── Syntax highlighting ──

type Token = { text: string; color?: string }

// Groups: [key+colon] [string value] [bool/null] [number] [punctuation] [fallback]
const JSON_RE =
  /("(?:\\.|[^"\\])*")\s*:|("(?:\\.|[^"\\])*")|(true|false|null)|(-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)|([{}[\],:])|(\s+|.)/g

function tokenizeJson(src: string): Token[] {
  const tokens: Token[] = []
  for (const m of src.matchAll(JSON_RE)) {
    if (m[1] !== undefined) {
      tokens.push({ text: m[1], color: 'var(--syn-constant)' })
      tokens.push({ text: m[0].slice(m[1].length), color: 'var(--syn-comment)' })
    } else if (m[2] !== undefined) {
      tokens.push({ text: m[2], color: 'var(--syn-string)' })
    } else if (m[3] !== undefined) {
      tokens.push({ text: m[3], color: 'var(--syn-keyword)' })
    } else if (m[4] !== undefined) {
      tokens.push({ text: m[4], color: 'var(--syn-variable)' })
    } else if (m[5] !== undefined) {
      tokens.push({ text: m[5], color: 'var(--syn-comment)' })
    } else {
      tokens.push({ text: m[0] })
    }
  }
  return tokens
}

// Groups: [comment] [quoted-str] [bool/null/~] [number] [key] [anchor/alias/tag] [doc-sep] [block-scalar] [colon] [fallback]
const YAML_RE =
  /(#[^\n]*)|("(?:\\.|[^"\\])*"|'[^']*')|(true|false|yes|no|on|off|null|~(?=[\s,\]}\n]|$))|(-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)|([\w][\w.-]*(?=\s*:(?:\s|$|\n)))|([&*!][\w.-]*)|(---|\.\.\.)|([|>](?=[ \t]*\n))|(:\s*|:\n)|(.)/g

function tokenizeYaml(src: string): Token[] {
  const tokens: Token[] = []
  let last = 0
  for (const m of src.matchAll(YAML_RE)) {
    if (m.index > last) tokens.push({ text: src.slice(last, m.index) })
    last = m.index + m[0].length
    if (m[1] !== undefined) tokens.push({ text: m[1], color: 'var(--syn-comment)' })
    else if (m[2] !== undefined) tokens.push({ text: m[2], color: 'var(--syn-string)' })
    else if (m[3] !== undefined) tokens.push({ text: m[3], color: 'var(--syn-keyword)' })
    else if (m[4] !== undefined) tokens.push({ text: m[4], color: 'var(--syn-variable)' })
    else if (m[5] !== undefined) tokens.push({ text: m[5], color: 'var(--syn-constant)' })
    else if (m[6] !== undefined) tokens.push({ text: m[6], color: 'var(--syn-tag)' })
    else if (m[7] !== undefined) tokens.push({ text: m[7], color: 'var(--syn-comment)' })
    else if (m[8] !== undefined) tokens.push({ text: m[8], color: 'var(--syn-comment)' })
    else if (m[9] !== undefined) tokens.push({ text: m[9], color: 'var(--syn-comment)' })
    else tokens.push({ text: m[0] })
  }
  if (last < src.length) tokens.push({ text: src.slice(last) })
  return tokens
}

function ResultBlock({ text }: { text: string }) {
  let display = text
  let tokens: Token[]
  try {
    display = JSON.stringify(JSON.parse(text), null, 2)
    tokens = tokenizeJson(display)
  } catch {
    tokens = tokenizeYaml(display)
  }
  return (
    <pre
      style={{
        margin: 0,
        padding: '10px 12px',
        background: 'var(--surface)',
        border: '1px solid var(--border)',
        borderRadius: 6,
        fontSize: 12,
        fontFamily: 'var(--font-mono, monospace)',
        color: 'var(--text-dim)',
        whiteSpace: 'pre-wrap',
        wordBreak: 'break-word',
        lineHeight: 1.6,
      }}
    >
      {tokens.map((tok, i) =>
        tok.color ? (
          <span key={i} style={{ color: tok.color }}>
            {tok.text}
          </span>
        ) : (
          tok.text
        ),
      )}
    </pre>
  )
}

function ContentBlocks({ blocks }: { blocks: { type: string; text: string }[] }) {
  if (!blocks || blocks.length === 0) {
    return (
      <div style={{ fontSize: 12, color: 'var(--text-faint)', fontStyle: 'italic' }}>
        (empty response)
      </div>
    )
  }
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      {blocks.map((block, i) => (
        <ResultBlock key={i} text={block.text} />
      ))}
    </div>
  )
}
