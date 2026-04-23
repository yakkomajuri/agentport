import { useEffect, useState } from 'react'
import { X } from 'lucide-react'
import { api, type LogEntry, type ApprovalRequest } from '@/api/client'
import { ResultView } from './JsonView'

const DECISION_LABELS: Record<string, string> = {
  approve_once: 'Approved once',
  allow_exact_forever: 'Approved forever (same params)',
  allow_tool_forever: 'Never ask again for this tool',
  deny: 'Denied',
}

function fmt(ts: string): string {
  return new Date(ts).toLocaleString([], {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  })
}

function formatDuration(ms: number): string {
  return ms >= 1000 ? `${(ms / 1000).toFixed(1)}s` : `${ms}ms`
}

type StageStatus = 'success' | 'error' | 'pending' | 'info'

function StageNode({ status, last }: { status: StageStatus; last?: boolean }) {
  const color =
    status === 'success'
      ? 'var(--green)'
      : status === 'error'
        ? 'var(--red)'
        : status === 'pending'
          ? 'var(--amber)'
          : 'var(--text-faint)'

  return (
    <div
      style={{
        position: 'relative',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        width: 20,
        flexShrink: 0,
      }}
    >
      {!last && (
        <div
          style={{
            position: 'absolute',
            top: 0,
            bottom: 0,
            width: 1,
            background: 'var(--border)',
          }}
        />
      )}
      <div
        style={{
          position: 'relative',
          width: 10,
          height: 10,
          borderRadius: '50%',
          background: color,
          border: `2px solid var(--content-bg)`,
          boxShadow: `0 0 0 1px ${color}`,
          flexShrink: 0,
          zIndex: 1,
          marginTop: 2,
        }}
      />
    </div>
  )
}

function StageRow({
  status,
  title,
  meta,
  last,
}: {
  status: StageStatus
  title: string
  meta?: React.ReactNode
  last?: boolean
}) {
  return (
    <div style={{ display: 'flex', gap: 12, alignItems: 'stretch' }}>
      <StageNode status={status} last={last} />
      <div style={{ paddingBottom: last ? 0 : 20, minWidth: 0, flex: 1 }}>
        <div style={{ fontSize: 13, fontWeight: 500, color: 'var(--text)', lineHeight: 1.2 }}>
          {title}
        </div>
        {meta && (
          <div style={{ marginTop: 6, display: 'flex', flexDirection: 'column', gap: 3 }}>
            {meta}
          </div>
        )}
      </div>
    </div>
  )
}

function MetaLine({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <div style={{ display: 'flex', gap: 8, alignItems: 'baseline' }}>
      <span
        style={{
          fontSize: 11,
          fontWeight: 500,
          color: 'var(--text-faint)',
          textTransform: 'uppercase',
          letterSpacing: '0.04em',
          width: 60,
          flexShrink: 0,
        }}
      >
        {label}
      </span>
      <span
        style={{
          fontSize: 12,
          color: 'var(--text-dim)',
          fontFamily: mono ? 'var(--font-mono, monospace)' : undefined,
          wordBreak: 'break-all',
        }}
      >
        {value}
      </span>
    </div>
  )
}

