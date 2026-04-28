import { useLayoutEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { Check, CheckCheck, ShieldCheck, X, Loader2 } from 'lucide-react'
import { api, type LogEntry } from '@/api/client'

function TooltipPopup({ label, cx, y }: { label: string; cx: number; y: number }) {
  const ref = useRef<HTMLDivElement>(null)

  useLayoutEffect(() => {
    const element = ref.current
    if (!element) return
    const rect = element.getBoundingClientRect()
    let n = 0
    if (rect.left < 8) n = 8 - rect.left
    else if (rect.right > window.innerWidth - 8) n = window.innerWidth - 8 - rect.right
    element.style.left = `${cx + n}px`
    element.style.opacity = '1'
  }, [cx, y])

  return (
    <div
      ref={ref}
      style={{
        position: 'fixed',
        top: y - 6,
        left: cx,
        transform: 'translate(-50%, -100%)',
        opacity: 0,
        background: 'var(--text)',
        color: 'var(--content-bg)',
        fontSize: 11,
        fontWeight: 500,
        padding: '4px 8px',
        borderRadius: 4,
        whiteSpace: 'nowrap',
        pointerEvents: 'none',
        zIndex: 9999,
        letterSpacing: '0.01em',
      }}
    >
      {label}
    </div>
  )
}

function Tooltip({ children, label }: { children: React.ReactNode; label: string }) {
  const ref = useRef<HTMLDivElement>(null)
  const [pos, setPos] = useState<{ cx: number; y: number } | null>(null)

  return (
    <div
      ref={ref}
      style={{ display: 'inline-flex' }}
      onMouseEnter={() => {
        const r = ref.current?.getBoundingClientRect()
        if (r) setPos({ cx: r.left + r.width / 2, y: r.top })
      }}
      onMouseLeave={() => setPos(null)}
    >
      {children}
      {pos && createPortal(<TooltipPopup label={label} cx={pos.cx} y={pos.y} />, document.body)}
    </div>
  )
}

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
  approved_once: { label: 'approved once', color: 'var(--green)' },
  approved_exact: { label: 'approved forever', color: 'var(--green)' },
  approved_any: { label: 'never ask again', color: 'var(--blue)' },
}

type ApprovalAction = 'once' | 'forever' | 'tool' | 'deny'

function ApprovalActions({ approvalId, onDone }: { approvalId: string; onDone: () => void }) {
  const [acting, setActing] = useState<ApprovalAction | null>(null)

  async function act(action: ApprovalAction, e: React.MouseEvent) {
    e.stopPropagation()
    if (acting) return
    setActing(action)
    try {
      if (action === 'once') await api.approvals.approveOnce(approvalId)
      if (action === 'forever') await api.approvals.approveForever(approvalId)
      if (action === 'tool') await api.approvals.allowTool(approvalId)
      if (action === 'deny') await api.approvals.deny(approvalId)
      onDone()
    } catch {
      /* parent refetch will reflect reality */
    } finally {
      setActing(null)
    }
  }

  function btn(action: ApprovalAction, icon: React.ReactNode, hoverColor: string) {
    const isActive = acting === action
    return (
      <button
        key={action}
        onClick={(e) => act(action, e)}
        disabled={!!acting}
        style={{
          width: 24,
          height: 24,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          background: 'none',
          border: '1px solid var(--border)',
          borderRadius: 4,
          cursor: acting ? 'default' : 'pointer',
          color: isActive ? hoverColor : 'var(--text-faint)',
          opacity: acting && !isActive ? 0.4 : 1,
          transition: 'color 100ms, border-color 100ms',
          flexShrink: 0,
        }}
        onMouseEnter={(e) => {
          if (!acting) {
            e.currentTarget.style.color = hoverColor
            e.currentTarget.style.borderColor = hoverColor
          }
        }}
        onMouseLeave={(e) => {
          if (!isActive) {
            e.currentTarget.style.color = 'var(--text-faint)'
            e.currentTarget.style.borderColor = 'var(--border)'
          }
        }}
      >
        {isActive ? <Loader2 size={12} style={{ animation: 'spin 0.8s linear infinite' }} /> : icon}
      </button>
    )
  }

  return (
    <div
      style={{ display: 'flex', alignItems: 'center', gap: 4, flexShrink: 0 }}
      onClick={(e) => e.stopPropagation()}
    >
      <Tooltip label="Approve this call once">
        {btn('once', <Check size={12} />, 'var(--green)')}
      </Tooltip>
      <Tooltip label="Always approve with these exact params">
        {btn('forever', <CheckCheck size={12} />, 'var(--green)')}
      </Tooltip>
      <Tooltip label="Always approve any call to this tool">
        {btn('tool', <ShieldCheck size={12} />, 'var(--blue)')}
      </Tooltip>
      <Tooltip label="Deny this request">{btn('deny', <X size={12} />, 'var(--red)')}</Tooltip>
    </div>
  )
}

