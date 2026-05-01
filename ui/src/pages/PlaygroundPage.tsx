import { useEffect, useMemo, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { Link } from 'react-router-dom'
import { ChevronDown, Loader2, Play, X } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { api, type InstalledIntegration, type Tool } from '@/api/client'
import { useConnectionsStore } from '@/stores/connections'
import { IntegrationSelector } from '@/components/playground/IntegrationSelector'
import { ToolSelector } from '@/components/playground/ToolSelector'
import { ModeControl } from '@/components/playground/ModeControl'
import { SchemaForm } from '@/components/playground/SchemaForm'
import { ResponsePanel, type PlaygroundResult } from '@/components/playground/ResponsePanel'
import ApprovePage from '@/pages/ApprovePage'
import { useIsMobile } from '@/lib/useMediaQuery'

export default function PlaygroundPage() {
  const { installed, integrations, fetchInstalled, fetchIntegrations } = useConnectionsStore()
  const isMobile = useIsMobile()
  const sidePad = isMobile ? 14 : 20

  const [selectedIntegration, setSelectedIntegration] = useState<InstalledIntegration | null>(null)
  const [tools, setTools] = useState<Tool[]>([])
  const [toolsLoading, setToolsLoading] = useState(false)
  const [selectedTool, setSelectedTool] = useState<Tool | null>(null)

  const [fieldValues, setFieldValues] = useState<Record<string, unknown>>({})
  const [rawMode, setRawMode] = useState(false)
  const [rawJson, setRawJson] = useState('{}')
  const [paramsOpen, setParamsOpen] = useState(false)

  const [running, setRunning] = useState(false)
  const [awaitingApproval, setAwaitingApproval] = useState(false)
  const [result, setResult] = useState<PlaygroundResult | null>(null)
  const [durationMs, setDurationMs] = useState<number | null>(null)
  const lastArgsRef = useRef<Record<string, unknown>>({})
  const doCallRef = useRef<(args: Record<string, unknown>) => Promise<void>>(async () => {})

  const [drawerOpen, setDrawerOpen] = useState(false)
  const approvalRequestId =
    result?.status === 'approval_required' ? result.data.approval_request_id : null
  const selectedIntegrationId = selectedIntegration?.integration_id ?? null

  useEffect(() => {
    if (installed.length === 0) fetchInstalled()
    if (integrations.length === 0) fetchIntegrations()
  }, [fetchInstalled, fetchIntegrations, installed.length, integrations.length])

  // Auto-select first integration once the list loads
  useEffect(() => {
    if (installed.length > 0 && !selectedIntegration) {
      setSelectedIntegration(installed[0])
    }
  }, [installed, selectedIntegration])

  useEffect(() => {
    if (!selectedIntegrationId) {
      setTools([])
      return
    }
    setToolsLoading(true)
    setSelectedTool(null)
    setFieldValues({})
    setRawJson('{}')
    setRawMode(false)
    setResult(null)
    setDurationMs(null)
    api.tools
      .listForIntegration(selectedIntegrationId)
      .then((fetched) => {
        setTools(fetched)
        if (fetched.length > 0) setSelectedTool(fetched[0])
      })
      .catch(() => setTools([]))
      .finally(() => setToolsLoading(false))
  }, [selectedIntegrationId])

  useEffect(() => {
    if (!selectedTool) return
    setFieldValues(initFieldValues(selectedTool))
    setRawJson('{}')
    setRawMode(false)
    setResult(null)
    setDurationMs(null)
  }, [selectedTool])

  // Auto-poll when awaiting approval
  useEffect(() => {
    if (!awaitingApproval || !approvalRequestId) return
    const interval = setInterval(async () => {
      try {
        const req = await api.approvals.get(approvalRequestId)
        if (req.status === 'approved' || req.status === 'consumed') {
          clearInterval(interval)
          setAwaitingApproval(false)
          setDrawerOpen(false)
          await doCallRef.current(lastArgsRef.current)
        } else if (req.status === 'denied' || req.status === 'expired') {
          clearInterval(interval)
          setAwaitingApproval(false)
          setResult({
            status: 'denied',
            data: { error: 'denied', message: `Approval request was ${req.status}.` },
          })
        }
      } catch {
        // transient errors — keep polling
      }
    }, 2000)
    return () => clearInterval(interval)
  }, [awaitingApproval, approvalRequestId])

  function initFieldValues(tool: Tool): Record<string, unknown> {
    const props =
      (tool.inputSchema?.properties as Record<string, { type?: string }> | undefined) ?? {}
    const vals: Record<string, unknown> = {}
    for (const [key, prop] of Object.entries(props)) {
      vals[key] = prop.type === 'boolean' ? false : ''
    }
    return vals
  }

  function buildArgs(): Record<string, unknown> | null {
    if (rawMode) {
      try {
        return rawJson.trim() ? JSON.parse(rawJson) : {}
      } catch {
        return null
      }
    }
    const schema = selectedTool?.inputSchema
    const props = schema?.properties as Record<string, { type?: string }> | undefined
    if (!props || Object.keys(props).length === 0) return {}

    const args: Record<string, unknown> = {}
    for (const [key, prop] of Object.entries(props)) {
      const raw = fieldValues[key]
      if (prop.type === 'number' || prop.type === 'integer') {
        if (raw !== '' && raw !== undefined) {
          const n = Number(raw)
          if (!isNaN(n)) args[key] = n
        }
      } else if (prop.type === 'boolean') {
        args[key] = Boolean(raw)
      } else if (prop.type === 'array' || prop.type === 'object') {
        if (typeof raw === 'string' && raw.trim()) {
          try {
            args[key] = JSON.parse(raw)
          } catch {
            return null
          }
        }
      } else {
        if (raw !== '' && raw !== undefined) args[key] = raw
      }
    }
    return args
  }

  async function doCall(args: Record<string, unknown>) {
    if (!selectedIntegration || !selectedTool) return
    setRunning(true)
    const start = Date.now()
    try {
      const res = await api.tools.call(selectedIntegration.integration_id, selectedTool.name, args)
      setDurationMs(Date.now() - start)
      setResult(res)
      if (res.status === 'approval_required') {
        setAwaitingApproval(true)
      }
    } finally {
      setRunning(false)
    }
  }
  doCallRef.current = doCall

  async function handleRun() {
    const args = buildArgs()
    if (args === null) return
    lastArgsRef.current = args
    setAwaitingApproval(false)
    setResult(null)
    setDurationMs(null)
    await doCall(args)
  }

  function handleRawToggle(toRaw: boolean) {
    if (toRaw) {
      const args = buildArgs() ?? {}
      setRawJson(JSON.stringify(args, null, 2))
    }
    setRawMode(toRaw)
  }

  const hasProperties = useMemo(() => {
    const props = selectedTool?.inputSchema?.properties as Record<string, unknown> | undefined
    return props && Object.keys(props).length > 0
  }, [selectedTool])

  const paramCount = useMemo(() => {
    const props = selectedTool?.inputSchema?.properties as Record<string, unknown> | undefined
    return props ? Object.keys(props).length : 0
  }, [selectedTool])

  const hasUnfilledRequired = useMemo(() => {
    if (rawMode) return false
    const schema = selectedTool?.inputSchema
    const required = (schema?.required as string[]) ?? []
    if (required.length === 0) return false
    const props = schema?.properties as Record<string, { type?: string }> | undefined
    return required.some((key) => {
      const prop = props?.[key]
      if (prop?.type === 'boolean') return false
      const val = fieldValues[key]
      return val === '' || val === undefined || val === null
    })
  }, [rawMode, selectedTool, fieldValues])

  const canRun = !!(selectedIntegration && selectedTool && !running && !hasUnfilledRequired)
  const isMac = navigator.platform.toUpperCase().includes('MAC')
  const handleRunRef = useRef(handleRun)
  handleRunRef.current = handleRun

  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === 'Enter' && (e.metaKey || e.ctrlKey) && canRun) {
        e.preventDefault()
        handleRunRef.current()
      }
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [canRun])

  return (
    <>
      {/* Page header */}
      <div
        style={{
          height: 44,
          display: 'flex',
          alignItems: 'center',
          padding: `0 ${sidePad}px`,
          borderBottom: '1px solid var(--border)',
          background: 'var(--content-bg)',
          flexShrink: 0,
        }}
      >
        <span style={{ fontSize: 13, fontWeight: 500, color: 'var(--text)' }}>Playground</span>
      </div>

      {/* Toolbar */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          flexWrap: isMobile ? 'wrap' : 'nowrap',
          gap: 8,
          padding: `10px ${sidePad}px`,
          borderBottom: '1px solid var(--border)',
          background: 'var(--content-bg)',
          flexShrink: 0,
        }}
      >
        {/* Integration */}
        {installed.length === 0 ? (
          <div style={{ fontSize: 12, color: 'var(--text-faint)' }}>
            No integrations.{' '}
            <Link
              to="/integrations"
              style={{ color: 'var(--blue)', textDecoration: 'none', fontWeight: 500 }}
            >
              Connect one →
            </Link>
          </div>
        ) : (
          <>
            <IntegrationSelector
              installed={installed}
              integrations={integrations}
              selected={selectedIntegration}
              onSelect={setSelectedIntegration}
            />

            {/* Separator */}
            {!isMobile && (
              <span style={{ color: 'var(--border-strong)', fontSize: 16, userSelect: 'none' }}>
                /
              </span>
            )}

            {/* Tool selector */}
            <div
              style={{
                flex: isMobile ? '1 1 100%' : '1 1 auto',
                minWidth: 0,
                maxWidth: isMobile ? '100%' : 400,
              }}
            >
              <ToolSelector
                tools={tools}
                selected={selectedTool}
                onSelect={setSelectedTool}
                loading={toolsLoading}
              />
            </div>

            {/* Mode control */}
            {selectedTool && selectedIntegration && (
              <ModeControl
                mode={selectedTool.execution_mode}
                integrationName={selectedIntegration.integration_id}
                toolName={selectedTool.name}
                onModeChange={(newMode) =>
                  setSelectedTool((prev) => (prev ? { ...prev, execution_mode: newMode } : prev))
                }
              />
            )}

            {/* Spacer */}
            <div style={{ flex: 1 }} />

            {/* Run */}
            <Button
              onClick={handleRun}
              disabled={!canRun}
              size="sm"
              style={{ gap: 5, paddingLeft: 12, paddingRight: 14 }}
            >
              {running ? (
                <Loader2 size={12} style={{ animation: 'spin 1s linear infinite' }} />
              ) : (
                <Play size={12} />
              )}
              {running ? 'Running…' : 'Run'}
              {!running && !isMobile && (
                <span style={{ fontSize: 10, opacity: 0.5, letterSpacing: 0 }}>
                  {isMac ? '⌘↵' : 'Ctrl+↵'}
                </span>
              )}
            </Button>
          </>
        )}
      </div>

      {/* Content area */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
        {/* Parameters section (collapsible) */}
        {selectedTool && (
          <div
            style={{
              flexShrink: 0,
              borderBottom: '1px solid var(--border)',
              maxHeight: paramsOpen ? '50vh' : undefined,
              overflowY: paramsOpen ? 'auto' : undefined,
            }}
          >
            {/* Section header — always visible, toggles collapse */}
            <button
              onClick={() => setParamsOpen((v) => !v)}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 8,
                width: '100%',
                padding: `9px ${sidePad}px`,
                background: 'none',
                border: 'none',
                cursor: 'pointer',
                textAlign: 'left',
                borderBottom: 'none',
              }}
            >
              <ChevronDown
                size={13}
                style={{
                  color: 'var(--text-faint)',
                  transform: paramsOpen ? undefined : 'rotate(-90deg)',
                  transition: 'transform 150ms',
                  flexShrink: 0,
                }}
              />
              <span
                style={{
                  fontSize: 11,
                  fontWeight: 600,
                  textTransform: 'uppercase',
                  letterSpacing: 0.6,
                  color: 'var(--text-faint)',
                }}
              >
                Parameters
              </span>
              {hasUnfilledRequired && (
                <span style={{ fontSize: 11, color: 'var(--red)', lineHeight: 1 }}>*</span>
              )}
              {paramCount > 0 && (
                <span
                  style={{
                    fontSize: 10,
                    fontWeight: 500,
                    color: 'var(--text-faint)',
                    background: 'var(--surface)',
                    border: '1px solid var(--border)',
                    padding: '1px 6px',
                    borderRadius: 4,
                  }}
                >
                  {paramCount}
                </span>
              )}
              {/* Form/Raw toggle — right-aligned, only when there are properties */}
              {hasProperties && (
                <div
                  style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 4 }}
                  onClick={(e) => e.stopPropagation()}
                >
                  <div
                    style={{
                      display: 'flex',
                      background: 'var(--surface)',
                      border: '1px solid var(--border)',
                      borderRadius: 4,
                      padding: 2,
                      gap: 1,
                    }}
                  >
                    {(['Form', 'Raw'] as const).map((mode) => {
                      const isActive = mode === 'Raw' ? rawMode : !rawMode
                      return (
                        <button
                          key={mode}
                          onClick={() => handleRawToggle(mode === 'Raw')}
                          style={{
                            fontSize: 10,
                            fontWeight: 500,
                            padding: '1px 7px',
                            borderRadius: 3,
                            border: 'none',
                            cursor: 'pointer',
                            background: isActive ? 'var(--content-bg)' : 'transparent',
                            color: isActive ? 'var(--text)' : 'var(--text-faint)',
                            boxShadow: isActive ? '0 1px 2px rgba(0,0,0,0.06)' : 'none',
                            transition: 'background 120ms',
                          }}
                        >
                          {mode}
                        </button>
                      )
                    })}
                  </div>
                </div>
              )}
            </button>

            {/* Fields */}
            {paramsOpen && (
              <div style={{ padding: isMobile ? '12px 14px 14px' : '16px 20px 16px 41px' }}>
                <SchemaForm
                  schema={selectedTool.inputSchema as Record<string, unknown> | undefined}
                  values={fieldValues}
                  rawMode={rawMode}
                  rawJson={rawJson}
                  onFieldChange={(field, value) =>
                    setFieldValues((prev) => ({ ...prev, [field]: value }))
                  }
                  onRawJsonChange={setRawJson}
                />
              </div>
            )}
          </div>
        )}

        {/* Response */}
        <div style={{ flex: 1, overflowY: 'auto', padding: isMobile ? 14 : 24 }}>
          <ResponsePanel
            result={result}
            running={running}
            awaitingApproval={awaitingApproval}
            durationMs={durationMs}
            onOpenDrawer={() => setDrawerOpen(true)}
            onCancelPolling={() => setAwaitingApproval(false)}
          />
        </div>
      </div>

      {/* Approval drawer */}
      {drawerOpen &&
        approvalRequestId &&
        createPortal(
          <>
            <div
              onClick={() => setDrawerOpen(false)}
              style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.3)', zIndex: 9998 }}
            />
            <div
              style={{
                position: 'fixed',
                top: 0,
                right: 0,
                bottom: 0,
                width: isMobile ? '100%' : 480,
                maxWidth: '100%',
                background: 'var(--content-bg)',
                borderLeft: '1px solid var(--border)',
                zIndex: 9999,
                display: 'flex',
                flexDirection: 'column',
                boxShadow: '-8px 0 32px rgba(0,0,0,0.12)',
                overflowY: 'auto',
              }}
            >
              <div
                style={{
                  height: 44,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  padding: '0 16px',
                  borderBottom: '1px solid var(--border)',
                  flexShrink: 0,
                  position: 'sticky',
                  top: 0,
                  background: 'var(--content-bg)',
                  zIndex: 1,
                }}
              >
                <span style={{ fontSize: 12, fontWeight: 500, color: 'var(--text-dim)' }}>
                  Approve tool call
                </span>
                <button
                  onClick={() => setDrawerOpen(false)}
                  style={{
                    width: 24,
                    height: 24,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    background: 'none',
                    border: 'none',
                    cursor: 'pointer',
                    color: 'var(--text-faint)',
                    borderRadius: 4,
                  }}
                  onMouseEnter={(e) => (e.currentTarget.style.color = 'var(--text)')}
                  onMouseLeave={(e) => (e.currentTarget.style.color = 'var(--text-faint)')}
                >
                  <X size={15} />
                </button>
              </div>
              <ApprovePage
                overrideId={approvalRequestId}
                embeddedProp={true}
                onAllowTool={(_integrationName, toolName) => {
                  // Close the drawer and re-run immediately — don't wait for the polling cycle.
                  // Also flip the tool's local execution_mode so the ModeControl reflects the change.
                  setDrawerOpen(false)
                  setAwaitingApproval(false)
                  setSelectedTool((prev) =>
                    prev && prev.name === toolName ? { ...prev, execution_mode: 'allow' } : prev,
                  )
                  api.toolSettings.update(_integrationName, toolName, 'allow').catch(() => {
                    /* best-effort — wildcard policy already covers enforcement */
                  })
                  doCallRef.current(lastArgsRef.current)
                }}
              />
            </div>
          </>,
          document.body,
        )}

      <style>{`@keyframes spin { to { transform: rotate(360deg) } }`}</style>
    </>
  )
}