export function LogDetailPanel({ entry, onClose }: { entry: LogEntry; onClose: () => void }) {
  const [approval, setApproval] = useState<ApprovalRequest | null>(null)
  const [loadingApproval, setLoadingApproval] = useState(false)

  useEffect(() => {
    if (!entry.approval_request_id) return
    setLoadingApproval(true)
    api.approvals
      .get(entry.approval_request_id)
      .then(setApproval)
      .catch(() => {
        /* not critical */
      })
      .finally(() => setLoadingApproval(false))
  }, [entry.approval_request_id])

  // Close on Escape
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [onClose])

  const isPending = entry.outcome === 'pending'
  const isApproved = entry.outcome === 'approved'
  const isError = entry.outcome === 'error'
  const isDenied = entry.outcome === 'denied'
  const isExecuted = entry.outcome === 'executed'
  const isExpired =
    isPending &&
    !!approval &&
    (approval.status === 'expired' || new Date(approval.expires_at) <= new Date())

  let args: Record<string, unknown> = {}
  try {
    if (entry.args_json) args = JSON.parse(entry.args_json)
  } catch {
    /**/
  }
  const argEntries = Object.entries(args)

  let result: unknown = null
  try {
    if (entry.result_json) result = JSON.parse(entry.result_json)
  } catch {
    /**/
  }

  // Build stages
  const stages: React.ReactNode[] = []

  // Stage 1: Approval requested (if there was an approval)
  if (approval) {
    stages.push(
      <StageRow
        key="requested"
        status="pending"
        title="Approval requested"
        meta={
          <>
            <MetaLine label="When" value={fmt(approval.requested_at)} />
            {approval.requester_ip && <MetaLine label="From" value={approval.requester_ip} mono />}
            {approval.user_agent && <MetaLine label="Client" value={approval.user_agent} />}
            {approval.api_key_label && <MetaLine label="Key" value={approval.api_key_label} mono />}
          </>
        }
      />,
    )
  } else if (!approval && (isPending || isApproved)) {
    // Approval request not loaded yet / not found — show a placeholder
    stages.push(
      <StageRow
        key="requested"
        status="pending"
        title="Approval requested"
        meta={
          <>
            <MetaLine label="When" value={fmt(entry.timestamp)} />
            {entry.requester_ip && <MetaLine label="From" value={entry.requester_ip} mono />}
            {entry.api_key_label && <MetaLine label="Key" value={entry.api_key_label} mono />}
          </>
        }
      />,
    )
  }

  // Stage 2: Decision (if there was an approval)
  if (approval && approval.decided_at) {
    const decisionLabel = approval.decision_mode
      ? DECISION_LABELS[approval.decision_mode] ?? approval.decision_mode
      : 'Decided'
    const decisionStatus: StageStatus = approval.status === 'denied' ? 'error' : 'success'

    stages.push(
      <StageRow
        key="decision"
        status={decisionStatus}
        title={decisionLabel}
        last={isApproved}
        meta={
          <>
            <MetaLine label="When" value={fmt(approval.decided_at)} />
            {approval.approver_ip && <MetaLine label="From" value={approval.approver_ip} mono />}
          </>
        }
      />,
    )
  } else if (isExpired) {
    stages.push(<StageRow key="decision" status="info" last title="Expired" />)
  } else if (isPending) {
    // Still waiting for a decision
    stages.push(<StageRow key="decision" status="pending" last title="Awaiting approval" />)
  }

  // Stage 3: Execution (only for terminal outcomes)
  if (isExecuted || isError || isDenied) {
    const execTitle = isDenied ? 'Blocked by policy' : isError ? 'Execution failed' : 'Executed'
    const execStatus: StageStatus = isDenied || isError ? 'error' : 'success'

    stages.push(
      <StageRow
        key="exec"
        status={execStatus}
        last
        title={execTitle}
        meta={
          <>
            <MetaLine label="When" value={fmt(entry.timestamp)} />
            {entry.duration_ms != null && (
              <MetaLine label="Duration" value={formatDuration(entry.duration_ms)} mono />
            )}
            {entry.requester_ip && !approval && (
              <MetaLine label="From" value={entry.requester_ip} mono />
            )}
            {entry.api_key_label && !approval && (
              <MetaLine label="Key" value={entry.api_key_label} mono />
            )}
            {entry.error && <MetaLine label="Error" value={entry.error} />}
          </>
        }
      />,
    )
  }

  return (
    <>
      {/* Backdrop */}
      <div
        onClick={onClose}
        style={{
          position: 'fixed',
          inset: 0,
          background: 'rgba(0,0,0,0.25)',
          zIndex: 40,
        }}
      />

      {/* Panel */}
      <div
        style={{
          position: 'fixed',
          top: 0,
          right: 0,
          bottom: 0,
          width: 'min(520px, 100vw)',
          background: 'var(--content-bg)',
          borderLeft: '1px solid var(--border)',
          boxShadow: '-8px 0 32px rgba(0,0,0,0.12)',
          zIndex: 50,
          display: 'flex',
          flexDirection: 'column',
          overflowY: 'auto',
        }}
      >
        {/* Header */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            padding: '16px 20px',
            borderBottom: '1px solid var(--border)',
            position: 'sticky',
            top: 0,
            background: 'var(--content-bg)',
            zIndex: 10,
          }}
        >
          <div>
            <div
              style={{
                fontSize: 14,
                fontWeight: 600,
                fontFamily: 'var(--font-mono, monospace)',
                color: 'var(--text)',
              }}
            >
              {entry.tool_name}
            </div>
            <div style={{ fontSize: 12, color: 'var(--text-faint)', marginTop: 1 }}>
              {entry.integration_id}
            </div>
          </div>
          <button
            onClick={onClose}
            style={{
              width: 28,
              height: 28,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              background: 'none',
              border: '1px solid var(--border)',
              borderRadius: 6,
              cursor: 'pointer',
              color: 'var(--text-dim)',
            }}
          >
            <X size={14} />
          </button>
        </div>

        <div style={{ padding: '24px 20px', display: 'flex', flexDirection: 'column', gap: 28 }}>
          {/* Stage rail */}
          {loadingApproval ? (
            <div style={{ fontSize: 12, color: 'var(--text-faint)' }}>Loading…</div>
          ) : (
            <div>{stages}</div>
          )}

          {/* Agent-supplied rationale */}
          {(entry.additional_info || approval?.additional_info) && (
            <section>
              <div
                style={{
                  fontSize: 11,
                  fontWeight: 600,
                  color: 'var(--text-faint)',
                  textTransform: 'uppercase',
                  letterSpacing: '0.05em',
                  marginBottom: 10,
                }}
              >
                Agent note
              </div>
              <div
                style={{
                  padding: '10px 12px',
                  background: 'var(--surface)',
                  border: '1px solid var(--border)',
                  borderLeft: '3px solid var(--amber)',
                  borderRadius: 6,
                  fontSize: 13,
                  lineHeight: 1.5,
                  color: 'var(--text)',
                  whiteSpace: 'pre-wrap',
                  wordBreak: 'break-word',
                }}
              >
                {entry.additional_info || approval?.additional_info}
              </div>
            </section>
          )}

          {/* Parameters */}
          {argEntries.length > 0 && (
            <section>
              <div
                style={{
                  fontSize: 11,
                  fontWeight: 600,
                  color: 'var(--text-faint)',
                  textTransform: 'uppercase',
                  letterSpacing: '0.05em',
                  marginBottom: 10,
                }}
              >
                Parameters
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                {argEntries.map(([key, val]) => (
                  <div key={key}>
                    <div
                      style={{
                        fontSize: 12,
                        fontWeight: 600,
                        fontFamily: 'var(--font-mono, monospace)',
                        color: 'var(--text-dim)',
                        marginBottom: 4,
                      }}
                    >
                      {key}
                    </div>
                    <div
                      style={{
                        padding: '8px 10px',
                        background: 'var(--surface)',
                        borderRadius: 6,
                        border: '1px solid var(--border)',
                        fontSize: 12,
                        color: 'var(--text)',
                        whiteSpace: 'pre-wrap',
                        wordBreak: 'break-word',
                        fontFamily:
                          typeof val !== 'string' ? 'var(--font-mono, monospace)' : undefined,
                      }}
                    >
                      {typeof val === 'string' ? val : JSON.stringify(val, null, 2)}
                    </div>
                  </div>
                ))}
              </div>
            </section>
          )}

          {/* Result */}
          {result != null && !isError && (
            <section>
              <div
                style={{
                  fontSize: 11,
                  fontWeight: 600,
                  color: 'var(--text-faint)',
                  textTransform: 'uppercase',
                  letterSpacing: '0.05em',
                  marginBottom: 10,
                }}
              >
                Result
              </div>
              <ResultView result={result} />
            </section>
          )}
        </div>
      </div>
    </>
  )
}
