import { useEffect, useMemo, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { useParams, useNavigate, Link } from 'react-router-dom'
import { ArrowLeft, ChevronRight, ExternalLink, Loader2, Minus, Search } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { useConnectionsStore } from '@/stores/connections'
import { useToolsStore } from '@/stores/tools'
import { useLogsStore } from '@/stores/logs'
import { LogCard } from '@/components/logs/LogCard'
import { LogDetailPanel } from '@/components/logs/LogDetailPanel'
import type { LogEntry } from '@/api/client'
import { ConnectDialog } from '@/components/connections/ConnectDialog'
import { LOGOS } from '@/components/connections/IntegrationCard'
import { api, type Tool } from '@/api/client'
import { TOOL_MODES } from '@/lib/toolModes'
import { useIsMobile } from '@/lib/useMediaQuery'
import { isTotpChallengeError } from '@/lib/totpError'
import { TotpCodeDialog } from '@/components/totp/TotpCodeDialog'

const TYPE_LABELS: Record<string, string> = {
  remote_mcp: 'Remote MCP',
  api: 'REST API',
}

type ToolWithMode = Tool & { execution_mode?: string }

export default function ConnectionDetailPage() {
  const { integrationId } = useParams<{ integrationId: string }>()
  const navigate = useNavigate()
  const isMobile = useIsMobile()
  const sidePad = isMobile ? 14 : 28
  const { integrations, installed, fetchIntegrations, fetchInstalled, remove } =
    useConnectionsStore()
  const {
    tools,
    loading: toolsLoading,
    error: toolsError,
    fetchForIntegration,
    patchToolMode,
    clear,
  } = useToolsStore()
  const { entries: logEntries, loading: logsLoading, fetch: fetchLogs } = useLogsStore()
  const [activeTab, setActiveTab] = useState<'tools' | 'logs'>('tools')
  const [toolFilter, setToolFilter] = useState('')
  const [connectOpen, setConnectOpen] = useState(false)
  const [reauthMode, setReauthMode] = useState(false)
  const [updating, setUpdating] = useState<string | null>(null)
  const [selectedLog, setSelectedLog] = useState<LogEntry | null>(null)
  const [pendingTotp, setPendingTotp] = useState<
    Array<{ toolName: string; newMode: string; prevMode: string }>
  >([])
  const [totpDialogOpen, setTotpDialogOpen] = useState(false)
  // Mark whether the current dialog close is from a successful submit so we
  // don't revert the optimistic updates that just persisted.
  const totpCommittedRef = useRef(false)

  useEffect(() => {
    if (integrations.length === 0) fetchIntegrations()
    if (installed.length === 0) fetchInstalled()
  }, [])

  const integration = integrations.find((i) => i.id === integrationId)
  const inst = installed.find((i) => i.integration_id === integrationId)

  useEffect(() => {
    if (inst) {
      fetchForIntegration(inst.integration_id)
    } else {
      clear()
    }
    return () => clear()
  }, [inst?.integration_id])

  useEffect(() => {
    if (activeTab === 'logs' && inst) {
      fetchLogs({ integration: inst.integration_id })
    }
  }, [activeTab, inst?.integration_id])

  // Reset tab when navigating to a different connection
  useEffect(() => {
    setActiveTab('tools')
    setToolFilter('')
  }, [integrationId])

  const filteredTools = (tools as ToolWithMode[]).filter(
    (t) =>
      !toolFilter ||
      t.name.toLowerCase().includes(toolFilter.toLowerCase()) ||
      t.title?.toLowerCase().includes(toolFilter.toLowerCase()) ||
      t.description?.toLowerCase().includes(toolFilter.toLowerCase()),
  )

  // Group by category when available; null/undefined category → ungrouped
  const hasCategories = filteredTools.some((t) => t.category)
  const grouped = useMemo(() => {
    if (!hasCategories) return null
    const map = new Map<string, ToolWithMode[]>()
    for (const tool of filteredTools) {
      const cat = tool.category || 'Other'
      if (!map.has(cat)) map.set(cat, [])
      map.get(cat)!.push(tool)
    }
    return Array.from(map.entries()).sort(([a], [b]) => a.localeCompare(b))
  }, [filteredTools, hasCategories])

  if (!integration) {
    return (
      <>
        <FilterBar sidePad={sidePad}>
          <BackLink />
          <span style={{ fontSize: 13, fontWeight: 500, color: 'var(--text)' }}>
            {integrations.length === 0 ? 'Loading...' : 'Not found'}
          </span>
        </FilterBar>
        <div
          style={{
            flex: 1,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: 'var(--text-faint)',
            fontSize: 13,
          }}
        >
          {integrations.length === 0 ? (
            <Loader2 size={16} style={{ animation: 'spin 1s linear infinite' }} />
          ) : (
            'Integration not found.'
          )}
        </div>
        <style>{`@keyframes spin { to { transform: rotate(360deg) } }`}</style>
      </>
    )
  }

  const isConnected = !!inst?.connected

  async function setMode(toolName: string, newMode: string, currentMode: string) {
    if (!inst || newMode === currentMode) return
    setUpdating(toolName)
    patchToolMode(toolName, newMode)
    try {
      await api.toolSettings.update(inst.integration_id, toolName, newMode)
    } catch (e) {
      if (isTotpChallengeError(e)) {
        setPendingTotp([{ toolName, newMode, prevMode: currentMode }])
        totpCommittedRef.current = false
        setTotpDialogOpen(true)
      } else {
        patchToolMode(toolName, currentMode)
      }
    } finally {
      setUpdating(null)
    }
  }

  async function setCategoryMode(categoryTools: ToolWithMode[], newMode: string) {
    if (!inst) return
    const work = categoryTools
      .filter((t) => (t.execution_mode || 'require_approval') !== newMode)
      .map((t) => ({
        toolName: t.name,
        newMode,
        prevMode: t.execution_mode || 'require_approval',
      }))
    if (work.length === 0) return

    work.forEach((w) => patchToolMode(w.toolName, w.newMode))

    const results = await Promise.allSettled(
      work.map((w) => api.toolSettings.update(inst.integration_id, w.toolName, w.newMode)),
    )
    const needTotp: typeof work = []
    results.forEach((r, i) => {
      if (r.status === 'rejected') {
        if (isTotpChallengeError(r.reason)) {
          needTotp.push(work[i])
        } else {
          patchToolMode(work[i].toolName, work[i].prevMode)
        }
      }
    })
    if (needTotp.length > 0) {
      setPendingTotp(needTotp)
      totpCommittedRef.current = false
      setTotpDialogOpen(true)
    }
  }

  async function handleTotpSubmit(code: string) {
    if (!inst || pendingTotp.length === 0) return
    const results = await Promise.allSettled(
      pendingTotp.map((w) =>
        api.toolSettings.update(inst.integration_id, w.toolName, w.newMode, code),
      ),
    )
    const stillInvalid: typeof pendingTotp = []
    results.forEach((r, i) => {
      if (r.status === 'rejected') {
        if (isTotpChallengeError(r.reason)) {
          stillInvalid.push(pendingTotp[i])
        } else {
          patchToolMode(pendingTotp[i].toolName, pendingTotp[i].prevMode)
        }
      }
    })
    if (stillInvalid.length > 0) {
      setPendingTotp(stillInvalid)
      // Throwing keeps TotpCodeDialog open and lets it show the error.
      throw new Error("That code didn't match — try again with a fresh one.")
    }
    totpCommittedRef.current = true
    setPendingTotp([])
  }

  function handleTotpClose() {
    if (!totpCommittedRef.current) {
      pendingTotp.forEach((w) => patchToolMode(w.toolName, w.prevMode))
      setPendingTotp([])
    }
    totpCommittedRef.current = false
    setTotpDialogOpen(false)
  }

  async function handleDisconnect() {
    if (!inst) return
    await remove(inst.integration_id)
    navigate('/integrations')
  }

  return (
    <>
      {/* FilterBar */}
      <FilterBar sidePad={sidePad}>
        <BackLink />
        <span
          style={{
            fontSize: 13,
            fontWeight: 500,
            color: 'var(--text)',
            minWidth: 0,
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
          }}
        >
          {integration.name}
        </span>
        <div
          style={{
            marginLeft: 'auto',
            display: 'flex',
            alignItems: 'center',
            gap: 8,
            flexShrink: 0,
          }}
        >
          {isConnected ? (
            <>
              <Button
                variant="outline"
                size="sm"
                onClick={() => {
                  setReauthMode(true)
                  setConnectOpen(true)
                }}
              >
                {isMobile ? 'Re-auth' : 'Re-authenticate'}
              </Button>
              <Button variant="destructive" size="sm" onClick={handleDisconnect}>
                Disconnect
              </Button>
            </>
          ) : (
            <Button size="sm" onClick={() => setConnectOpen(true)}>
              Connect
            </Button>
          )}
        </div>
      </FilterBar>

      <div style={{ flex: 1, overflowY: 'auto' }}>
        {/* Info section */}
        <div style={{ padding: `${sidePad}px ${sidePad}px 0` }}>
          <div style={{ display: 'flex', alignItems: 'flex-start', gap: 14 }}>
            <div
              style={{
                width: 40,
                height: 40,
                borderRadius: 8,
                border: '1px solid var(--border)',
                background: 'var(--surface)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontSize: 20,
                flexShrink: 0,
              }}
            >
              {LOGOS[integration.id] ? (
                <img
                  src={LOGOS[integration.id].src}
                  alt={integration.name}
                  style={{
                    width: 24,
                    height: 24,
                    objectFit: 'contain',
                    filter: LOGOS[integration.id].darkInvert
                      ? 'var(--logo-invert-filter)'
                      : undefined,
                  }}
                />
              ) : (
                integration.name.charAt(0).toUpperCase()
              )}
            </div>
            <div>
              <h2 style={{ fontSize: 17, fontWeight: 600, margin: 0, color: 'var(--text)' }}>
                {integration.name}
              </h2>
              {integration.description && (
                <p
                  style={{ fontSize: 13, color: 'var(--text-dim)', marginTop: 4, lineHeight: 1.5 }}
                >
                  {integration.description}
                </p>
              )}
              <div
                style={{
                  display: 'flex',
                  flexWrap: 'wrap',
                  rowGap: 10,
                  columnGap: 16,
                  marginTop: 14,
                  alignItems: 'flex-end',
                }}
              >
                <MetaItem label="Type" value={TYPE_LABELS[integration.type] ?? integration.type} />
                {inst && <MetaItem label="Auth" value={inst.auth_method} />}
                {inst && (
                  <MetaItem label="Status">
                    <span
                      style={{
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: 5,
                        padding: '2px 8px',
                        borderRadius: 99,
                        fontSize: 11,
                        fontWeight: 500,
                        background: 'var(--badge-green-bg)',
                        color: 'var(--badge-green-text)',
                      }}
                    >
                      <span
                        style={{
                          width: 6,
                          height: 6,
                          borderRadius: '50%',
                          background: 'var(--badge-green-dot)',
                        }}
                      />
                      Connected
                    </span>
                  </MetaItem>
                )}
                {(inst || (integration.type === 'api' && integration.tools?.length)) && (
                  <MetaItem
                    label="Tools"
                    value={
                      inst
                        ? toolsLoading
                          ? '...'
                          : String(tools.length)
                        : String(integration.tools?.length ?? 0)
                    }
                  />
                )}
                {integration.docs_url && (
                  <MetaItem label="Docs">
                    <a
                      href={integration.docs_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      style={{
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: 4,
                        fontSize: 13,
                        fontWeight: 500,
                        color: '#3b82f6',
                        textDecoration: 'none',
                      }}
                      onMouseEnter={(e) => (e.currentTarget.style.textDecoration = 'underline')}
                      onMouseLeave={(e) => (e.currentTarget.style.textDecoration = 'none')}
                    >
                      View docs
                      <ExternalLink size={11} />
                    </a>
                  </MetaItem>
                )}
              </div>
            </div>
          </div>
        </div>

        {/* Divider */}
        <div style={{ height: 1, background: 'var(--border)', margin: '24px 0 0' }} />

        {isConnected ? (
          <>
            {/* Tab bar */}
            <div
              style={{
                display: 'flex',
                padding: `0 ${sidePad}px`,
                borderBottom: '1px solid var(--border)',
              }}
            >
              {(['tools', 'logs'] as const).map((tab) => (
                <button
                  key={tab}
                  onClick={() => setActiveTab(tab)}
                  style={{
                    padding: '10px 2px',
                    marginRight: 20,
                    marginBottom: -1,
                    fontSize: 13,
                    fontWeight: activeTab === tab ? 500 : 400,
                    color: activeTab === tab ? 'var(--text)' : 'var(--text-faint)',
                    background: 'none',
                    border: 'none',
                    borderBottom: `2px solid ${activeTab === tab ? 'var(--accent)' : 'transparent'}`,
                    cursor: 'pointer',
                    fontFamily: 'inherit',
                    outline: 'none',
                    transition: 'color 120ms',
                  }}
                >
                  {tab.charAt(0).toUpperCase() + tab.slice(1)}
                </button>
              ))}
            </div>

            {/* Tools tab */}
            {activeTab === 'tools' && (
              <div style={{ padding: `20px ${sidePad}px 48px` }}>
                <div
                  style={{
                    position: 'relative',
                    display: 'flex',
                    alignItems: 'center',
                    marginBottom: 14,
                  }}
                >
                  <Search
                    size={14}
                    style={{
                      position: 'absolute',
                      left: 10,
                      color: 'var(--text-faint)',
                      pointerEvents: 'none',
                    }}
                  />
                  <input
                    value={toolFilter}
                    onChange={(e) => setToolFilter(e.target.value)}
                    placeholder="Filter tools..."
                    style={{
                      height: 32,
                      padding: '0 10px 0 32px',
                      border: '1px solid var(--border)',
                      borderRadius: 7,
                      background: 'var(--input-bg)',
                      fontSize: 13,
                      fontFamily: 'inherit',
                      color: 'var(--text)',
                      outline: 'none',
                      width: isMobile ? '100%' : 240,
                      transition: 'border-color 150ms',
                    }}
                    onFocus={(e) => (e.currentTarget.style.borderColor = 'var(--accent)')}
                    onBlur={(e) => (e.currentTarget.style.borderColor = 'var(--border)')}
                  />
                </div>

                {toolsLoading ? (
                  <div
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      padding: 40,
                      color: 'var(--text-faint)',
                    }}
                  >
                    <Loader2 size={16} style={{ animation: 'spin 1s linear infinite' }} />
                  </div>
                ) : toolsError ? (
                  <div
                    style={{
                      padding: 20,
                      fontSize: 12,
                      color: 'var(--red)',
                      textAlign: 'center',
                    }}
                  >
                    {toolsError}
                  </div>
                ) : filteredTools.length === 0 ? (
                  <div
                    style={{
                      padding: 20,
                      fontSize: 12,
                      color: 'var(--text-faint)',
                      textAlign: 'center',
                    }}
                  >
                    {toolFilter ? 'No tools match your filter.' : 'No tools available.'}
                  </div>
                ) : grouped ? (
                  <div style={{ display: 'flex', flexDirection: 'column' }}>
                    {grouped.map(([category, catTools], i) => (
                      <div key={category}>
                        {i > 0 && (
                          <div
                            style={{ height: 1, background: 'var(--border)', margin: '4px 0' }}
                          />
                        )}
                        <CategoryGroup
                          category={category}
                          tools={catTools}
                          updating={updating}
                          onSetMode={setMode}
                          onSetCategoryMode={setCategoryMode}
                        />
                      </div>
                    ))}
                  </div>
                ) : (
                  <ToolList tools={filteredTools} updating={updating} onSetMode={setMode} />
                )}
              </div>
            )}

            {/* Logs tab */}
            {activeTab === 'logs' && (
              <div>
                {/* Log rows */}
                {logsLoading && logEntries.length === 0 && (
                  <div
                    style={{
                      padding: 40,
                      textAlign: 'center',
                      color: 'var(--text-faint)',
                      fontSize: 13,
                    }}
                  >
                    Loading…
                  </div>
                )}
                {!logsLoading && logEntries.length === 0 && (
                  <div
                    style={{
                      padding: 40,
                      textAlign: 'center',
                      color: 'var(--text-faint)',
                      fontSize: 13,
                    }}
                  >
                    No log entries yet. Tool calls will appear here.
                  </div>
                )}
                <div
                  style={{
                    display: 'flex',
                    flexDirection: 'column',
                    gap: 8,
                    padding: `16px ${Math.max(sidePad - 8, 12)}px`,
                  }}
                >
                  {logEntries.map((entry) => (
                    <LogCard
                      key={entry.id}
                      entry={entry}
                      onClick={() => setSelectedLog(entry)}
                      onAction={() => inst && fetchLogs({ integration: inst.integration_id })}
                    />
                  ))}
                </div>
              </div>
            )}
          </>
        ) : integration.type === 'api' && integration.tools?.length ? (
          <PreviewToolList
            integration={integration}
            filter={toolFilter}
            onFilterChange={setToolFilter}
            sidePad={sidePad}
            isMobile={isMobile}
          />
        ) : (
          <div
            style={{
              padding: '40px 20px',
              textAlign: 'center',
              color: 'var(--text-faint)',
              fontSize: 13,
            }}
          >
            Connect this integration to see its tools.
          </div>
        )}
      </div>

      <ConnectDialog
        integration={connectOpen ? integration : null}
        open={connectOpen}
        reauth={reauthMode}
        onClose={() => {
          setConnectOpen(false)
          setReauthMode(false)
        }}
      />
      {selectedLog &&
        createPortal(
          <LogDetailPanel entry={selectedLog} onClose={() => setSelectedLog(null)} />,
          document.body,
        )}
      <TotpCodeDialog
        open={totpDialogOpen}
        title="Confirm allow access"
        description={
          pendingTotp.length > 1
            ? `Enter your authenticator code to allow ${pendingTotp.length} tools.`
            : `Enter your authenticator code to allow ${pendingTotp[0]?.toolName ?? 'this tool'}.`
        }
        confirmLabel="Allow"
        onClose={handleTotpClose}
        onSubmit={handleTotpSubmit}
      />
      <style>{`@keyframes spin { to { transform: rotate(360deg) } }`}</style>
    </>
  )
}

