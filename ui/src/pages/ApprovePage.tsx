import React, { useEffect, useRef, useState } from 'react'
import { useParams, Navigate, useSearchParams } from 'react-router-dom'
import {
  Shield,
  ShieldCheck,
  ShieldX,
  CheckCircle2,
  XCircle,
  Clock,
  Loader2,
  Maximize2,
  KeyRound,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import {
  api,
  ApiError,
  type ApprovalRequest,
  type BundledIntegration,
  type Tool,
} from '@/api/client'
import { useAuthStore } from '@/stores/auth'
import { LOGOS } from '@/components/connections/IntegrationCard'
import { CodeInput } from '@/components/totp/CodeInput'

interface ApprovePageProps {
  /** When rendered inline (e.g. playground drawer) override the URL param */
  overrideId?: string
  /** When true, suppresses the page shell / footer (same as ?embedded=true) */
  embeddedProp?: boolean
  /** Called immediately after allow-tool succeeds, before the success state renders */
  onAllowTool?: (integrationName: string, toolName: string) => void
}

const URL_REGEX = /(https?:\/\/[^\s<>"']+)/g

function renderWithLinks(text: string): React.ReactNode[] {
  const parts: React.ReactNode[] = []
  let lastIndex = 0
  let match: RegExpExecArray | null
  URL_REGEX.lastIndex = 0
  while ((match = URL_REGEX.exec(text)) !== null) {
    const [raw] = match
    const start = match.index
    const trimmed = raw.replace(/[.,;:!?)\]}'"]+$/, '')
    const end = start + trimmed.length
    if (start > lastIndex) parts.push(text.slice(lastIndex, start))
    parts.push(
      <a
        key={`${start}-${trimmed}`}
        href={trimmed}
        target="_blank"
        rel="noopener noreferrer"
        style={{ color: 'var(--accent)', textDecoration: 'underline', wordBreak: 'break-all' }}
      >
        {trimmed}
      </a>,
    )
    lastIndex = end
    if (end < start + raw.length) URL_REGEX.lastIndex = end
  }
  if (lastIndex < text.length) parts.push(text.slice(lastIndex))
  return parts
}

function isTotpChallengeError(error: unknown): error is ApiError {
  if (!(error instanceof ApiError) || error.status !== 403) return false
  const body = error.body
  if (!body || typeof body !== 'object') return false
  const detail = 'detail' in body ? (body as { detail?: unknown }).detail : null
  if (!detail || typeof detail !== 'object') return false
  const code = 'error' in detail ? (detail as { error?: unknown }).error : null
  return code === 'totp_required' || code === 'totp_invalid'
}

export default function ApprovePage({
  overrideId,
  embeddedProp,
  onAllowTool,
}: ApprovePageProps = {}) {
  const { id: urlId } = useParams<{ id: string }>()
  const [searchParams] = useSearchParams()
  const id = overrideId ?? urlId
  const embedded = embeddedProp ?? searchParams.get('embedded') === 'true'
  const token = useAuthStore((s) => s.token)
  const [req, setReq] = useState<ApprovalRequest | null>(null)
  const [tool, setTool] = useState<Tool | null>(null)
  const [integration, setIntegration] = useState<BundledIntegration | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [acting, setActing] = useState(false)
  const [result, setResult] = useState<{ action: string; ok: boolean } | null>(null)
  const [paramsOpen, setParamsOpen] = useState(false)
  const [paramsView, setParamsView] = useState<'pretty' | 'json'>('pretty')
  const [descOpen, setDescOpen] = useState(false)
  const [descClamped, setDescClamped] = useState(false)
  const descRef = useRef<HTMLSpanElement>(null)
  const [totpRequired, setTotpRequired] = useState(false)
  const [totpCode, setTotpCode] = useState('')
  const [totpError, setTotpError] = useState('')
  const [useRecovery, setUseRecovery] = useState(false)
  const [recoveryCode, setRecoveryCode] = useState('')

  useEffect(() => {
    if (descRef.current) {
      setDescClamped(descRef.current.scrollHeight > descRef.current.clientHeight)
    }
  }, [tool])

  useEffect(() => {
    if (!id || !token) return
    api.approvals
      .get(id)
      .then((approval) => {
        setReq(approval)
        return Promise.all([
          api.tools.listForIntegration(approval.integration_id).then((tools) => {
            const match = tools.find((t) => t.name === approval.tool_name)
            if (match) setTool(match)
          }),
          api.integrations.list().then((integrations) => {
            const match = integrations.find((i) => i.id === approval.integration_id)
            if (match) setIntegration(match)
          }),
        ])
      })
      .catch((e) => setError(e instanceof Error ? e.message : 'Failed to load request'))
      .finally(() => setLoading(false))
  }, [id, token])

  useEffect(() => {
    if (!token) return
    api.totp
      .status()
      .then((s) => setTotpRequired(s.enabled))
      .catch(() => setTotpRequired(false))
  }, [token])

  if (!token) {
    return <Navigate to={`/login?redirect=/approve/${id}`} replace />
  }

  async function act(action: 'approve-once' | 'allow-tool' | 'deny') {
    if (!id) return
    const codeToSend = useRecovery ? recoveryCode.trim() : totpCode
    if (totpRequired) {
      if (useRecovery) {
        if (!codeToSend) {
          setTotpError('Enter a recovery code to continue')
          return
        }
      } else if (codeToSend.length < 6) {
        setTotpError('Enter the 6-digit code from your authenticator')
        return
      }
    }
    setActing(true)
    setError('')
    setTotpError('')
    try {
      const fn =
        action === 'approve-once'
          ? api.approvals.approveOnce
          : action === 'allow-tool'
            ? api.approvals.allowTool
            : api.approvals.deny
      const updated = await fn(id, totpRequired ? codeToSend : undefined)
      setReq(updated)
      setResult({ action, ok: true })
      if (action === 'allow-tool') {
        onAllowTool?.(updated.integration_id, updated.tool_name)
      }
    } catch (e) {
      if (isTotpChallengeError(e)) {
        setTotpRequired(true)
        setTotpError(e.message)
        setTotpCode('')
        setRecoveryCode('')
      } else {
        setError(e instanceof Error ? e.message : 'Action failed')
        setResult({ action, ok: false })
      }
    } finally {
      setActing(false)
    }
  }

  const isPending = req?.status === 'pending'
  const isExpired = req?.status === 'expired' || (req && parseUtcDate(req.expires_at) <= new Date())

  let args: Record<string, unknown> = {}
  if (req?.args_json) {
    try {
      args = JSON.parse(req.args_json)
    } catch {
      /* ignore */
    }
  }
  const hasArgs = Object.keys(args).length > 0
  const argEntries = Object.entries(args)

  const logo = req ? LOGOS[req.integration_id] : null
  const isReadOnly = tool?.annotations?.readOnlyHint === true
  const isDestructive = tool?.annotations?.destructiveHint === true

  const statusIcon = result?.ok ? (result.action === 'deny' ? ShieldX : ShieldCheck) : Shield
  const StatusIcon = statusIcon

  // ── Params full view (shared between modal and sheet) ──
  const paramsFullContent = (
    <>
      <div style={paramsFullHeaderStyle}>
        <span style={{ fontSize: 14, fontWeight: 600 }}>Parameters</span>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <div style={viewToggleContainerStyle}>
            <button
              onClick={() => setParamsView('pretty')}
              style={viewToggleBtnStyle(paramsView === 'pretty')}
            >
              Pretty
            </button>
            <button
              onClick={() => setParamsView('json')}
              style={viewToggleBtnStyle(paramsView === 'json')}
            >
              JSON
            </button>
          </div>
          <button onClick={() => setParamsOpen(false)} style={closeButtonStyle}>
            &times;
          </button>
        </div>
      </div>
      <div style={paramsFullScrollStyle}>
        {paramsView === 'pretty' ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {argEntries.map(([key, value]) => (
              <ParamCard key={key} name={key} value={value} />
            ))}
          </div>
        ) : (
          <pre style={jsonStyle}>{JSON.stringify(args, null, 2)}</pre>
        )}
      </div>
    </>
  )

  return (
    <div
      style={
        embedded
          ? {
              width: '100%',
              minHeight: '100dvh',
              background: 'var(--bg)',
              padding: 'clamp(16px, 4vw, 24px)',
              boxSizing: 'border-box' as const,
            }
          : pageStyle
      }
    >
      <div
        style={
          embedded
            ? {
                ...cardStyle,
                width: '100%',
                maxWidth: 'none',
                maxHeight: 'none',
                border: 'none',
                borderRadius: 0,
                boxShadow: 'none',
              }
            : cardStyle
        }
      >
        {loading && (
          <div style={{ textAlign: 'center', padding: 48, color: 'var(--text-faint)' }}>
            <Loader2 size={24} style={{ animation: 'spin 1s linear infinite' }} />
          </div>
        )}

        {error && !req && (
          <div style={{ textAlign: 'center', padding: 32 }}>
            <ShieldX size={32} style={{ color: 'var(--red)', margin: '0 auto 12px' }} />
            <p style={{ fontSize: 14, color: 'var(--red)', margin: 0 }}>{error}</p>
          </div>
        )}

        {req && (
          <>
            {/* Integration identity */}
            <div style={headerStyle}>
              <div style={logoContainerStyle}>
                {logo ? (
                  <img
                    src={logo.src}
                    alt={req.integration_id}
                    style={{
                      width: 24,
                      height: 24,
                      objectFit: 'contain',
                      filter: logo.darkInvert ? 'var(--logo-invert-filter)' : undefined,
                    }}
                  />
                ) : (
                  <span style={{ fontSize: 20, fontWeight: 600, color: 'var(--text-dim)' }}>
                    {req.integration_id.charAt(0).toUpperCase()}
                  </span>
                )}
              </div>
              <div>
                <div style={{ fontSize: 13, fontWeight: 500, color: 'var(--text-dim)' }}>
                  {integration?.name ?? req.integration_id}
                </div>
                <div
                  style={{
                    fontSize: 18,
                    fontWeight: 600,
                    color: 'var(--text)',
                    fontFamily: 'var(--font-mono, monospace)',
                    letterSpacing: '-0.01em',
                  }}
                >
                  {req.tool_name}
                </div>
              </div>
            </div>

            {/* Tool description */}
            {tool?.description && (
              <div style={descriptionStyle}>
                <div style={additionalInfoLabelStyle}>Tool description</div>
                <div style={descriptionBodyStyle}>
                  <span
                    ref={descRef}
                    style={
                      descOpen
                        ? undefined
                        : {
                            display: '-webkit-box',
                            WebkitLineClamp: 2,
                            WebkitBoxOrient: 'vertical',
                            overflow: 'hidden',
                          }
                    }
                  >
                    {tool.description}
                  </span>
                  {descClamped && (
                    <button
                      onClick={() => setDescOpen((o) => !o)}
                      style={descExpandBtnStyle}
                      onMouseEnter={(e) => (e.currentTarget.style.color = 'var(--text)')}
                      onMouseLeave={(e) => (e.currentTarget.style.color = 'var(--text-faint)')}
                    >
                      {descOpen ? 'Show less' : 'See full description'}
                    </button>
                  )}
                </div>
              </div>
            )}

            {/* Agent-supplied rationale */}
            {req.additional_info && (
              <div style={additionalInfoStyle}>
                <div style={additionalInfoLabelStyle}>Agent note</div>
                <div style={additionalInfoCardStyle}>
                  <div style={additionalInfoValueStyle}>{renderWithLinks(req.additional_info)}</div>
                </div>
              </div>
            )}

            {/* Status + expiry */}
            <div style={statusRowStyle}>
              <span style={badgeStyle(isExpired ? 'expired' : req.status)}>
                <StatusIcon size={11} style={{ marginRight: 4, verticalAlign: -1 }} />
                {isExpired ? 'EXPIRED' : req.status.toUpperCase()}
              </span>
              {isPending && !isExpired && (
                <span
                  style={{
                    fontSize: 11,
                    color: 'var(--text-faint)',
                    display: 'flex',
                    alignItems: 'center',
                    gap: 4,
                  }}
                >
                  <Clock size={11} />
                  Expires{' '}
                  {parseUtcDate(req.expires_at).toLocaleTimeString([], {
                    hour: '2-digit',
                    minute: '2-digit',
                  })}
                </span>
              )}
            </div>

            {/* Provenance timeline */}
            <div style={provenanceStyle}>
              <div style={provenanceRowStyle}>
                <span style={provenanceLabelStyle}>Requested</span>
                <span style={provenanceValueStyle}>
                  {parseUtcDate(req.requested_at).toLocaleString([], {
                    month: 'short',
                    day: 'numeric',
                    hour: '2-digit',
                    minute: '2-digit',
                  })}
                </span>
              </div>
              {(req.api_key_prefix || req.api_key_label) && (
                <div style={provenanceRowStyle}>
                  <span style={provenanceLabelStyle}>API key</span>
                  <span
                    style={{
                      ...provenanceValueStyle,
                      fontFamily: 'var(--font-mono, monospace)',
                      fontSize: 11,
                    }}
                  >
                    {req.api_key_prefix ?? ''}
                    {req.api_key_label && (
                      <span style={{ fontFamily: 'inherit', color: 'var(--text-faint)' }}>
                        {req.api_key_prefix ? ' ' : ''}({req.api_key_label})
                      </span>
                    )}
                  </span>
                </div>
              )}
              {req.requester_ip && (
                <div style={provenanceRowStyle}>
                  <span style={provenanceLabelStyle}>From</span>
                  <span
                    style={{
                      ...provenanceValueStyle,
                      fontFamily: 'var(--font-mono, monospace)',
                      fontSize: 11,
                    }}
                  >
                    {req.requester_ip}
                  </span>
                </div>
              )}
              {req.user_agent && (
                <div style={provenanceRowStyle}>
                  <span style={provenanceLabelStyle}>Client</span>
                  <span
                    style={{
                      ...provenanceValueStyle,
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                      whiteSpace: 'nowrap',
                    }}
                    title={req.user_agent}
                  >
                    {req.user_agent}
                  </span>
                </div>
              )}
              {req.decided_at && (
                <>
                  <div style={provenanceDividerStyle} />
                  <div style={provenanceRowStyle}>
                    <span style={provenanceLabelStyle}>
                      {req.status === 'denied' ? 'Denied' : 'Approved'}
                    </span>
                    <span style={provenanceValueStyle}>
                      {parseUtcDate(req.decided_at).toLocaleString([], {
                        month: 'short',
                        day: 'numeric',
                        hour: '2-digit',
                        minute: '2-digit',
                      })}
                    </span>
                  </div>
                  {req.approver_ip && (
                    <div style={provenanceRowStyle}>
                      <span style={provenanceLabelStyle}>From</span>
                      <span
                        style={{
                          ...provenanceValueStyle,
                          fontFamily: 'var(--font-mono, monospace)',
                          fontSize: 11,
                        }}
                      >
                        {req.approver_ip}
                      </span>
                    </div>
                  )}
                </>
              )}
            </div>

            {/* Annotations */}
            {tool?.annotations && (
              <div style={annotationsRowStyle}>
                {isReadOnly && (
                  <span
                    style={readOnlyTagStyle}
                    title={`Tool declared as read-only by ${integration?.name ?? req.integration_id}`}
                  >
                    Read-only
                  </span>
                )}
                {isDestructive && (
                  <span
                    style={{
                      ...annotationTagStyle,
                      background: 'var(--badge-red-bg)',
                      color: 'var(--badge-red-text)',
                    }}
                  >
                    Destructive
                  </span>
                )}
                {tool.annotations.idempotentHint && (
                  <span style={annotationTagStyle}>Idempotent</span>
                )}
              </div>
            )}

            {/* Inline param previews */}
            {hasArgs && (
              <div style={paramsPreviewSectionStyle}>
                <div
                  style={{
                    fontSize: 12,
                    fontWeight: 500,
                    color: 'var(--text-faint)',
                    marginBottom: 8,
                  }}
                >
                  Parameters
                </div>
                <div style={paramsPreviewListStyle}>
                  {argEntries.map(([key, value]) => {
                    const display = typeof value === 'string' ? value : JSON.stringify(value)
                    return (
                      <div key={key} style={paramInlineStyle}>
                        <div style={paramInlineNameStyle}>{key}</div>
                        <div style={paramInlineValueStyle}>{display}</div>
                      </div>
                    )
                  })}
                </div>
                <button
                  onClick={() => setParamsOpen(true)}
                  style={viewFullBtnStyle}
                  onMouseEnter={(e) => (e.currentTarget.style.background = 'var(--surface-hover)')}
                  onMouseLeave={(e) => (e.currentTarget.style.background = 'var(--surface)')}
                >
                  <Maximize2 size={13} />
                  See parameters in full
                </button>
              </div>
            )}

            {/* Result message */}
            {result?.ok && (
              <div style={resultStyle(result.action === 'deny' ? 'deny' : 'approve')}>
                {result.action === 'deny' ? (
                  <XCircle size={15} style={{ flexShrink: 0 }} />
                ) : (
                  <CheckCircle2 size={15} style={{ flexShrink: 0 }} />
                )}
                <span>
                  {result.action === 'approve-once'
                    ? 'Approved for this call. The agent can proceed.'
                    : result.action === 'allow-tool'
                      ? `All future calls to ${req?.tool_name} will auto-execute.`
                      : 'Denied. The agent will be blocked.'}
                </span>
              </div>
            )}

            {error && req && (
              <p style={{ fontSize: 12, color: 'var(--red)', margin: '0 0 12px' }}>{error}</p>
            )}

            {/* TOTP gate */}
            {isPending && !isExpired && !result?.ok && totpRequired && (
              <div style={totpGateStyle}>
                <div style={totpGateHeaderStyle}>
                  <KeyRound size={13} style={{ color: 'var(--text-dim)' }} />
                  <span style={totpGateTitleStyle}>
                    {useRecovery ? 'Enter a recovery code' : 'Enter your authenticator code'}
                  </span>
                </div>
                {useRecovery ? (
                  <input
                    autoFocus
                    value={recoveryCode}
                    onChange={(e) => {
                      setRecoveryCode(e.target.value)
                      if (totpError) setTotpError('')
                    }}
                    placeholder="xxxxx-xxxxx"
                    disabled={acting}
                    aria-label="Recovery code"
                    style={recoveryInputStyle(!!totpError)}
                  />
                ) : (
                  <div style={{ display: 'flex', justifyContent: 'center', padding: '4px 0' }}>
                    <CodeInput
                      value={totpCode}
                      onChange={(v) => {
                        setTotpCode(v)
                        if (totpError) setTotpError('')
                      }}
                      hasError={!!totpError}
                      disabled={acting}
                    />
                  </div>
                )}
                <div style={totpFootRowStyle}>
                  <button
                    onClick={() => {
                      setUseRecovery((v) => !v)
                      setTotpCode('')
                      setRecoveryCode('')
                      setTotpError('')
                    }}
                    style={totpSwitchBtnStyle}
                    disabled={acting}
                  >
                    {useRecovery ? 'Use authenticator code' : 'Use a recovery code'}
                  </button>
                  {totpError && (
                    <span style={{ fontSize: 11, color: 'var(--red)' }}>{totpError}</span>
                  )}
                </div>
              </div>
            )}

            {/* Actions */}
            {isPending && !isExpired && !result?.ok && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                <Button
                  onClick={() => act('approve-once')}
                  disabled={acting}
                  style={{ width: '100%', height: 40, fontSize: 14, fontWeight: 600 }}
                >
                  {acting ? (
                    <Loader2
                      size={14}
                      style={{ animation: 'spin 1s linear infinite', marginRight: 6 }}
                    />
                  ) : (
                    <CheckCircle2 size={14} style={{ marginRight: 6 }} />
                  )}
                  {acting ? 'Working...' : 'Approve Once'}
                </Button>
                <Button
                  onClick={() => act('allow-tool')}
                  disabled={acting}
                  variant="outline"
                  style={{ width: '100%', height: 40, fontSize: 13 }}
                >
                  Always approve {req?.tool_name} calls
                </Button>
                <Button
                  onClick={() => act('deny')}
                  disabled={acting}
                  variant="outline"
                  style={{
                    width: '100%',
                    height: 40,
                    fontSize: 13,
                    color: 'var(--red)',
                    borderColor: 'color-mix(in srgb, var(--red) 30%, transparent)',
                  }}
                >
                  <XCircle size={13} style={{ marginRight: 4 }} />
                  Deny
                </Button>
              </div>
            )}

            {isExpired && !result?.ok && (
              <div style={inertMessageStyle}>
                <Clock size={14} style={{ color: 'var(--text-faint)' }} />
                <span>This approval request has expired.</span>
              </div>
            )}

            {!isPending && !isExpired && !result?.ok && (
              <div style={inertMessageStyle}>
                {req.status === 'denied' ? (
                  <XCircle size={14} style={{ color: 'var(--red)' }} />
                ) : (
                  <CheckCircle2 size={14} style={{ color: 'var(--green)' }} />
                )}
                <span>This request has already been {req.status}.</span>
              </div>
            )}
          </>
        )}
      </div>

      {!embedded && <p style={footerStyle}>AgentPort</p>}

      {/* ── Params overlay (modal on desktop, sheet on mobile) ── */}
      {!embedded && paramsOpen && (
        <div className="approve-overlay" onClick={() => setParamsOpen(false)}>
          {/* Desktop modal */}
          <div className="approve-modal" style={modalStyle} onClick={(e) => e.stopPropagation()}>
            {paramsFullContent}
          </div>

          {/* Mobile bottom sheet */}
          <div className="approve-sheet">
            <div className="approve-sheet-panel" onClick={(e) => e.stopPropagation()}>
              <div style={sheetHandleStyle} />
              {paramsFullContent}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

// ── Helpers ──

/** Server returns naive UTC datetimes without Z; ensure JS interprets them as UTC. */
function parseUtcDate(s: string): Date {
  return new Date(s.endsWith('Z') || s.includes('+') ? s : s + 'Z')
}

// ── Components ──

function ParamCard({ name, value }: { name: string; value: unknown }) {
  const [expanded, setExpanded] = useState(false)
  const display = typeof value === 'string' ? value : JSON.stringify(value, null, 2)
  const isTruncated = display.length > 120

  return (
    <div style={paramCardStyle}>
      <div style={paramCardNameStyle}>{name}</div>
      <div style={paramCardValueStyle}>
        {expanded || !isTruncated ? display : display.slice(0, 120) + '\u2026'}
      </div>
      {isTruncated && (
        <button onClick={() => setExpanded(!expanded)} style={showMoreStyle}>
          {expanded ? 'Show less' : 'Show more'}
        </button>
      )}
    </div>
  )
}

// ── Styles ──

const pageStyle: React.CSSProperties = {
  minHeight: '100dvh',
  display: 'flex',
  flexDirection: 'column',
  alignItems: 'center',
  justifyContent: 'center',
  background: 'var(--bg)',
  padding: '16px 12px',
  boxSizing: 'border-box',
}

const cardStyle: React.CSSProperties = {
  width: '100%',
  maxWidth: 640,
  maxHeight: 'calc(100dvh - 48px)',
  padding: 'clamp(20px, 4.5vw, 36px)',
  background: 'var(--content-bg)',
  border: '1px solid var(--border)',
  borderRadius: 12,
  boxShadow: 'var(--shadow-sm)',
  display: 'flex',
  flexDirection: 'column',
  overflow: 'hidden',
  boxSizing: 'border-box',
}

const headerStyle: React.CSSProperties = {
  display: 'flex',
  alignItems: 'center',
  gap: 14,
  marginBottom: 20,
}

const logoContainerStyle: React.CSSProperties = {
  width: 48,
  height: 48,
  borderRadius: 10,
  border: '1px solid var(--border)',
  background: 'var(--surface)',
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  flexShrink: 0,
}

const descriptionStyle: React.CSSProperties = {
  margin: '0 0 16px',
}

const descriptionBodyStyle: React.CSSProperties = {
  fontSize: 13,
  lineHeight: 1.5,
  color: 'var(--text-dim)',
}

const additionalInfoStyle: React.CSSProperties = {
  margin: '0 0 16px',
}

const additionalInfoCardStyle: React.CSSProperties = {
  padding: '12px 14px',
  background: 'var(--surface)',
  borderRadius: 8,
  border: '1px solid var(--border)',
}

const additionalInfoLabelStyle: React.CSSProperties = {
  fontSize: 11,
  fontWeight: 600,
  color: 'var(--text-faint)',
  textTransform: 'uppercase',
  letterSpacing: '0.04em',
  marginBottom: 4,
}

const additionalInfoValueStyle: React.CSSProperties = {
  fontSize: 13,
  lineHeight: 1.5,
  color: 'var(--text)',
  whiteSpace: 'pre-wrap',
  wordBreak: 'break-word',
}

const descExpandBtnStyle: React.CSSProperties = {
  display: 'inline',
  marginLeft: 6,
  padding: 0,
  background: 'none',
  border: 'none',
  cursor: 'pointer',
  fontSize: 12,
  fontWeight: 500,
  color: 'var(--text-faint)',
  textDecoration: 'underline',
  textUnderlineOffset: 2,
}

const statusRowStyle: React.CSSProperties = {
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'space-between',
  marginBottom: 16,
}

const annotationsRowStyle: React.CSSProperties = {
  display: 'flex',
  gap: 6,
  marginBottom: 16,
}

const annotationTagStyle: React.CSSProperties = {
  fontSize: 11,
  fontWeight: 500,
  padding: '2px 8px',
  borderRadius: 4,
  background: 'var(--badge-gray-bg)',
  color: 'var(--badge-gray-text)',
}

const readOnlyTagStyle: React.CSSProperties = {
  ...annotationTagStyle,
  background: 'var(--badge-green-bg)',
  color: 'var(--badge-green-text)',
  cursor: 'help',
}

// ── Inline param previews ──

const paramsPreviewSectionStyle: React.CSSProperties = {
  flex: 1,
  minHeight: 0,
  marginBottom: 20,
  display: 'flex',
  flexDirection: 'column',
}

const paramsPreviewListStyle: React.CSSProperties = {
  display: 'flex',
  flexDirection: 'column',
  gap: 6,
  flex: 1,
  minHeight: 0,
  overflowY: 'auto',
}

const paramInlineStyle: React.CSSProperties = {
  border: '1px solid var(--border)',
  borderRadius: 8,
  background: 'var(--surface)',
  padding: '8px 12px',
}

const paramInlineNameStyle: React.CSSProperties = {
  fontSize: 11,
  fontWeight: 600,
  fontFamily: 'var(--font-mono, monospace)',
  color: 'var(--text-faint)',
  textTransform: 'uppercase',
  letterSpacing: '0.03em',
  marginBottom: 2,
}

const paramInlineValueStyle: React.CSSProperties = {
  fontSize: 13,
  color: 'var(--text)',
  whiteSpace: 'nowrap',
  overflow: 'hidden',
  textOverflow: 'ellipsis',
}

const viewFullBtnStyle: React.CSSProperties = {
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  gap: 6,
  width: '100%',
  padding: 8,
  fontSize: 12,
  fontWeight: 500,
  color: 'var(--text-dim)',
  background: 'var(--surface)',
  border: '1px solid var(--border)',
  borderRadius: 8,
  cursor: 'pointer',
  marginTop: 8,
  transition: 'background 150ms',
}

// ── Modal / sheet shared ──

const paramsFullHeaderStyle: React.CSSProperties = {
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'space-between',
  padding: '20px 24px',
  borderBottom: '1px solid var(--border)',
  flexShrink: 0,
}

const paramsFullScrollStyle: React.CSSProperties = {
  flex: 1,
  minHeight: 0,
  overflowY: 'auto',
  padding: '20px 24px',
  WebkitOverflowScrolling: 'touch',
}

const closeButtonStyle: React.CSSProperties = {
  width: 28,
  height: 28,
  borderRadius: 6,
  border: '1px solid var(--border)',
  background: 'var(--surface)',
  cursor: 'pointer',
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  color: 'var(--text-dim)',
  fontSize: 18,
  lineHeight: 1,
}

const viewToggleContainerStyle: React.CSSProperties = {
  display: 'flex',
  background: 'var(--surface)',
  border: '1px solid var(--border)',
  borderRadius: 5,
  padding: 2,
  gap: 1,
}

function viewToggleBtnStyle(active: boolean): React.CSSProperties {
  return {
    fontSize: 11,
    fontWeight: 500,
    padding: '2px 8px',
    borderRadius: 3,
    border: 'none',
    cursor: 'pointer',
    background: active ? 'var(--content-bg)' : 'transparent',
    color: active ? 'var(--text)' : 'var(--text-faint)',
    boxShadow: active ? '0 1px 2px rgba(0,0,0,0.06)' : 'none',
  }
}

// ── Desktop modal ──

const modalStyle: React.CSSProperties = {
  width: 720,
  maxWidth: 'calc(100vw - 48px)',
  height: 560,
  background: 'var(--content-bg)',
  border: '1px solid var(--border)',
  borderRadius: 12,
  boxShadow: 'var(--shadow-md)',
  flexDirection: 'column',
  overflow: 'hidden',
}

// ── Mobile sheet ──

const sheetHandleStyle: React.CSSProperties = {
  width: 36,
  height: 4,
  borderRadius: 2,
  background: 'var(--border-strong)',
  margin: '10px auto 0',
}

// ── Param cards (inside modal/sheet) ──

const paramCardStyle: React.CSSProperties = {
  border: '1px solid var(--border)',
  borderRadius: 8,
  background: 'var(--surface)',
  padding: '10px 12px',
}

const paramCardNameStyle: React.CSSProperties = {
  fontSize: 11,
  fontWeight: 600,
  fontFamily: 'var(--font-mono, monospace)',
  color: 'var(--text-faint)',
  textTransform: 'uppercase',
  letterSpacing: '0.03em',
  marginBottom: 4,
}

const paramCardValueStyle: React.CSSProperties = {
  fontSize: 13,
  lineHeight: 1.5,
  color: 'var(--text)',
  whiteSpace: 'pre-wrap',
  wordBreak: 'break-word',
}

const showMoreStyle: React.CSSProperties = {
  fontSize: 11,
  fontWeight: 500,
  color: 'var(--blue)',
  background: 'none',
  border: 'none',
  cursor: 'pointer',
  padding: 0,
  marginTop: 4,
}

const jsonStyle: React.CSSProperties = {
  fontSize: 12,
  fontFamily: 'var(--font-mono, monospace)',
  background: 'var(--surface)',
  border: '1px solid var(--border)',
  borderRadius: 8,
  padding: 12,
  margin: 0,
  whiteSpace: 'pre-wrap',
  wordBreak: 'break-word',
  color: 'var(--text-dim)',
}

// ── Action buttons ──

const inertMessageStyle: React.CSSProperties = {
  display: 'flex',
  alignItems: 'center',
  gap: 8,
  fontSize: 13,
  color: 'var(--text-dim)',
  padding: '12px 14px',
  background: 'var(--surface)',
  borderRadius: 8,
}

const footerStyle: React.CSSProperties = {
  marginTop: 16,
  fontSize: 11,
  color: 'var(--text-faint)',
  letterSpacing: '0.04em',
}

function badgeStyle(status: string): React.CSSProperties {
  const colors: Record<string, { bg: string; text: string }> = {
    pending: { bg: 'rgba(245, 166, 35, 0.12)', text: 'var(--amber)' },
    approved: { bg: 'rgba(52, 199, 89, 0.12)', text: 'var(--green)' },
    denied: { bg: 'rgba(255, 59, 48, 0.12)', text: 'var(--red)' },
    expired: { bg: 'rgba(142, 142, 147, 0.12)', text: 'var(--text-faint)' },
    consumed: { bg: 'rgba(52, 199, 89, 0.12)', text: 'var(--green)' },
  }
  const c = colors[status] || colors.expired
  return {
    display: 'inline-flex',
    alignItems: 'center',
    fontSize: 10,
    fontWeight: 600,
    letterSpacing: '0.04em',
    padding: '4px 10px',
    borderRadius: 5,
    background: c.bg,
    color: c.text,
  }
}

const provenanceStyle: React.CSSProperties = {
  display: 'flex',
  flexDirection: 'column',
  gap: 5,
  marginBottom: 16,
  fontSize: 12,
}

const provenanceRowStyle: React.CSSProperties = {
  display: 'flex',
  gap: 20,
  alignItems: 'baseline',
  minWidth: 0,
}

const provenanceLabelStyle: React.CSSProperties = {
  width: 64,
  flexShrink: 0,
  fontSize: 11,
  fontWeight: 500,
  color: 'var(--text-faint)',
  textTransform: 'uppercase',
  letterSpacing: '0.03em',
}

const provenanceValueStyle: React.CSSProperties = {
  flex: 1,
  minWidth: 0,
  fontSize: 12,
  color: 'var(--text-dim)',
}

const provenanceDividerStyle: React.CSSProperties = {
  height: 1,
  background: 'var(--border)',
  margin: '4px 0',
}

const totpGateStyle: React.CSSProperties = {
  border: '1px solid var(--border)',
  borderRadius: 10,
  background: 'var(--surface)',
  padding: '14px 16px',
  marginBottom: 14,
  display: 'flex',
  flexDirection: 'column',
  gap: 10,
}

const totpGateHeaderStyle: React.CSSProperties = {
  display: 'flex',
  alignItems: 'center',
  gap: 6,
}

const totpGateTitleStyle: React.CSSProperties = {
  fontSize: 12,
  fontWeight: 600,
  color: 'var(--text-dim)',
  letterSpacing: '0.005em',
}

const totpFootRowStyle: React.CSSProperties = {
  display: 'flex',
  justifyContent: 'space-between',
  alignItems: 'center',
  minHeight: 16,
}

const totpSwitchBtnStyle: React.CSSProperties = {
  background: 'none',
  border: 'none',
  padding: 0,
  fontSize: 11,
  fontWeight: 500,
  color: 'var(--text-faint)',
  cursor: 'pointer',
  textDecoration: 'underline',
  textUnderlineOffset: 2,
}

function recoveryInputStyle(hasError: boolean): React.CSSProperties {
  return {
    width: '100%',
    height: 38,
    padding: '0 12px',
    fontSize: 14,
    fontFamily: 'var(--font-mono, monospace)',
    letterSpacing: '0.06em',
    background: 'var(--content-bg)',
    border: `1px solid ${hasError ? 'var(--red)' : 'var(--border)'}`,
    borderRadius: 8,
    color: 'var(--text)',
    outline: 'none',
    boxSizing: 'border-box',
  }
}

function resultStyle(type: 'approve' | 'deny'): React.CSSProperties {
  const isApprove = type === 'approve'
  return {
    display: 'flex',
    alignItems: 'center',
    gap: 10,
    fontSize: 13,
    fontWeight: 500,
    padding: '14px 16px',
    marginBottom: 12,
    borderRadius: 8,
    background: isApprove ? 'rgba(52, 199, 89, 0.08)' : 'rgba(255, 59, 48, 0.08)',
    color: isApprove ? 'var(--green)' : 'var(--red)',
  }
}
