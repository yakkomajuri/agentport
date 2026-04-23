import { useEffect, useRef, useState, type FormEvent } from 'react'
import { UserCog, Users } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { api, setToken } from '@/api/client'
import { useAuthStore } from '@/stores/auth'
import { IS_CLOUD } from '@/lib/env'
import { useIsMobile } from '@/lib/useMediaQuery'

interface WaitlistEntry {
  id: string
  email: string
  added_at: string
}

interface AdminUser {
  id: string
  email: string
  is_admin: boolean
  is_active: boolean
  created_at: string
}

type AdminTab = 'users' | 'waitlist'

export default function AdminPage() {
  const { email, isAdmin } = useAuthStore()
  const isMobile = useIsMobile()
  const [activeTab, setActiveTab] = useState<AdminTab>('users')

  if (!email) {
    return null
  }

  if (!isAdmin) {
    return (
      <>
        <AdminHeader isMobile={isMobile} />
        <div
          style={{
            flex: 1,
            overflowY: 'auto',
            padding: isMobile ? '20px 14px 40px' : '32px 40px',
          }}
        >
          <div style={{ ...panelStyle, maxWidth: 640 }}>
            <div style={panelTitleStyle}>You don't have access to this page</div>
            <div style={panelSubtitleStyle}>
              Admin privileges are required. Ask an instance admin to grant access.
            </div>
          </div>
        </div>
      </>
    )
  }

  const tabs: Array<{ id: AdminTab; label: string }> = [
    { id: 'users', label: 'Users' },
    ...(IS_CLOUD ? [{ id: 'waitlist' as const, label: 'Waitlist' }] : []),
  ]

  return (
    <>
      <AdminHeader isMobile={isMobile} />
      {tabs.length > 1 && (
        <div
          style={{
            display: 'flex',
            borderBottom: '1px solid var(--border)',
            padding: `0 ${isMobile ? 14 : 40}px`,
            overflowX: 'auto',
            WebkitOverflowScrolling: 'touch',
            flexShrink: 0,
          }}
        >
          {tabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              style={{
                background: 'none',
                border: 'none',
                padding: isMobile ? '10px 14px' : '10px 18px',
                borderBottom:
                  activeTab === tab.id ? '2px solid var(--accent)' : '2px solid transparent',
                marginBottom: -1,
                cursor: 'pointer',
                color: activeTab === tab.id ? 'var(--text)' : 'var(--text-faint)',
                fontSize: 13,
                fontWeight: activeTab === tab.id ? 500 : 400,
                transition: 'color 0.1s',
                whiteSpace: 'nowrap',
              }}
            >
              {tab.label}
            </button>
          ))}
        </div>
      )}
      <div
        style={{
          flex: 1,
          overflowY: 'auto',
          padding: isMobile ? '20px 14px 40px' : '32px 40px',
        }}
      >
        {activeTab === 'users' && <UsersSection currentEmail={email} />}
        {activeTab === 'waitlist' && IS_CLOUD && <WaitlistSection />}
      </div>
    </>
  )
}

function AdminHeader({ isMobile }: { isMobile: boolean }) {
  return (
    <div
      style={{
        height: 44,
        display: 'flex',
        alignItems: 'center',
        padding: `0 ${isMobile ? 14 : 20}px`,
        borderBottom: '1px solid var(--border)',
        background: 'var(--content-bg)',
        flexShrink: 0,
      }}
    >
      <span style={{ fontSize: 13, fontWeight: 500, color: 'var(--text)' }}>Admin</span>
    </div>
  )
}