const MODES = TOOL_MODES

const CUSTOM_DISPLAY = {
  mode: 'custom',
  label: 'Custom',
  icon: Minus,
  color: 'var(--text-faint)',
  bg: 'transparent',
}

function ModeSelect({
  mode,
  disabled,
  onChange,
}: {
  mode: string
  disabled: boolean
  onChange: (newMode: string) => void
}) {
  const isMobile = useIsMobile()
  const [open, setOpen] = useState(false)
  const [pos, setPos] = useState({ top: 0, right: 0 })
  const triggerRef = useRef<HTMLButtonElement>(null)
  const dropdownRef = useRef<HTMLDivElement>(null)
  const active = mode === 'custom' ? CUSTOM_DISPLAY : MODES.find((m) => m.mode === mode) ?? MODES[1]

  function handleToggle() {
    if (disabled) return
    if (!open && triggerRef.current) {
      const rect = triggerRef.current.getBoundingClientRect()
      setPos({ top: rect.bottom + 4, right: window.innerWidth - rect.right })
    }
    setOpen((v) => !v)
  }

  useEffect(() => {
    if (!open) return
    function handleClick(e: MouseEvent) {
      if (
        !triggerRef.current?.contains(e.target as Node) &&
        !dropdownRef.current?.contains(e.target as Node)
      ) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClick)
    return () => document.removeEventListener('mousedown', handleClick)
  }, [open])

  return (
    <div style={{ position: 'relative', flexShrink: 0 }}>
      {/* Trigger */}
      <button
        ref={triggerRef}
        onClick={handleToggle}
        aria-label={isMobile ? active.label : undefined}
        title={isMobile ? active.label : undefined}
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: isMobile ? 'center' : undefined,
          gap: isMobile ? 0 : 6,
          width: isMobile ? 28 : 148,
          height: isMobile ? 24 : undefined,
          padding: isMobile ? 0 : '4px 8px 4px 10px',
          borderRadius: 5,
          border: '1px solid var(--border)',
          background: open ? 'var(--surface-hover)' : 'transparent',
          color: 'var(--text)',
          fontSize: 11,
          fontWeight: 500,
          cursor: disabled ? 'wait' : 'pointer',
          opacity: disabled ? 0.5 : 1,
          transition: 'background 120ms',
          whiteSpace: 'nowrap',
          outline: 'none',
        }}
        onMouseEnter={(e) => {
          if (!disabled && !open) e.currentTarget.style.background = 'var(--surface-hover)'
        }}
        onMouseLeave={(e) => {
          if (!open) e.currentTarget.style.background = 'transparent'
        }}
      >
        <active.icon size={isMobile ? 13 : 12} style={{ color: active.color, flexShrink: 0 }} />
        {!isMobile && (
          <>
            <span style={{ flex: 1, textAlign: 'left' }}>{active.label}</span>
            <svg
              width="10"
              height="10"
              viewBox="0 0 10 10"
              fill="none"
              style={{
                flexShrink: 0,
                color: 'var(--text-faint)',
                transform: open ? 'rotate(180deg)' : 'rotate(0deg)',
                transition: 'transform 150ms',
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
          </>
        )}
      </button>

      {/* Dropdown rendered via portal to escape overflow clipping */}
      {open &&
        createPortal(
          <div
            ref={dropdownRef}
            style={{
              position: 'fixed',
              top: pos.top,
              right: pos.right,
              minWidth: 180,
              background: 'var(--content-bg)',
              border: '1px solid var(--border)',
              borderRadius: 7,
              boxShadow: '0 4px 16px rgba(0,0,0,0.12), 0 1px 4px rgba(0,0,0,0.08)',
              zIndex: 9999,
              padding: 3,
              display: 'flex',
              flexDirection: 'column',
              gap: 1,
            }}
          >
            {MODES.map(({ mode: m, label, icon: Icon, color, bg }) => {
              const isActive = mode === m
              return (
                <button
                  key={m}
                  onClick={() => {
                    if (!isActive) onChange(m)
                    setOpen(false)
                  }}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 8,
                    padding: '7px 9px',
                    borderRadius: 5,
                    border: 'none',
                    background: isActive ? bg : 'transparent',
                    color: isActive ? color : 'var(--text)',
                    fontSize: 12,
                    fontWeight: isActive ? 500 : 400,
                    cursor: 'pointer',
                    textAlign: 'left',
                    width: '100%',
                    transition: 'background 100ms',
                  }}
                  onMouseEnter={(e) => {
                    if (!isActive) e.currentTarget.style.background = 'var(--surface-hover)'
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.background = isActive ? bg : 'transparent'
                  }}
                >
                  <Icon
                    size={13}
                    style={{ color: isActive ? color : 'var(--text-faint)', flexShrink: 0 }}
                  />
                  <span>{label}</span>
                  {isActive && (
                    <svg
                      width="12"
                      height="12"
                      viewBox="0 0 12 12"
                      fill="none"
                      style={{ marginLeft: 'auto', color }}
                    >
                      <path
                        d="M2 6L5 9L10 3"
                        stroke="currentColor"
                        strokeWidth="1.5"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                      />
                    </svg>
                  )}
                </button>
              )
            })}
          </div>,
          document.body,
        )}
    </div>
  )
}

