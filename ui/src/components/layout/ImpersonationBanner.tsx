import { useState } from 'react'
import { api } from '@/api/client'
import { useAuthStore } from '@/stores/auth'

export function ImpersonationBanner() {
  const email = useAuthStore((s) => s.email)
  const impersonatorEmail = useAuthStore((s) => s.impersonatorEmail)
  const setAuth = useAuthStore((s) => s.setAuth)
  const [returning, setReturning] = useState(false)

  if (!impersonatorEmail) return null

  const handleReturn = async () => {
    setReturning(true)
    try {
      const res = await api.admin.stopImpersonation()
      setAuth(res.access_token)
      window.location.assign('/admin')
    } catch {
      setReturning(false)
    }
  }

  return (
    <div
      style={{
        flexShrink: 0,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        gap: 12,
        padding: '8px 16px',
        background: '#b45309',
        color: '#fff',
        fontSize: 12,
        fontWeight: 500,
        borderBottom: '1px solid rgba(0,0,0,0.15)',
      }}
    >
      <div
        style={{ minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}
      >
        Impersonating <strong>{email}</strong> — signed in as {impersonatorEmail}
      </div>
      <button
        type="button"
        onClick={handleReturn}
        disabled={returning}
        style={{
          flexShrink: 0,
          background: 'rgba(255,255,255,0.15)',
          color: '#fff',
          border: '1px solid rgba(255,255,255,0.35)',
          borderRadius: 6,
          padding: '4px 10px',
          fontSize: 12,
          fontWeight: 500,
          cursor: returning ? 'not-allowed' : 'pointer',
          opacity: returning ? 0.6 : 1,
        }}
      >
        {returning ? 'Returning…' : 'Return to admin'}
      </button>
    </div>
  )
}