function WaitlistSection() {
  const [enabled, setEnabled] = useState<boolean | null>(null)
  const [entries, setEntries] = useState<WaitlistEntry[]>([])
  const [entriesLoading, setEntriesLoading] = useState(true)
  const [newEmail, setNewEmail] = useState('')
  const [addError, setAddError] = useState('')
  const [adding, setAdding] = useState(false)
  const [toggleLoading, setToggleLoading] = useState(true)

  useEffect(() => {
    api.admin
      .getSettings()
      .then((s) => setEnabled(s.waitlist_enabled))
      .catch(() => setEnabled(false))
      .finally(() => setToggleLoading(false))

    api.admin
      .listWaitlist()
      .then(setEntries)
      .catch(() => setEntries([]))
      .finally(() => setEntriesLoading(false))
  }, [])

  async function onToggle() {
    if (enabled === null) return
    const next = !enabled
    setEnabled(next)
    try {
      await api.admin.updateSettings(next)
    } catch {
      setEnabled(!next)
    }
  }

  async function onAddEmail(e: FormEvent) {
    e.preventDefault()
    setAddError('')
    const trimmed = newEmail.trim()
    if (!trimmed) return
    setAdding(true)
    try {
      const entry = await api.admin.addWaitlistEmail(trimmed)
      setEntries((prev) => [entry, ...prev])
      setNewEmail('')
    } catch (err) {
      setAddError(err instanceof Error ? err.message : 'Failed to add email')
    } finally {
      setAdding(false)
    }
  }

  async function onRemove(id: string) {
    const prev = entries
    setEntries((current) => current.filter((e) => e.id !== id))
    try {
      await api.admin.removeWaitlistEmail(id)
    } catch {
      setEntries(prev)
    }
  }

  return (
    <>
      <SectionLabel>Waitlist</SectionLabel>
      <div style={panelStyle}>
        <div style={{ display: 'flex', alignItems: 'flex-start', gap: 12 }}>
          <div style={panelIconStyle}>
            <Users size={14} />
          </div>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={panelTitleRowStyle}>
              <div>
                <div style={panelTitleStyle}>Require approval for new signups</div>
                <div style={panelSubtitleStyle}>
                  Only emails on the waitlist below can create new accounts. Existing users are
                  unaffected.
                </div>
              </div>
              <Toggle
                checked={!!enabled}
                disabled={toggleLoading || enabled === null}
                onChange={onToggle}
              />
            </div>
          </div>
        </div>
      </div>

      {enabled && (
        <>
          <SectionLabel>Approved emails</SectionLabel>
          <div style={panelStyle}>
            <form onSubmit={onAddEmail} style={{ display: 'flex', gap: 8, alignItems: 'flex-end' }}>
              <div style={{ flex: 1 }}>
                <Label htmlFor="new-email" style={labelStyle}>
                  Email
                </Label>
                <Input
                  id="new-email"
                  type="email"
                  value={newEmail}
                  onChange={(e) => setNewEmail(e.target.value)}
                  placeholder="person@example.com"
                  required
                  style={inputStyle}
                />
              </div>
              <Button type="submit" size="sm" disabled={adding}>
                {adding ? 'Adding...' : 'Add'}
              </Button>
            </form>
            {addError && (
              <p style={{ fontSize: 12, color: 'var(--red)', marginTop: 10, marginBottom: 0 }}>
                {addError}
              </p>
            )}
          </div>

          <div style={{ ...panelStyle, padding: 0, overflow: 'hidden' }}>
            {entriesLoading && <div style={emptyStyle}>Loading…</div>}
            {!entriesLoading && entries.length === 0 && (
              <div style={emptyStyle}>
                No approved emails yet. Add one above to let them sign up.
              </div>
            )}
            {!entriesLoading &&
              entries.map((entry, idx) => (
                <div
                  key={entry.id}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    padding: '10px 14px',
                    borderTop: idx === 0 ? 'none' : '1px solid var(--border)',
                    gap: 12,
                  }}
                >
                  <div style={{ minWidth: 0, flex: 1 }}>
                    <div
                      style={{
                        fontSize: 13,
                        color: 'var(--text)',
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                        whiteSpace: 'nowrap',
                      }}
                    >
                      {entry.email}
                    </div>
                    <div style={{ fontSize: 11, color: 'var(--text-faint)', marginTop: 2 }}>
                      Added {new Date(entry.added_at).toLocaleDateString()}
                    </div>
                  </div>
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    onClick={() => onRemove(entry.id)}
                  >
                    Remove
                  </Button>
                </div>
              ))}
          </div>
        </>
      )}
    </>
  )
}

function UsersSection({ currentEmail }: { currentEmail: string }) {
  const [query, setQuery] = useState('')
  const [users, setUsers] = useState<AdminUser[]>([])
  const [loading, setLoading] = useState(true)
  const [impersonatingId, setImpersonatingId] = useState<string | null>(null)
  const [error, setError] = useState('')
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(() => {
      setLoading(true)
      api.admin
        .listUsers(query.trim() || undefined)
        .then(setUsers)
        .catch(() => setUsers([]))
        .finally(() => setLoading(false))
    }, 200)
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current)
    }
  }, [query])

  async function onImpersonate(userId: string) {
    setError('')
    setImpersonatingId(userId)
    try {
      const res = await api.admin.impersonate(userId)
      setToken(res.access_token)
      window.location.assign('/')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to impersonate user')
      setImpersonatingId(null)
    }
  }

  return (
    <>
      <SectionLabel>Users</SectionLabel>
      <div style={panelStyle}>
        <div style={{ display: 'flex', alignItems: 'flex-start', gap: 12, marginBottom: 14 }}>
          <div style={panelIconStyle}>
            <UserCog size={14} />
          </div>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={panelTitleStyle}>Impersonate a user</div>
            <div style={panelSubtitleStyle}>
              Click a user to sign in as them. A banner will mark the session and let you return to
              your admin account.
            </div>
          </div>
        </div>
        <Label htmlFor="user-search" style={labelStyle}>
          Search
        </Label>
        <Input
          id="user-search"
          type="search"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Email..."
          style={inputStyle}
        />
        {error && (
          <p style={{ fontSize: 12, color: 'var(--red)', marginTop: 10, marginBottom: 0 }}>
            {error}
          </p>
        )}
      </div>

      <div style={{ ...panelStyle, padding: 0, overflow: 'hidden' }}>
        {loading && <div style={emptyStyle}>Loading…</div>}
        {!loading && users.length === 0 && <div style={emptyStyle}>No users found.</div>}
        {!loading &&
          users.map((user, idx) => {
            const isSelf = user.email === currentEmail
            const busy = impersonatingId === user.id
            return (
              <div
                key={user.id}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  padding: '10px 14px',
                  borderTop: idx === 0 ? 'none' : '1px solid var(--border)',
                  gap: 12,
                }}
              >
                <div style={{ minWidth: 0, flex: 1 }}>
                  <div
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: 6,
                      minWidth: 0,
                    }}
                  >
                    <div
                      style={{
                        fontSize: 13,
                        color: 'var(--text)',
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                        whiteSpace: 'nowrap',
                      }}
                    >
                      {user.email}
                    </div>
                    {user.is_admin && <Badge>Admin</Badge>}
                    {!user.is_active && <Badge>Inactive</Badge>}
                  </div>
                  <div style={{ fontSize: 11, color: 'var(--text-faint)', marginTop: 2 }}>
                    Joined {new Date(user.created_at).toLocaleDateString()}
                  </div>
                </div>
                {!isSelf && user.is_active && (
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    onClick={() => onImpersonate(user.id)}
                    disabled={busy || impersonatingId !== null}
                  >
                    {busy ? 'Impersonating…' : 'Impersonate'}
                  </Button>
                )}
                {isSelf && <span style={{ fontSize: 11, color: 'var(--text-faint)' }}>You</span>}
              </div>
            )
          })}
      </div>
    </>
  )
}

