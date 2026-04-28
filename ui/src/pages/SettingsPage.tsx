import { useEffect, useState, type FormEvent } from 'react'
import { Clock, Key, ShieldCheck } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { api, type OrgSettingsResponse, type TotpStatusResponse } from '@/api/client'
import { TotpCodeDialog } from '@/components/totp/TotpCodeDialog'
import { TotpSetupDialog } from '@/components/totp/TotpSetupDialog'
import { useIsMobile } from '@/lib/useMediaQuery'

export default function SettingsPage() {
  const [currentPassword, setCurrentPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const [loading, setLoading] = useState(false)
  const isMobile = useIsMobile()

  async function onChangePassword(e: FormEvent) {
    e.preventDefault()
    setError('')
    setSuccess('')

    if (newPassword !== confirmPassword) {
      setError('New passwords do not match')
      return
    }
    if (newPassword.length < 6) {
      setError('New password must be at least 6 characters')
      return
    }

    setLoading(true)
    try {
      const res = await api.auth.changePassword(currentPassword, newPassword)
      setSuccess(res.message)
      setCurrentPassword('')
      setNewPassword('')
      setConfirmPassword('')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to change password')
    } finally {
      setLoading(false)
    }
  }

  return (
    <>
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
        <span style={{ fontSize: 13, fontWeight: 500, color: 'var(--text)' }}>Settings</span>
      </div>

      <div
        style={{
          flex: 1,
          overflowY: 'auto',
          padding: isMobile ? '20px 14px 40px' : '32px 40px',
          maxWidth: 640,
          width: '100%',
        }}
      >
        <SectionLabel>Approvals</SectionLabel>
        <ApprovalExpiryPanel />

        <SectionLabel>Security</SectionLabel>
        <TwoFactorPanel />

        {/* Change Password */}
        <SectionLabel>Change Password</SectionLabel>
        <form
          onSubmit={onChangePassword}
          style={{ display: 'flex', flexDirection: 'column', gap: 12, marginBottom: 32 }}
        >
          <div>
            <Label htmlFor="current-password" style={labelStyle}>
              Current password
            </Label>
            <Input
              id="current-password"
              type="password"
              value={currentPassword}
              onChange={(e) => setCurrentPassword(e.target.value)}
              required
              style={inputStyle}
            />
          </div>
          <div>
            <Label htmlFor="new-password" style={labelStyle}>
              New password
            </Label>
            <Input
              id="new-password"
              type="password"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              required
              minLength={6}
              style={inputStyle}
            />
          </div>
          <div>
            <Label htmlFor="confirm-password" style={labelStyle}>
              Confirm new password
            </Label>
            <Input
              id="confirm-password"
              type="password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              required
              minLength={6}
              style={inputStyle}
            />
          </div>

          {error && <p style={{ fontSize: 12, color: 'var(--red)', margin: 0 }}>{error}</p>}
          {success && (
            <p style={{ fontSize: 12, color: 'var(--green, #22c55e)', margin: 0 }}>{success}</p>
          )}

          <div>
            <Button type="submit" size="sm" disabled={loading}>
              {loading ? 'Changing...' : 'Change password'}
            </Button>
          </div>
        </form>

        {/* Danger Zone */}
        <SectionLabel>Danger Zone</SectionLabel>
        <div>
          <Button variant="destructive" size="sm">
            Delete Organization
          </Button>
        </div>
      </div>
    </>
  )
}

const MIN_EXPIRY_MINUTES = 1
const MAX_EXPIRY_MINUTES = 1440

function ApprovalExpiryPanel() {
  const [settings, setSettings] = useState<OrgSettingsResponse | null>(null)
  const [draft, setDraft] = useState('')
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')

  useEffect(() => {
    api.orgSettings
      .get()
      .then((s) => {
        setSettings(s)
        setDraft(String(s.approval_expiry_minutes))
      })
      .catch((e) => setError(e instanceof Error ? e.message : 'Could not load approval settings'))
      .finally(() => setLoading(false))
  }, [])

  async function save(value: number | null) {
    setError('')
    setSuccess('')
    setSaving(true)
    try {
      const next = await api.orgSettings.update(value)
      setSettings(next)
      setDraft(String(next.approval_expiry_minutes))
      setSuccess(value === null ? 'Reverted to default.' : 'Saved.')
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to save')
    } finally {
      setSaving(false)
    }
  }

  function onSubmit(e: FormEvent) {
    e.preventDefault()
    const n = Number(draft)
    if (!Number.isInteger(n) || n < MIN_EXPIRY_MINUTES || n > MAX_EXPIRY_MINUTES) {
      setError(`Enter a whole number between ${MIN_EXPIRY_MINUTES} and ${MAX_EXPIRY_MINUTES}.`)
      return
    }
    save(n)
  }

  const isOverridden = !!settings && settings.approval_expiry_minutes_override !== null
  const defaultMinutes = settings?.approval_expiry_minutes_default ?? null

  return (
    <div style={panelStyle}>
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: 12 }}>
        <div style={panelIconStyle}>
          <Clock size={14} />
        </div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={panelTitleRowStyle}>
            <div>
              <div style={panelTitleStyle}>Approval request expiration</div>
              <div style={panelSubtitleStyle}>
                How long a pending approval stays valid before it expires. Applies to new requests
                only.
              </div>
            </div>
          </div>

          {!loading && settings && (
            <form
              onSubmit={onSubmit}
              style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 12 }}
            >
              <Input
                type="number"
                min={MIN_EXPIRY_MINUTES}
                max={MAX_EXPIRY_MINUTES}
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                style={{ ...inputStyle, width: 100 }}
                disabled={saving}
              />
              <span style={{ fontSize: 12, color: 'var(--text-dim)' }}>minutes</span>
              <Button type="submit" size="sm" disabled={saving}>
                {saving ? 'Saving...' : 'Save'}
              </Button>
              {isOverridden && defaultMinutes !== null && (
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  onClick={() => save(null)}
                  disabled={saving}
                >
                  Reset to default ({defaultMinutes}m)
                </Button>
              )}
            </form>
          )}

          {!loading && settings && !isOverridden && defaultMinutes !== null && (
            <div style={inlineMetaStyle}>
              <span>Using instance default ({defaultMinutes} minutes).</span>
            </div>
          )}

          {error && <div style={{ fontSize: 12, color: 'var(--red)', marginTop: 10 }}>{error}</div>}
          {success && (
            <div style={{ fontSize: 12, color: 'var(--green, #22c55e)', marginTop: 10 }}>
              {success}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

function TwoFactorPanel() {
  const [status, setStatus] = useState<TotpStatusResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [setupOpen, setSetupOpen] = useState(false)
  const [toggleAction, setToggleAction] = useState<'disable' | 're-enable' | null>(null)

  useEffect(() => {
    api.totp
      .status()
      .then(setStatus)
      .catch((e) => {
        setStatus({ enabled: false, configured: false })
        setError(e instanceof Error ? e.message : 'Could not load two-factor settings')
      })
      .finally(() => setLoading(false))
  }, [])

  function onToggle() {
    if (!status) return
    setError('')
    if (status.enabled) {
      setToggleAction('disable')
      return
    }
    if (status.configured) {
      setToggleAction('re-enable')
      return
    }
    setSetupOpen(true)
  }

  async function onConfirmToggle(code: string) {
    if (!status || !toggleAction) return
    if (toggleAction === 'disable') {
      await api.totp.disable(code)
      setStatus({ enabled: false, configured: status.configured })
      return
    }
    const next = await api.totp.reEnable(code)
    setStatus(next)
  }

  return (
    <div style={panelStyle}>
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: 12 }}>
        <div style={panelIconStyle}>
          <ShieldCheck size={14} />
        </div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={panelTitleRowStyle}>
            <div>
              <div style={panelTitleStyle}>Enable one-time codes for extra security</div>
              <div style={panelSubtitleStyle}>
                Every approval asks for a 6-digit code from your authenticator app.
              </div>
            </div>
            <Toggle checked={!!status?.enabled} disabled={loading} onChange={onToggle} />
          </div>

          {!loading && status?.enabled && (
            <div style={inlineMetaStyle}>
              <span style={dotStyle('on')} />
              <span>
                {status.configured ? 'Active. Approvals will require a code.' : 'Active.'}
              </span>
            </div>
          )}

          {!loading && !status?.enabled && status?.configured && (
            <div style={inlineMetaStyle}>
              <Key size={12} style={{ color: 'var(--text-faint)' }} />
              <span>Authenticator is set up — toggle on to resume requiring codes.</span>
            </div>
          )}

          {error && <div style={{ fontSize: 12, color: 'var(--red)', marginTop: 10 }}>{error}</div>}
        </div>
      </div>

      <TotpSetupDialog
        open={setupOpen}
        onClose={() => setSetupOpen(false)}
        onEnabled={() => setStatus({ enabled: true, configured: true })}
      />
      <TotpCodeDialog
        open={toggleAction !== null}
        title={
          toggleAction === 'disable'
            ? 'Disable two-factor authentication'
            : 'Re-enable two-factor authentication'
        }
        description={
          toggleAction === 'disable'
            ? 'Enter a current authenticator code or recovery code before approvals stop requiring one-time codes.'
            : 'Enter a current authenticator code or recovery code before approvals start requiring one-time codes again.'
        }
        confirmLabel={toggleAction === 'disable' ? 'Disable' : 'Enable'}
        onClose={() => setToggleAction(null)}
        onSubmit={onConfirmToggle}
      />
    </div>
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

const inlineMetaStyle: React.CSSProperties = {
  display: 'inline-flex',
  alignItems: 'center',
  gap: 6,
  marginTop: 10,
  fontSize: 12,
  color: 'var(--text-dim)',
}

function dotStyle(state: 'on' | 'off'): React.CSSProperties {
  return {
    width: 6,
    height: 6,
    borderRadius: 3,
    background: state === 'on' ? 'var(--green, #22c55e)' : 'var(--text-faint)',
    display: 'inline-block',
  }
}
