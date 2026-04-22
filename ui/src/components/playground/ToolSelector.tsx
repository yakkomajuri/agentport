import { useState, useRef, useEffect, useMemo } from 'react'
import { createPortal } from 'react-dom'
import type { Tool } from '@/api/client'

interface ToolSelectorProps {
  tools: Tool[]
  selected: Tool | null
  onSelect: (tool: Tool) => void
  loading: boolean
}

export function ToolSelector({ tools, selected, onSelect, loading }: ToolSelectorProps) {
  const [open, setOpen] = useState(false)
  const [search, setSearch] = useState('')
  const [pos, setPos] = useState({ top: 0, left: 0, width: 0 })
  const triggerRef = useRef<HTMLButtonElement>(null)
  const dropdownRef = useRef<HTMLDivElement>(null)
  const searchRef = useRef<HTMLInputElement>(null)

  const filtered = useMemo(() => {
    if (!search.trim()) return tools
    const q = search.toLowerCase()
    return tools.filter(
      (t) =>
        t.name.toLowerCase().includes(q) ||
        t.title?.toLowerCase().includes(q) ||
        t.description?.toLowerCase().includes(q),
    )
  }, [tools, search])

  const grouped = useMemo(() => {
    const map = new Map<string, Tool[]>()
    for (const tool of filtered) {
      const cat = tool.category || '__other__'
      if (!map.has(cat)) map.set(cat, [])
      map.get(cat)!.push(tool)
    }
    return Array.from(map.entries()).sort(([a], [b]) => {
      if (a === '__other__') return 1
      if (b === '__other__') return -1
      return a.localeCompare(b)
    })
  }, [filtered])

  function openDropdown() {
    if (!triggerRef.current || loading || tools.length === 0) return
    const rect = triggerRef.current.getBoundingClientRect()
    setPos({ top: rect.bottom + 4, left: rect.left, width: rect.width })
    setOpen(true)
    setTimeout(() => searchRef.current?.focus(), 30)
  }

  function close() {
    setOpen(false)
    setSearch('')
  }

  function handleSelect(tool: Tool) {
    onSelect(tool)
    close()
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

  const placeholder = loading ? 'Loading…' : tools.length === 0 ? 'No tools available' : 'Select a tool…'

  return (
    <div style={{ flex: 1, minWidth: 0 }}>
      <button
        ref={triggerRef}
        onClick={openDropdown}
        disabled={loading || tools.length === 0}
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 6,
          width: '100%',
          height: 32,
          padding: '0 8px 0 10px',
          borderRadius: 6,
          border: '1px solid var(--border)',
          background: open ? 'var(--surface-hover)' : 'var(--input-bg)',
          color: selected ? 'var(--text)' : 'var(--text-faint)',
          fontSize: 12,
          fontFamily: 'inherit',
          cursor: loading || tools.length === 0 ? 'default' : 'pointer',
          outline: 'none',
          opacity: loading || tools.length === 0 ? 0.5 : 1,
          textAlign: 'left',
        }}
      >
        <span
          style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}
        >
          {selected ? selected.title || selected.name : placeholder}
        </span>
        <svg
          width="10"
          height="10"
          viewBox="0 0 10 10"
          fill="none"
          style={{
            flexShrink: 0,
            color: 'var(--text-faint)',
            transform: open ? 'rotate(180deg)' : undefined,
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
      </button>

      {open &&
        createPortal(
          <div
            ref={dropdownRef}
            style={{
              position: 'fixed',
              top: pos.top,
              left: pos.left,
              width: pos.width,
              maxHeight: 340,
              background: 'var(--content-bg)',
              border: '1px solid var(--border)',
              borderRadius: 7,
              boxShadow: '0 4px 16px rgba(0,0,0,0.12), 0 1px 4px rgba(0,0,0,0.08)',
              zIndex: 9999,
              display: 'flex',
              flexDirection: 'column',
              overflow: 'hidden',
            }}
          >
            {/* Search */}
            <div
              style={{
                padding: '6px 10px',
                borderBottom: '1px solid var(--border)',
                flexShrink: 0,
              }}
            >
              <input
                ref={searchRef}
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Filter tools…"
                style={{
                  width: '100%',
                  border: 'none',
                  background: 'transparent',
                  fontSize: 12,
                  color: 'var(--text)',
                  outline: 'none',
                  padding: 0,
                }}
              />
            </div>

            {/* Groups */}
            <div style={{ flex: 1, overflowY: 'auto' }}>
              {grouped.length === 0 && (
                <div style={{ padding: '12px 12px', fontSize: 12, color: 'var(--text-faint)' }}>
                  No tools found
                </div>
              )}
              {grouped.map(([cat, catTools]) => (
                <div key={cat}>
                  {(grouped.length > 1 || cat !== '__other__') && (
                    <div
                      style={{
                        padding: '8px 12px 3px',
                        fontSize: 10,
                        fontWeight: 600,
                        textTransform: 'uppercase',
                        letterSpacing: 0.6,
                        color: 'var(--text-faint)',
                      }}
                    >
                      {cat === '__other__' ? 'Other' : cat}
                    </div>
                  )}
                  {catTools.map((tool) => (
                    <ToolOption
                      key={tool.name}
                      tool={tool}
                      active={selected?.name === tool.name}
                      onSelect={handleSelect}
                    />
                  ))}
                </div>
              ))}
            </div>
          </div>,
          document.body,
        )}
    </div>
  )
}

function ToolOption({
  tool,
  active,
  onSelect,
}: {
  tool: Tool
  active: boolean
  onSelect: (t: Tool) => void
}) {
  const [hovered, setHovered] = useState(false)
  return (
    <div
      onClick={() => onSelect(tool)}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      style={{
        padding: '6px 12px',
        cursor: 'pointer',
        background: active
          ? 'var(--surface-selected)'
          : hovered
            ? 'var(--surface-hover)'
            : 'transparent',
      }}
    >
      <div
        style={{
          fontSize: 12,
          color: 'var(--text)',
          fontWeight: 500,
        }}
      >
        {tool.title || tool.name}
      </div>
      {tool.description && (
        <div
          style={{
            fontSize: 11,
            color: 'var(--text-faint)',
            marginTop: 1,
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
          }}
        >
          {tool.description}
        </div>
      )}
    </div>
  )
}