function Badge({ children }: { children: React.ReactNode }) {
  return (
    <span
      style={{
        fontSize: 10,
        fontWeight: 500,
        color: 'var(--text-dim)',
        background: 'var(--surface)',
        border: '1px solid var(--border)',
        borderRadius: 4,
        padding: '1px 6px',
        textTransform: 'uppercase',
        letterSpacing: 0.4,
        flexShrink: 0,
      }}
    >
      {children}
    </span>
  )
}

function Toggle({
  checked,
  onChange,
  disabled,
}: {
  checked: boolean
  onChange: () => void
  disabled?: boolean
}) {
  return (
    <button
      role="switch"
      aria-checked={checked}
      onClick={onChange}
      disabled={disabled}
      style={{
        position: 'relative',
        width: 34,
        height: 20,
        borderRadius: 999,
        border: '1px solid var(--border)',
        background: checked ? 'var(--text-dim)' : 'var(--surface)',
        cursor: disabled ? 'default' : 'pointer',
        transition: 'background 150ms',
        flexShrink: 0,
        opacity: disabled ? 0.6 : 1,
        padding: 0,
      }}
    >
      <span
        style={{
          position: 'absolute',
          top: 1,
          left: checked ? 15 : 1,
          width: 16,
          height: 16,
          borderRadius: '50%',
          background: checked ? 'var(--content-bg)' : 'var(--text-faint)',
          transition: 'left 150ms, background 150ms',
        }}
      />
    </button>
  )
}

function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <div
      style={{
        fontSize: 10,
        fontWeight: 600,
        textTransform: 'uppercase',
        letterSpacing: 0.6,
        color: 'var(--text-faint)',
        marginBottom: 10,
      }}
    >
      {children}
    </div>
  )
}

const labelStyle: React.CSSProperties = {
  fontSize: 12,
  fontWeight: 500,
  color: 'var(--text-dim)',
  marginBottom: 6,
  display: 'block',
}

const inputStyle: React.CSSProperties = {
  background: 'var(--input-bg)',
  border: '1px solid var(--border)',
  color: 'var(--text)',
  fontSize: 13,
}

const panelStyle: React.CSSProperties = {
  padding: 16,
  border: '1px solid var(--border)',
  borderRadius: 10,
  background: 'var(--content-bg)',
  marginBottom: 32,
}

const panelIconStyle: React.CSSProperties = {
  width: 28,
  height: 28,
  borderRadius: 7,
  border: '1px solid var(--border)',
  background: 'var(--surface)',
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  color: 'var(--text-dim)',
  flexShrink: 0,
  marginTop: 1,
}

const panelTitleRowStyle: React.CSSProperties = {
  display: 'flex',
  alignItems: 'flex-start',
  justifyContent: 'space-between',
  gap: 16,
}

const panelTitleStyle: React.CSSProperties = {
  fontSize: 13,
  fontWeight: 600,
  color: 'var(--text)',
  letterSpacing: '-0.005em',
}

const panelSubtitleStyle: React.CSSProperties = {
  fontSize: 12,
  color: 'var(--text-faint)',
  marginTop: 3,
  lineHeight: 1.5,
}

const emptyStyle: React.CSSProperties = {
  padding: '20px 14px',
  fontSize: 12,
  color: 'var(--text-faint)',
  textAlign: 'center',
}
