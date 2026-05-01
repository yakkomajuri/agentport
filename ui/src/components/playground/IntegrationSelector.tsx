import { useState, useRef, useEffect } from 'react'
import { createPortal } from 'react-dom'
import { ChevronDown, Search } from 'lucide-react'
import type { BundledIntegration, InstalledIntegration } from '@/api/client'
import { LOGOS } from '@/components/connections/logos'

interface IntegrationSelectorProps {
  installed: InstalledIntegration[]
  integrations: BundledIntegration[]
  selected: InstalledIntegration | null
  onSelect: (integration: InstalledIntegration) => void
}

export function IntegrationSelector({
  installed,
  integrations,
  selected,
  onSelect,
}: IntegrationSelectorProps) {
  const [open, setOpen] = useState(false)
  const [pos, setPos] = useState({ top: 0, left: 0, width: 0 })
  const [search, setSearch] = useState('')
  const triggerRef = useRef<HTMLButtonElement>(null)
  const dropdownRef = useRef<HTMLDivElement>(null)
  const searchRef = useRef<HTMLInputElement>(null)

  function displayName(inst: InstalledIntegration) {
    return integrations.find((i) => i.id === inst.integration_id)?.name ?? inst.integration_id
  }

  function openDropdown() {
    if (!triggerRef.current || installed.length === 0) return
    const rect = triggerRef.current.getBoundingClientRect()
    setPos({ top: rect.bottom + 4, left: rect.left, width: Math.max(rect.width, 200) })
    setSearch('')
    setOpen(true)
    setTimeout(() => searchRef.current?.focus(), 0)
  }

  function close() {
    setOpen(false)
    setSearch('')
  }

  useEffect(() => {
    if (!open) return
    function onMouseDown(e: MouseEvent) {
      if (
        !triggerRef.current?.contains(e.target as Node) &&
        !dropdownRef.current?.contains(e.target as Node)
      )
        close()
    }
    function onKey(e: KeyboardEvent) {
      if (e.key === 'Escape') close()
    }
    document.addEventListener('mousedown', onMouseDown)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('mousedown', onMouseDown)
      document.removeEventListener('keydown', onKey)
    }
  }, [open])

  return (
    <div style={{ flexShrink: 0 }}>
      <button
        ref={triggerRef}
        onClick={openDropdown}
        disabled={installed.length === 0}
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 8,
          height: 34,
          padding: '0 10px 0 8px',
          borderRadius: 6,
          border: '1px solid var(--border)',
          background: open ? 'var(--surface-hover)' : 'var(--input-bg)',
          cursor: installed.length === 0 ? 'default' : 'pointer',
          outline: 'none',
          minWidth: 160,
        }}
        onMouseEnter={(e) => {
          if (!open) e.currentTarget.style.background = 'var(--surface-hover)'
        }}
        onMouseLeave={(e) => {
          if (!open) e.currentTarget.style.background = 'var(--input-bg)'
        }}
      >
        {selected ? (
          <>
            <IntegrationLogo integration_id={selected.integration_id} size={18} />
            <span
              style={{
                fontSize: 13,
                fontWeight: 500,
                color: 'var(--text)',
                flex: 1,
                textAlign: 'left',
              }}
            >
              {displayName(selected)}
            </span>
          </>
        ) : (
          <span style={{ fontSize: 13, color: 'var(--text-faint)', flex: 1, textAlign: 'left' }}>
            Integration…
          </span>
        )}
        <ChevronDown
          size={11}
          style={{
            color: 'var(--text-faint)',
            flexShrink: 0,
            transform: open ? 'rotate(180deg)' : undefined,
            transition: 'transform 150ms',
          }}
        />
      </button>

      {open &&
        createPortal(
          <div
            ref={dropdownRef}
            style={{
              position: 'fixed',
              top: pos.top,
              left: pos.left,
              minWidth: pos.width,
              background: 'var(--content-bg)',
              border: '1px solid var(--border)',
              borderRadius: 7,
              boxShadow: '0 4px 16px rgba(0,0,0,0.12), 0 1px 4px rgba(0,0,0,0.08)',
              zIndex: 9999,
              padding: 3,
              display: 'flex',
              flexDirection: 'column',
            }}
          >
            <div style={{ padding: '3px 3px 4px', flexShrink: 0 }}>
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 6,
                  padding: '0 8px',
                  height: 30,
                  borderRadius: 5,
                  border: '1px solid var(--border)',
                  background: 'var(--input-bg)',
                }}
              >
                <Search size={12} style={{ color: 'var(--text-faint)', flexShrink: 0 }} />
                <input
                  ref={searchRef}
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  placeholder="Search…"
                  style={{
                    border: 'none',
                    outline: 'none',
                    background: 'transparent',
                    fontSize: 12,
                    color: 'var(--text)',
                    width: '100%',
                  }}
                />
              </div>
            </div>
            <div style={{ overflowY: 'auto', maxHeight: 240 }}>
              {installed
                .filter((inst) => displayName(inst).toLowerCase().includes(search.toLowerCase()))
                .map((inst) => (
                  <IntegrationOption
                    key={inst.integration_id}
                    inst={inst}
                    label={displayName(inst)}
                    active={selected?.integration_id === inst.integration_id}
                    onSelect={() => {
                      onSelect(inst)
                      close()
                    }}
                  />
                ))}
            </div>
          </div>,
          document.body,
        )}
    </div>
  )
}

function IntegrationOption({
  inst,
  label,
  active,
  onSelect,
}: {
  inst: InstalledIntegration
  label: string
  active: boolean
  onSelect: () => void
}) {
  const [hovered, setHovered] = useState(false)
  return (
    <div
      onClick={onSelect}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 10,
        padding: '6px 10px',
        borderRadius: 5,
        cursor: 'pointer',
        background: active
          ? 'var(--surface-selected)'
          : hovered
            ? 'var(--surface-hover)'
            : 'transparent',
      }}
    >
      <IntegrationLogo integration_id={inst.integration_id} size={20} />
      <span style={{ fontSize: 13, fontWeight: active ? 500 : 400, color: 'var(--text)' }}>
        {label}
      </span>
    </div>
  )
}

function IntegrationLogo({ integration_id, size }: { integration_id: string; size: number }) {
  const logo = LOGOS[integration_id]
  if (logo) {
    return (
      <img
        src={logo.src}
        alt={integration_id}
        style={{
          width: size,
          height: size,
          objectFit: 'contain',
          flexShrink: 0,
          filter: logo.darkInvert ? 'var(--logo-invert-filter)' : undefined,
        }}
      />
    )
  }
  return (
    <div
      style={{
        width: size,
        height: size,
        borderRadius: 4,
        background: 'var(--surface)',
        border: '1px solid var(--border)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        fontSize: size * 0.55,
        fontWeight: 600,
        color: 'var(--text-dim)',
        flexShrink: 0,
      }}
    >
      {integration_id.charAt(0).toUpperCase()}
    </div>
  )
}
