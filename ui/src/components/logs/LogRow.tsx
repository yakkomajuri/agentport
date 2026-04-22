import type { LogEntry } from '@/api/client'

function timeAgo(ts: string): string {
  const diff = Date.now() - new Date(ts).getTime()
  const secs = Math.floor(diff / 1000)
  if (secs <= 0) return 'just now'
  if (secs < 60) return `${secs}s ago`
  const mins = Math.floor(secs / 60)
  if (mins < 60) return `${mins}m ago`
  const hrs = Math.floor(mins / 60)
  if (hrs < 24) return `${hrs}h ago`
  return new Date(ts).toLocaleDateString()
}

function formatDuration(ms: number): string {
  return ms >= 1000 ? `${(ms / 1000).toFixed(1)}s` : `${ms}ms`
}

const ACCESS_LABELS: Record<string, { label: string; color: string }> = {
  approved_once:  { label: 'approved once',   color: 'var(--green)' },
  approved_exact: { label: 'approved forever', color: 'var(--green)' },
  approved_any:   { label: 'never ask again',  color: 'var(--blue)' },
}

export function LogRow({
  entry,
  onClick,
}: {
  entry: LogEntry
  onClick: () => void
}) {
  const isPending  = entry.outcome === 'pending'
  const isApproved = entry.outcome === 'approved'
  const isError    = entry.outcome === 'error'
  const isDenied   = entry.outcome === 'denied'
  const isExpired  =
    isPending &&
    !!entry.approval_expires_at &&
    new Date(entry.approval_expires_at) <= new Date()

  const dotColor = (isDenied || isError) ? 'var(--red)'
    : isExpired  ? 'var(--text-faint)'
    : isPending  ? 'var(--amber)'
    : isApproved ? 'var(--blue, #4f8ef7)'
    : 'var(--green)'

  const accessTag = entry.access_reason ? ACCESS_LABELS[entry.access_reason] : null

  return (
    <div
      onClick={onClick}
      style={{
        display: 'grid',
        gridTemplateColumns: '16px 1fr auto auto',
        alignItems: 'center',
        gap: '0 12px',
        padding: '9px 20px',
        cursor: 'pointer',
        borderBottom: '1px solid var(--border)',
        transition: 'background 100ms',
      }}
      onMouseEnter={(e) => (e.currentTarget.style.background = 'var(--surface)')}
      onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
    >
      {/* Outcome dot */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <div style={{
          width: 7,
          height: 7,
          borderRadius: '50%',
          background: dotColor,
          flexShrink: 0,
        }} />
      </div>

      {/* Main body */}
      <div style={{ minWidth: 0 }}>
        <div style={{ display: 'flex', alignItems: 'baseline', gap: 8, flexWrap: 'wrap' }}>
          <span style={{
            fontSize: 13,
            fontWeight: 500,
            fontFamily: 'var(--font-mono, monospace)',
            color: 'var(--text)',
            whiteSpace: 'nowrap',
          }}>
            {entry.tool_name}
          </span>
          <span style={{ fontSize: 12, color: 'var(--text-faint)', whiteSpace: 'nowrap' }}>
            {entry.integration_id}
          </span>
          {isPending && (
            <span style={{ fontSize: 11, color: 'var(--amber)', fontWeight: 500 }}>
              · awaiting approval
            </span>
          )}
          {isApproved && (
            <span style={{ fontSize: 11, color: 'var(--blue, #4f8ef7)', fontWeight: 500 }}>
              · approved, waiting for agent
            </span>
          )}
          {accessTag && (
            <span style={{
              fontSize: 11,
              color: accessTag.color,
              fontWeight: 500,
              whiteSpace: 'nowrap',
              opacity: 0.85,
            }}>
              · {accessTag.label}
            </span>
          )}
          {isDenied && (
            <span style={{ fontSize: 11, color: 'var(--red)', fontWeight: 500 }}>
              · blocked
            </span>
          )}
          {isExpired && (
            <span style={{ fontSize: 11, color: 'var(--text-faint)', fontWeight: 500 }}>
              · expired
            </span>
          )}
          {isError && (
            <span style={{
              fontSize: 11,
              color: 'var(--red)',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
              maxWidth: 240,
            }}>
              · {entry.error}
            </span>
          )}
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 2 }}>
          <span style={{ fontSize: 11, color: 'var(--text-faint)' }}>
            {timeAgo(entry.timestamp)}
          </span>
          {entry.api_key_label && (
            <span style={{
              fontSize: 11,
              color: 'var(--text-faint)',
              fontFamily: 'var(--font-mono, monospace)',
            }}>
              {entry.api_key_label}
            </span>
          )}
        </div>
      </div>

      {/* Duration */}
      <div style={{
        fontSize: 11,
        color: 'var(--text-faint)',
        fontFamily: 'var(--font-mono, monospace)',
        fontVariantNumeric: 'tabular-nums',
        whiteSpace: 'nowrap',
        flexShrink: 0,
      }}>
        {entry.duration_ms != null ? formatDuration(entry.duration_ms) : '—'}
      </div>

      {/* Chevron hint */}
      <div style={{ color: 'var(--text-faint)', fontSize: 12, flexShrink: 0 }}>›</div>
    </div>
  )
}