const OUTCOME_PILL: Record<string, { label: string; bg: string; color: string }> = {
  executed: { label: 'Executed', bg: 'var(--badge-green-bg)', color: 'var(--badge-green-text)' },
  error: { label: 'Error', bg: 'var(--badge-red-bg)', color: 'var(--badge-red-text)' },
  denied: { label: 'Blocked', bg: 'var(--badge-red-bg)', color: 'var(--badge-red-text)' },
  pending: {
    label: 'Awaiting Approval',
    bg: 'var(--badge-amber-bg)',
    color: 'var(--badge-amber-text)',
  },
  approved: {
    label: 'Waiting for Agent',
    bg: 'var(--badge-blue-bg)',
    color: 'var(--badge-blue-text)',
  },
  expired: { label: 'Expired', bg: 'var(--badge-gray-bg)', color: 'var(--badge-gray-text)' },
}

export function LogCard({
  entry,
  onClick,
  onAction,
}: {
  entry: LogEntry
  onClick: () => void
  onAction?: () => void
}) {
  const isPending = entry.outcome === 'pending'
  const isError = entry.outcome === 'error'
  const isExpired =
    isPending && !!entry.approval_expires_at && new Date(entry.approval_expires_at) <= new Date()

  const pill = isExpired
    ? OUTCOME_PILL.expired
    : (OUTCOME_PILL[entry.outcome ?? 'executed'] ?? OUTCOME_PILL.executed)
  const accessTag = entry.access_reason ? ACCESS_LABELS[entry.access_reason] : null

  return (
    <div
      onClick={onClick}
      style={{
        display: 'flex',
        flexDirection: 'column',
        gap: 8,
        padding: '14px 16px',
        background: 'var(--content-bg)',
        border: '1px solid var(--border)',
        borderRadius: 8,
        cursor: 'pointer',
        boxShadow: '0 1px 3px rgba(0,0,0,0.06), 0 1px 2px rgba(0,0,0,0.04)',
        transition: 'box-shadow 120ms, border-color 120ms',
      }}
      onMouseEnter={(e) => {
        e.currentTarget.style.boxShadow = '0 4px 12px rgba(0,0,0,0.10), 0 1px 3px rgba(0,0,0,0.06)'
        e.currentTarget.style.borderColor = 'var(--border-strong)'
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.boxShadow = '0 1px 3px rgba(0,0,0,0.06), 0 1px 2px rgba(0,0,0,0.04)'
        e.currentTarget.style.borderColor = 'var(--border)'
      }}
    >
      {/* Top row: tool name · pill · access tag · spacer · duration or approval actions */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, minWidth: 0 }}>
        <span
          style={{
            fontSize: 13,
            fontWeight: 500,
            color: 'var(--text)',
            whiteSpace: 'nowrap',
          }}
        >
          {entry.tool_name}
        </span>

        <span
          style={{
            fontSize: 11,
            fontWeight: 500,
            padding: '2px 7px',
            borderRadius: 999,
            background: pill.bg,
            color: pill.color,
            whiteSpace: 'nowrap',
            flexShrink: 0,
          }}
        >
          {pill.label}
        </span>

        {accessTag && (
          <span
            style={{
              fontSize: 11,
              color: accessTag.color,
              fontWeight: 500,
              opacity: 0.85,
              whiteSpace: 'nowrap',
            }}
          >
            {accessTag.label}
          </span>
        )}

        {isError && entry.error && (
          <span
            style={{
              fontSize: 11,
              color: 'var(--text-faint)',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
            }}
          >
            {entry.error}
          </span>
        )}

        <div style={{ flex: 1 }} />

        {isPending && !isExpired && entry.approval_request_id ? (
          <ApprovalActions approvalId={entry.approval_request_id} onDone={() => onAction?.()} />
        ) : (
          <span
            style={{
              fontSize: 11,
              color: 'var(--text-faint)',
              fontFamily: 'var(--font-mono, monospace)',
              fontVariantNumeric: 'tabular-nums',
              whiteSpace: 'nowrap',
              flexShrink: 0,
            }}
          >
            {entry.duration_ms != null ? formatDuration(entry.duration_ms) : '—'}
          </span>
        )}
      </div>

      {/* Bottom row: timestamp · api key */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
        <span style={{ fontSize: 11, color: 'var(--text-faint)' }}>{timeAgo(entry.timestamp)}</span>
        {(entry.api_key_prefix || entry.api_key_label) && (
          <span
            style={{
              fontSize: 11,
              color: 'var(--text-faint)',
              fontFamily: 'var(--font-mono, monospace)',
            }}
          >
            · {entry.api_key_prefix ?? ''}
            {entry.api_key_label && (
              <span style={{ fontFamily: 'var(--font-sans, sans-serif)' }}>
                {entry.api_key_prefix ? ` (${entry.api_key_label})` : entry.api_key_label}
              </span>
            )}
          </span>
        )}
      </div>
    </div>
  )
}
