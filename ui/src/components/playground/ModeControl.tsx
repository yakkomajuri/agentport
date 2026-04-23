import { useState, useRef, useEffect } from 'react'
import { createPortal } from 'react-dom'
import { AlertTriangle, ChevronDown, Loader2 } from 'lucide-react'
import { TOOL_MODES } from '@/lib/toolModes'
import { api } from '@/api/client'
import { isTotpChallengeError } from '@/lib/totpError'
import { TotpCodeDialog } from '@/components/totp/TotpCodeDialog'

const MODE_DESCRIPTIONS: Record<string, string> = {
  allow: 'Runs immediately without asking',
  require_approval: 'Each call needs manual approval',
  deny: 'All calls are blocked from running',
}

interface ModeControlProps {
  mode: string | undefined
  integrationName: string
  toolName: string
  onModeChange: (newMode: string) => void
}

export function ModeControl({ mode, integrationName, toolName, onModeChange }: ModeControlProps) {
  const [open, setOpen] = useState(false)
  const [pendingMode, setPendingMode] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [totpDialogOpen, setTotpDialogOpen] = useState(false)
  const triggerRef = useRef<HTMLButtonElement>(null)
  const popoverRef = useRef<HTMLDivElement>(null)
  const [pos, setPos] = useState({ top: 0, left: 0 })

  const currentConfig = TOOL_MODES.find((m) => m.mode === mode) ?? TOOL_MODES[1]
  const CurrentIcon = currentConfig.icon

  const pendingConfig = pendingMode
    ? (TOOL_MODES.find((m) => m.mode === pendingMode) ?? null)
    : null
  const hasChange = pendingMode !== null && pendingMode !== (mode ?? 'require_approval')

  function handleOpen() {
    if (!triggerRef.current) return
    const rect = triggerRef.current.getBoundingClientRect()
    const left = Math.min(rect.left, window.innerWidth - 316)
    setPos({ top: rect.bottom + 5, left })
    setPendingMode(mode ?? 'require_approval')
    setError(null)
    setOpen(true)
  }

  function handleClose() {
    if (saving) return
    setOpen(false)
    setPendingMode(null)
    setError(null)
  }

  async function savePending(totpCode?: string) {
    if (!pendingMode) return
    await api.toolSettings.update(integrationName, toolName, pendingMode, totpCode)
    onModeChange(pendingMode)
    setOpen(false)
    setPendingMode(null)
  }

  async function handleSave() {
    if (!pendingMode || !hasChange) return
    setSaving(true)
    setError(null)
    try {
      await savePending()
    } catch (e) {
      if (isTotpChallengeError(e)) {
        setOpen(false)
        setTotpDialogOpen(true)
      } else {
        setError(e instanceof Error ? e.message : 'Failed to save')
      }
    } finally {
      setSaving(false)
    }
  }

  async function handleTotpSubmit(code: string) {
    // Throw back to TotpCodeDialog on failure so it can surface the error
    // in its own UI (e.g. wrong code → inline message, dialog stays open).
    await savePending(code)
  }

  function handleTotpClose() {
    setTotpDialogOpen(false)
    setPendingMode(null)
    setError(null)
  }

  useEffect(() => {
    if (!open) return
    function onPointerDown(e: PointerEvent) {
      const target = e.target as Node
      if (triggerRef.current?.contains(target) || popoverRef.current?.contains(target)) return
      handleClose()
    }
    document.addEventListener('pointerdown', onPointerDown)
    return () => document.removeEventListener('pointerdown', onPointerDown)
  }, [open, saving])

  useEffect(() => {
    if (!open) return
    function onKey(e: KeyboardEvent) {
      if (e.key === 'Escape') handleClose()
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [open, saving])

  return (
    <>
      <button
        ref={triggerRef}
        onClick={open ? handleClose : handleOpen}
        title="Change execution mode"
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: 5,
          padding: '3px 7px 3px 9px',
          borderRadius: 5,
          background: currentConfig.bg,
          color: currentConfig.color,
          fontSize: 11,
          fontWeight: 500,
          border: `1px solid color-mix(in srgb, ${currentConfig.color} 28%, transparent)`,
          cursor: 'pointer',
          flexShrink: 0,
          whiteSpace: 'nowrap',
          outline: open
            ? `2px solid color-mix(in srgb, ${currentConfig.color} 35%, transparent)`
            : 'none',
          outlineOffset: 1,
          transition: 'outline 100ms',
        }}
      >
        <CurrentIcon size={11} />
        {currentConfig.label}
        <ChevronDown
          size={10}
          style={{
            opacity: 0.55,
            marginLeft: 1,
            transform: open ? 'rotate(180deg)' : 'none',
            transition: 'transform 150ms',
          }}
        />
      </button>

      {open &&
        createPortal(
          <div
            ref={popoverRef}
            style={{
              position: 'fixed',
              top: pos.top,
              left: pos.left,
              width: 300,
              background: 'var(--content-bg)',
              border: '1px solid var(--border)',
              borderRadius: 8,
              boxShadow: '0 6px 24px rgba(0,0,0,0.11), 0 1px 4px rgba(0,0,0,0.07)',
              zIndex: 9999,
              overflow: 'hidden',
            }}
          >
            {/* Header */}
            <div
              style={{
                padding: '10px 12px 9px',
                borderBottom: '1px solid var(--border)',
              }}
            >
              <div
                style={{
                  fontSize: 11,
                  fontWeight: 600,
                  textTransform: 'uppercase',
                  letterSpacing: 0.55,
                  color: 'var(--text-faint)',
                }}
              >
                Execution mode
              </div>
              <div
                style={{
                  fontSize: 12,
                  color: 'var(--text-dim)',
                  marginTop: 2,
                  fontWeight: 400,
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                  whiteSpace: 'nowrap',
                }}
              >
                {toolName}
              </div>
            </div>

            {/* Mode options */}
            <div style={{ padding: '5px 5px 3px' }}>
              {TOOL_MODES.map((m) => {
                const MIcon = m.icon
                const isSelected = pendingMode === m.mode
                return (
                  <button
                    key={m.mode}
                    onClick={() => setPendingMode(m.mode)}
                    style={{
                      display: 'flex',
                      alignItems: 'flex-start',
                      gap: 10,
                      width: '100%',
                      padding: '8px 10px 8px 9px',
                      borderRadius: 5,
                      background: isSelected ? m.bg : 'transparent',
                      border: isSelected
                        ? `1px solid color-mix(in srgb, ${m.color} 22%, transparent)`
                        : '1px solid transparent',
                      borderLeft: isSelected ? `3px solid ${m.color}` : '3px solid transparent',
                      cursor: 'pointer',
                      textAlign: 'left',
                      transition: 'background 100ms',
                    }}
                  >
                    <MIcon
                      size={13}
                      style={{
                        color: isSelected ? m.color : 'var(--text-faint)',
                        marginTop: 2,
                        flexShrink: 0,
                      }}
                    />
                    <div>
                      <div
                        style={{
                          fontSize: 12,
                          fontWeight: isSelected ? 500 : 400,
                          color: isSelected ? m.color : 'var(--text)',
                          lineHeight: 1.3,
                        }}
                      >
                        {m.label}
                      </div>
                      <div
                        style={{
                          fontSize: 11,
                          color: 'var(--text-faint)',
                          marginTop: 2,
                          lineHeight: 1.35,
                        }}
                      >
                        {MODE_DESCRIPTIONS[m.mode]}
                      </div>
                    </div>
                  </button>
                )
              })}
            </div>

            {/* Warning + actions — only visible when a change is pending */}
            <div
              style={{
                overflow: 'hidden',
                maxHeight: hasChange ? 200 : 0,
                transition: 'max-height 180ms ease',
              }}
            >
              <div style={{ padding: '0 5px 5px' }}>
                {/* Warning strip */}
                <div
                  style={{
                    display: 'flex',
                    gap: 8,
                    alignItems: 'flex-start',
                    padding: '8px 10px',
                    background: 'rgba(245, 166, 35, 0.07)',
                    border: '1px solid rgba(245, 166, 35, 0.22)',
                    borderRadius: 5,
                    marginBottom: 5,
                  }}
                >
                  <AlertTriangle
                    size={12}
                    style={{ color: 'var(--amber, #f5a623)', flexShrink: 0, marginTop: 1 }}
                  />
                  <span style={{ fontSize: 11, color: 'var(--text-dim)', lineHeight: 1.45 }}>
                    This updates the real setting for{' '}
                    <span style={{ fontWeight: 500, color: 'var(--text)' }}>{toolName}</span> — not
                    just in the playground. Applies to all agents and API calls.
                  </span>
                </div>

                {/* Error */}
                {error && (
                  <div
                    style={{
                      fontSize: 11,
                      color: 'var(--red, #dc2626)',
                      padding: '4px 10px',
                      marginBottom: 4,
                    }}
                  >
                    {error}
                  </div>
                )}

                {/* Action row */}
                <div style={{ display: 'flex', gap: 5 }}>
                  <button
                    onClick={handleClose}
                    disabled={saving}
                    style={{
                      flex: 1,
                      padding: '5px 10px',
                      fontSize: 11,
                      fontWeight: 500,
                      border: '1px solid var(--border)',
                      borderRadius: 5,
                      background: 'transparent',
                      color: 'var(--text-dim)',
                      cursor: saving ? 'not-allowed' : 'pointer',
                      opacity: saving ? 0.5 : 1,
                    }}
                  >
                    Cancel
                  </button>
                  <button
                    onClick={handleSave}
                    disabled={saving}
                    style={{
                      flex: 2,
                      padding: '5px 10px',
                      fontSize: 11,
                      fontWeight: 500,
                      border: 'none',
                      borderRadius: 5,
                      background: pendingConfig?.color ?? 'var(--blue)',
                      color: '#fff',
                      cursor: saving ? 'wait' : 'pointer',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      gap: 5,
                      opacity: saving ? 0.75 : 1,
                      transition: 'opacity 120ms',
                    }}
                  >
                    {saving && (
                      <Loader2 size={10} style={{ animation: 'spin 1s linear infinite' }} />
                    )}
                    {saving ? 'Saving…' : `Set to ${pendingConfig?.label ?? '…'}`}
                  </button>
                </div>
              </div>
            </div>
          </div>,
          document.body,
        )}

      <TotpCodeDialog
        open={totpDialogOpen}
        title="Confirm allow access"
        description={`Enter your authenticator code to let ${toolName} run without approval.`}
        confirmLabel="Allow"
        onClose={handleTotpClose}
        onSubmit={handleTotpSubmit}
      />
    </>
  )
}