function ToolRow({
  tool,
  updating,
  onSetMode,
}: {
  tool: ToolWithMode
  updating: string | null
  onSetMode: (name: string, newMode: string, currentMode: string) => void
}) {
  const mode = tool.execution_mode || 'require_approval'
  const isUpdating = updating === tool.name
  return (
    <div
      style={{
        margin: '0 -4px',
        padding: '10px 12px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        gap: 12,
        borderRadius: 6,
        transition: 'background 120ms',
      }}
      onMouseEnter={(e) => (e.currentTarget.style.background = 'var(--surface-hover)')}
      onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
    >
      <div style={{ flex: 1, minWidth: 0 }}>
        <div
          style={{
            fontSize: 13,
            fontWeight: 500,
            color: 'var(--text)',
            fontFamily: '"SF Mono", "Fira Code", monospace',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
          }}
        >
          {tool.title || tool.name}
        </div>
        {tool.description && (
          <div
            style={{
              fontSize: 12,
              color: 'var(--text-faint)',
              marginTop: 2,
              lineHeight: 1.4,
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
            }}
          >
            {tool.description}
          </div>
        )}
      </div>
      <ModeSelect
        mode={mode}
        disabled={isUpdating}
        onChange={(newMode) => onSetMode(tool.name, newMode, mode)}
      />
    </div>
  )
}

