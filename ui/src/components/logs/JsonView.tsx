import type { CSSProperties, ReactNode } from 'react'

// ── JSON syntax highlighter ──────────────────────────────────────────────────

// Tokenizes a pre-formatted JSON string and wraps tokens in colored spans.
// Uses the project's --syn-* and --code-* CSS variables from index.css.
function JsonHighlight({ json }: { json: string }) {
  // Groups: [1]=string [2]=optional colon (key) [3]=keyword [4]=number [5]=punctuation
  const TOKEN_RE =
    /("(?:[^"\\]|\\.)*")(\s*:)?|(true|false|null)|(-?\d+(?:\.\d*)?(?:[eE][+-]?\d+)?)|([{}[\],])/g

  const parts: ReactNode[] = []
  let last = 0
  let k = 0
  let match: RegExpExecArray | null

  while ((match = TOKEN_RE.exec(json)) !== null) {
    if (match.index > last) parts.push(json.slice(last, match.index))

    if (match[1] !== undefined) {
      if (match[2] !== undefined) {
        // Object key
        parts.push(
          <span key={k++} style={{ color: 'var(--syn-function)' }}>
            {match[1]}
          </span>,
        )
        parts.push(
          <span key={k++} style={{ color: 'var(--text-faint)' }}>
            {match[2]}
          </span>,
        )
      } else {
        // String value
        parts.push(
          <span key={k++} style={{ color: 'var(--syn-string)' }}>
            {match[1]}
          </span>,
        )
      }
    } else if (match[3] !== undefined) {
      // true / false / null
      parts.push(
        <span key={k++} style={{ color: 'var(--syn-keyword)' }}>
          {match[3]}
        </span>,
      )
    } else if (match[4] !== undefined) {
      // Number
      parts.push(
        <span key={k++} style={{ color: 'var(--syn-constant)' }}>
          {match[4]}
        </span>,
      )
    } else if (match[5] !== undefined) {
      // Punctuation: { } [ ] , :
      parts.push(
        <span key={k++} style={{ color: 'var(--text-faint)' }}>
          {match[5]}
        </span>,
      )
    }

    last = TOKEN_RE.lastIndex
  }

  if (last < json.length) parts.push(json.slice(last))

  return <>{parts}</>
}

// ── Code block wrapper ───────────────────────────────────────────────────────

function CodeBlock({ children, style }: { children: ReactNode; style?: CSSProperties }) {
  return (
    <pre
      style={{
        fontSize: 11,
        fontFamily: 'var(--font-mono, monospace)',
        background: 'var(--code-bg)',
        color: 'var(--code-text)',
        border: '1px solid var(--border)',
        borderRadius: 6,
        padding: '10px 12px',
        margin: 0,
        whiteSpace: 'pre-wrap',
        wordBreak: 'break-word',
        lineHeight: 1.6,
        ...style,
      }}
    >
      {children}
    </pre>
  )
}

// ── MCP result format detection ──────────────────────────────────────────────

type McpContentItem = {
  type: string
  text?: string
  [key: string]: unknown
}

type McpResult = {
  content: McpContentItem[]
  isError?: boolean
}

function isMcpResult(v: unknown): v is McpResult {
  if (typeof v !== 'object' || v === null) return false
  const r = v as McpResult
  return (
    Array.isArray(r.content) &&
    r.content.length > 0 &&
    r.content.every((item) => typeof item === 'object' && item !== null && 'type' in item)
  )
}

// Attempt to parse a string as JSON. Returns the parsed value or undefined.
function tryParseJson(s: string): unknown {
  const trimmed = s.trim()
  if (trimmed[0] !== '{' && trimmed[0] !== '[') return undefined
  try {
    return JSON.parse(s)
  } catch {
    return undefined
  }
}

// ── MCP content renderer ─────────────────────────────────────────────────────

function ContentLabel({ label }: { label: string }) {
  return (
    <div
      style={{
        fontSize: 10,
        color: 'var(--text-faint)',
        fontFamily: 'var(--font-mono, monospace)',
        marginBottom: 4,
        textTransform: 'uppercase',
        letterSpacing: '0.04em',
      }}
    >
      {label}
    </div>
  )
}

function McpTextItem({ text, label }: { text: string; label?: string }) {
  const parsed = tryParseJson(text)

  return (
    <div>
      {label && <ContentLabel label={label} />}
      <CodeBlock>
        {parsed !== undefined ? (
          <JsonHighlight json={JSON.stringify(parsed, null, 2)} />
        ) : (
          text
        )}
      </CodeBlock>
    </div>
  )
}

function McpResultView({ result }: { result: McpResult }) {
  const multi = result.content.length > 1

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      {result.content.map((item, idx) => {
        const label = multi ? `${item.type} [${idx + 1}]` : undefined

        if (item.type === 'text' && typeof item.text === 'string') {
          return <McpTextItem key={idx} text={item.text} label={label} />
        }

        // image, resource, or unknown content type — show as JSON
        return (
          <div key={idx}>
            {label && <ContentLabel label={label} />}
            <CodeBlock>
              <JsonHighlight json={JSON.stringify(item, null, 2)} />
            </CodeBlock>
          </div>
        )
      })}
    </div>
  )
}

// ── Public API ───────────────────────────────────────────────────────────────

/**
 * Renders a tool result value with syntax highlighting.
 *
 * - MCP tool results ({ content: [...], isError: bool }) are unwrapped: each
 *   content item is rendered individually. Text items whose content is valid
 *   JSON are parsed and pretty-printed rather than shown as an escaped string.
 * - Everything else is pretty-printed as syntax-highlighted JSON.
 */
export function ResultView({ result }: { result: unknown }) {
  if (isMcpResult(result)) {
    return <McpResultView result={result} />
  }

  return (
    <CodeBlock>
      <JsonHighlight json={JSON.stringify(result, null, 2)} />
    </CodeBlock>
  )
}
