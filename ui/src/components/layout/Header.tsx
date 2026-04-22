import { useEffect, useRef, useState } from 'react'
import { usePostHog } from '@posthog/react'
import { Menu, Moon, Sun } from 'lucide-react'
import { useThemeStore } from '@/stores/theme'
import { useAuthStore } from '@/stores/auth'
import { useNavigate } from 'react-router-dom'

function emailColor(email: string): string {
  let hash = 0
  for (let i = 0; i < email.length; i++) {
    hash = email.charCodeAt(i) + ((hash << 5) - hash)
  }
  const h = Math.abs(hash) % 360
  return `hsl(${h}, 45%, 50%)`
}

interface HeaderProps {
  /** When defined, a hamburger button is shown on the left that calls this to open the mobile drawer. */
  onOpenDrawer?: () => void
}

export function Header({ onOpenDrawer }: HeaderProps) {
  const { theme, toggle } = useThemeStore()
  const { email, isAdmin, logout } = useAuthStore()
  const posthog = usePostHog()
  const navigate = useNavigate()
  const [open, setOpen] = useState(false)
  const menuRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    function onClickOutside(e: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', onClickOutside)
    return () => document.removeEventListener('mousedown', onClickOutside)
  }, [open])

  function handleLogout() {
    posthog?.reset()
    logout()
    navigate('/login')
  }

  const initial = email ? email[0].toUpperCase() : '?'
  const bgColor = email ? emailColor(email) : 'var(--surface-hover)'

  return (
    <header
      style={{
        height: 44,
        display: 'flex',
        alignItems: 'center',
        padding: '0 12px',
        background: 'var(--bg)',
        borderBottom: '1px solid var(--border)',
        flexShrink: 0,
        gap: 12,
      }}
    >
      {onOpenDrawer && (
        <button
          onClick={onOpenDrawer}
          aria-label="Open menu"
          style={{
            width: 32,
            height: 32,
            borderRadius: 6,
            border: 'none',
            background: 'none',
            color: 'var(--text-dim)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            cursor: 'pointer',
          }}
        >
          <Menu size={16} />
        </button>
      )}

      <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 8 }}>
        <button
          onClick={toggle}
          title="Toggle theme"
          style={{
            width: 28,
            height: 28,
            borderRadius: 6,
            border: 'none',
            background: 'var(--bg)',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: 'var(--text-dim)',
          }}
        >
          {theme === 'light' ? <Moon size={14} /> : <Sun size={14} />}
        </button>

        <div ref={menuRef} style={{ position: 'relative' }}>
          <button
            onClick={() => setOpen((v) => !v)}
            title={email ?? 'Account'}
            style={{
              width: 26,
              height: 26,
              borderRadius: 99,
              background: bgColor,
              border: 'none',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontSize: 11,
              fontWeight: 700,
              color: '#fff',
              cursor: 'pointer',
              letterSpacing: 0,
            }}
          >
            {initial}
          </button>

          {open && (
            <div
              style={{
                position: 'absolute',
                top: 'calc(100% + 6px)',
                right: 0,
                background: 'var(--surface)',
                border: '1px solid var(--border)',
                borderRadius: 8,
                boxShadow: '0 4px 16px rgba(0,0,0,0.12)',
                minWidth: 180,
                zIndex: 100,
                overflow: 'hidden',
              }}
            >
              {email && (
                <div
                  style={{
                    padding: '10px 14px 8px',
                    fontSize: 12,
                    color: 'var(--text-dim)',
                    borderBottom: '1px solid var(--border)',
                    wordBreak: 'break-all',
                  }}
                >
                  {email}
                </div>
              )}
              {isAdmin && (
                <button
                  onClick={() => {
                    setOpen(false)
                    navigate('/admin')
                  }}
                  style={{
                    display: 'block',
                    width: '100%',
                    padding: '9px 14px',
                    textAlign: 'left',
                    background: 'none',
                    border: 'none',
                    borderBottom: '1px solid var(--border)',
                    fontSize: 13,
                    color: 'var(--text)',
                    cursor: 'pointer',
                  }}
                  onMouseEnter={(e) =>
                    ((e.currentTarget as HTMLButtonElement).style.background = 'var(--surface-hover)')
                  }
                  onMouseLeave={(e) =>
                    ((e.currentTarget as HTMLButtonElement).style.background = 'none')
                  }
                >
                  Admin
                </button>
              )}
              <button
                onClick={handleLogout}
                style={{
                  display: 'block',
                  width: '100%',
                  padding: '9px 14px',
                  textAlign: 'left',
                  background: 'none',
                  border: 'none',
                  fontSize: 13,
                  color: '#e5534b',
                  cursor: 'pointer',
                }}
                onMouseEnter={(e) =>
                  ((e.currentTarget as HTMLButtonElement).style.background = 'var(--surface-hover)')
                }
                onMouseLeave={(e) =>
                  ((e.currentTarget as HTMLButtonElement).style.background = 'none')
                }
              >
                Log out
              </button>
            </div>
          )}
        </div>
      </div>
    </header>
  )
}