function ToolList({
  tools,
  updating,
  onSetMode,
}: {
  tools: ToolWithMode[]
  updating: string | null
  onSetMode: (name: string, newMode: string, currentMode: string) => void
}) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column' }}>
      {tools.map((tool) => (
        <ToolRow key={tool.name} tool={tool} updating={updating} onSetMode={onSetMode} />
      ))}
    </div>
  )
}

function CategoryGroup({
  category,
  tools,
  updating,
  onSetMode,
  onSetCategoryMode,
}: {
  category: string
  tools: ToolWithMode[]
  updating: string | null
  onSetMode: (name: string, newMode: string, currentMode: string) => void
  onSetCategoryMode: (tools: ToolWithMode[], newMode: string) => void
}) {
  const [collapsed, setCollapsed] = useState(true)

  const modes = tools.map((t) => t.execution_mode || 'require_approval')
  const allSame = modes.every((m) => m === modes[0])
  const categoryMode = allSame ? modes[0] : 'custom'

  return (
    <div>
      <div
        onClick={() => setCollapsed((v) => !v)}
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 12,
          margin: '0 -4px',
          padding: '10px 12px',
          borderRadius: 6,
          transition: 'background 120ms',
          cursor: 'pointer',
        }}
        onMouseEnter={(e) => (e.currentTarget.style.background = 'var(--surface-hover)')}
        onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
      >
        <div
          style={{
            display: 'flex',
            alignItems: 'baseline',
            gap: 6,
            flex: 1,
            minWidth: 0,
          }}
        >
          <ChevronRight
            size={13}
            style={{
              color: 'var(--text-faint)',
              transition: 'transform 150ms',
              transform: collapsed ? 'rotate(0deg)' : 'rotate(90deg)',
              flexShrink: 0,
              alignSelf: 'center',
            }}
          />
          <span style={{ fontSize: 14, fontWeight: 600, color: 'var(--text)', lineHeight: 1 }}>
            {category}
          </span>
          <span
            style={{ fontSize: 12, color: 'var(--text-faint)', fontWeight: 400, lineHeight: 1 }}
          >
            {tools.length} {tools.length === 1 ? 'tool' : 'tools'}
          </span>
        </div>
        <div onClick={(e) => e.stopPropagation()}>
          <ModeSelect
            mode={categoryMode}
            disabled={false}
            onChange={(newMode) => onSetCategoryMode(tools, newMode)}
          />
        </div>
      </div>
      {!collapsed && (
        <div
          style={{
            marginLeft: 19,
            paddingLeft: 12,
            display: 'flex',
            flexDirection: 'column',
            paddingBottom: 8,
            paddingTop: 4,
          }}
        >
          <ToolList tools={tools} updating={updating} onSetMode={onSetMode} />
        </div>
      )}
    </div>
  )
}

