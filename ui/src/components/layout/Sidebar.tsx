import { Link, useLocation } from 'react-router-dom'
import { CreditCard, FlaskConical, KeyRound, Puzzle, Settings, X } from 'lucide-react'
import { useThemeStore } from '../../stores/theme'

const navItems = [
  { to: '/integrations', label: 'Integrations', icon: Puzzle },
  { to: '/connect', label: 'Connect', icon: KeyRound },
  { to: '/playground', label: 'Playground', icon: FlaskConical },
]

const accountItems = [
  { to: '/settings', label: 'Settings', icon: Settings },
  { to: '/settings/billing', label: 'Billing', icon: CreditCard },
]

interface SidebarProps {
  mobile?: boolean
  onNavigate?: () => void
}

export function Sidebar({ mobile = false, onNavigate }: SidebarProps) {
  const { pathname } = useLocation()
  const { theme } = useThemeStore()

  return (
    <aside
      style={{
        width: mobile ? 'min(260px, 80vw)' : 180,
        height: '100dvh',
        background: 'var(--bg)',
        borderRight: '1px solid var(--border)',
        display: 'flex',
        flexDirection: 'column',
        flexShrink: 0,
      }}
    >
      {/* Logo row */}
      <div
        style={{
          height: 44,
          padding: '0 14px',
          borderBottom: '1px solid var(--border)',
          display: 'flex',
          alignItems: 'center',
        }}
      >
        <img
          src={
            theme === 'dark' ? '/logos/agentport-dark-mode.png' : '/logos/agentport-light-mode.png'
          }
          alt="AgentPort"
          style={{ height: 22, width: 'auto' }}
        />
        <span
          style={{
            fontFamily: "'Space Grotesk', sans-serif",
            fontWeight: 600,
            fontSize: 16,
            letterSpacing: 0.4,
            color: 'var(--text)',
            marginLeft: 8,
          }}
        >
          AgentPort
        </span>
        {mobile && (
          <button
            onClick={onNavigate}
            aria-label="Close menu"
            style={{
              marginLeft: 'auto',
              width: 28,
              height: 28,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              border: 'none',
              background: 'none',
              cursor: 'pointer',
              color: 'var(--text-dim)',
              borderRadius: 6,
            }}
          >
            <X size={16} />
          </button>
        )}
      </div>

      {/* Nav */}
      <nav
        style={{
          flex: 1,
          padding: '8px 6px',
          display: 'flex',
          flexDirection: 'column',
          gap: 1,
          overflowY: 'auto',
        }}
      >
        <div style={sectionLabelStyle}>Main</div>
        {navItems.map((item) => (
          <NavItem
            key={item.to}
            {...item}
            active={pathname === item.to}
            mobile={mobile}
            onNavigate={onNavigate}
          />
        ))}
        <div style={{ ...sectionLabelStyle, marginTop: 8 }}>Account</div>
        {accountItems.map((item) => (
          <NavItem
            key={item.to}
            {...item}
            active={pathname === item.to}
            mobile={mobile}
            onNavigate={onNavigate}
          />
        ))}
      </nav>
    </aside>
  )
}

const sectionLabelStyle: React.CSSProperties = {
  fontSize: 10,
  fontWeight: 600,
  textTransform: 'uppercase',
  letterSpacing: 0.6,
  color: 'var(--text-faint)',
  padding: '12px 8px 4px',
}

function navItemBase(mobile: boolean): React.CSSProperties {
  return {
    display: 'flex',
    alignItems: 'center',
    gap: mobile ? 10 : 8,
    padding: mobile ? '10px 10px' : '6px 8px',
    borderRadius: 5,
    fontSize: mobile ? 14 : 12,
    fontWeight: 400,
    color: 'var(--text-dim)',
    cursor: 'pointer',
    transition: 'background 150ms',
    textDecoration: 'none',
    border: 'none',
    background: 'none',
    width: '100%',
    textAlign: 'left',
  }
}

function NavItem({
  to,
  label,
  icon: Icon,
  active,
  mobile,
  onNavigate,
}: {
  to: string
  label: string
  icon: React.ComponentType<{ size?: number }>
  active: boolean
  mobile: boolean
  onNavigate?: () => void
}) {
  return (
    <Link
      to={to}
      onClick={onNavigate}
      style={{
        ...navItemBase(mobile),
        background: active ? 'var(--surface-hover)' : undefined,
        color: active ? 'var(--text)' : 'var(--text-dim)',
        fontWeight: active ? 500 : 400,
      }}
    >
      <Icon size={mobile ? 17 : 15} />
      {label}
    </Link>
  )
}