function PreviewToolRow({ tool }: { tool: { name: string; description?: string } }) {
  return (
    <div
      style={{
        margin: '0 -4px',
        padding: '10px 12px',
        display: 'flex',
        alignItems: 'center',
        gap: 12,
        borderRadius: 6,
        transition: 'background 120ms',
      }}
      onMouseEnter={(e) => (e.currentTarget.style.background = 'var(--surface-hover)')}
      onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
    >
      <div style={{ flex: 1, minWidth: 0 }}>
        <div
          style={{
            fontSize: 13,
            fontWeight: 500,
            color: 'var(--text)',
            fontFamily: '"SF Mono", "Fira Code", monospace',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
          }}
        >
          {tool.name}
        </div>
        {tool.description && (
          <div
            style={{
              fontSize: 12,
              color: 'var(--text-faint)',
              marginTop: 2,
              lineHeight: 1.4,
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
            }}
          >
            {tool.description}
          </div>
        )}
      </div>
    </div>
  )
}

function PreviewToolList({
  integration,
  filter,
  onFilterChange,
  sidePad,
  isMobile,
}: {
  integration: {
    tools?: Array<{ name: string; description?: string }>
    tool_categories?: Record<string, string>
  }
  filter: string
  onFilterChange: (v: string) => void
  sidePad: number
  isMobile: boolean
}) {
  const allTools = integration.tools ?? []
  const filtered = filter
    ? allTools.filter(
        (t) =>
          t.name.toLowerCase().includes(filter.toLowerCase()) ||
          t.description?.toLowerCase().includes(filter.toLowerCase()),
      )
    : allTools

  const categories = integration.tool_categories ?? {}
  const hasCategories = Object.keys(categories).length > 0
  const grouped = hasCategories
    ? Array.from(
        filtered.reduce((map, tool) => {
          const cat = categories[tool.name] || 'Other'
          if (!map.has(cat)) map.set(cat, [])
          map.get(cat)!.push(tool)
          return map
        }, new Map<string, typeof filtered>()),
      ).sort(([a], [b]) => a.localeCompare(b))
    : null

  return (
    <div style={{ padding: `20px ${sidePad}px 48px` }}>
      <div
        style={{ position: 'relative', display: 'flex', alignItems: 'center', marginBottom: 14 }}
      >
        <Search
          size={14}
          style={{
            position: 'absolute',
            left: 10,
            color: 'var(--text-faint)',
            pointerEvents: 'none',
          }}
        />
        <input
          value={filter}
          onChange={(e) => onFilterChange(e.target.value)}
          placeholder="Filter tools..."
          style={{
            height: 32,
            padding: '0 10px 0 32px',
            border: '1px solid var(--border)',
            borderRadius: 7,
            background: 'var(--input-bg)',
            fontSize: 13,
            fontFamily: 'inherit',
            color: 'var(--text)',
            outline: 'none',
            width: isMobile ? '100%' : 240,
            transition: 'border-color 150ms',
          }}
          onFocus={(e) => (e.currentTarget.style.borderColor = 'var(--accent)')}
          onBlur={(e) => (e.currentTarget.style.borderColor = 'var(--border)')}
        />
      </div>

      {filtered.length === 0 ? (
        <div style={{ padding: 20, fontSize: 12, color: 'var(--text-faint)', textAlign: 'center' }}>
          No tools match your filter.
        </div>
      ) : grouped ? (
        <div style={{ display: 'flex', flexDirection: 'column' }}>
          {grouped.map(([category, catTools], i) => (
            <PreviewCategoryGroup
              key={category}
              category={category}
              tools={catTools}
              divider={i > 0}
            />
          ))}
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column' }}>
          {filtered.map((tool) => (
            <PreviewToolRow key={tool.name} tool={tool} />
          ))}
        </div>
      )}
    </div>
  )
}

function PreviewCategoryGroup({
  category,
  tools,
  divider,
}: {
  category: string
  tools: Array<{ name: string; description?: string }>
  divider: boolean
}) {
  const [collapsed, setCollapsed] = useState(true)
  return (
    <div>
      {divider && <div style={{ height: 1, background: 'var(--border)', margin: '4px 0' }} />}
      <div
        onClick={() => setCollapsed((v) => !v)}
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 12,
          margin: '0 -4px',
          padding: '10px 12px',
          borderRadius: 6,
          transition: 'background 120ms',
          cursor: 'pointer',
        }}
        onMouseEnter={(e) => (e.currentTarget.style.background = 'var(--surface-hover)')}
        onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
      >
        <ChevronRight
          size={13}
          style={{
            color: 'var(--text-faint)',
            transition: 'transform 150ms',
            transform: collapsed ? 'rotate(0deg)' : 'rotate(90deg)',
            flexShrink: 0,
          }}
        />
        <span style={{ fontSize: 14, fontWeight: 600, color: 'var(--text)', lineHeight: 1 }}>
          {category}
        </span>
        <span style={{ fontSize: 12, color: 'var(--text-faint)', fontWeight: 400, lineHeight: 1 }}>
          {tools.length} {tools.length === 1 ? 'tool' : 'tools'}
        </span>
      </div>
      {!collapsed && (
        <div
          style={{
            marginLeft: 19,
            paddingLeft: 12,
            display: 'flex',
            flexDirection: 'column',
            paddingBottom: 8,
            paddingTop: 4,
          }}
        >
          {tools.map((tool) => (
            <PreviewToolRow key={tool.name} tool={tool} />
          ))}
        </div>
      )}
    </div>
  )
}

function FilterBar({ children, sidePad = 20 }: { children: React.ReactNode; sidePad?: number }) {
  return (
    <div
      style={{
        height: 44,
        display: 'flex',
        alignItems: 'center',
        padding: `0 ${sidePad}px`,
        borderBottom: '1px solid var(--border)',
        background: 'var(--content-bg)',
        flexShrink: 0,
        gap: 8,
      }}
    >
      {children}
    </div>
  )
}

function BackLink() {
  return (
    <Link
      to="/integrations"
      style={{
        display: 'flex',
        alignItems: 'center',
        color: 'var(--text-dim)',
        textDecoration: 'none',
        marginRight: 4,
      }}
    >
      <ArrowLeft size={15} />
    </Link>
  )
}

function MetaItem({
  label,
  value,
  children,
}: {
  label: string
  value?: string
  children?: React.ReactNode
}) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
      <span
        style={{
          fontSize: 11,
          color: 'var(--text-faint)',
          fontWeight: 500,
          textTransform: 'uppercase',
          letterSpacing: 0.4,
        }}
      >
        {label}
      </span>
      {children || (
        <span style={{ fontSize: 13, color: 'var(--text)', fontWeight: 500 }}>{value}</span>
      )}
    </div>
  )
}
