import { create } from 'zustand'

const STORAGE_KEY = 'agent_port_email_verification'

export interface PendingEmailVerification {
  email: string
  verificationToken: string
  resendAvailableAt: string | null
  redirect: string | null
}

function readPendingVerification(): PendingEmailVerification | null {
  if (typeof window === 'undefined') return null

  const raw = window.sessionStorage.getItem(STORAGE_KEY)
  if (!raw) return null

  try {
    const parsed = JSON.parse(raw) as Partial<PendingEmailVerification>
    if (typeof parsed.email !== 'string' || typeof parsed.verificationToken !== 'string') {
      return null
    }

    return {
      email: parsed.email,
      verificationToken: parsed.verificationToken,
      resendAvailableAt:
        typeof parsed.resendAvailableAt === 'string' ? parsed.resendAvailableAt : null,
      redirect: typeof parsed.redirect === 'string' ? parsed.redirect : null,
    }
  } catch {
    return null
  }
}

function writePendingVerification(pending: PendingEmailVerification | null) {
  if (typeof window === 'undefined') return

  if (!pending) {
    window.sessionStorage.removeItem(STORAGE_KEY)
    return
  }

  window.sessionStorage.setItem(STORAGE_KEY, JSON.stringify(pending))
}

interface EmailVerificationState {
  pending: PendingEmailVerification | null
  startPendingVerification: (pending: PendingEmailVerification) => void
  updateResendAvailableAt: (resendAvailableAt: string | null) => void
  clearPendingVerification: () => void
}

export const useEmailVerificationStore = create<EmailVerificationState>((set) => ({
  pending: readPendingVerification(),
  startPendingVerification: (pending) => {
    writePendingVerification(pending)
    set({ pending })
  },
  updateResendAvailableAt: (resendAvailableAt) =>
    set((state) => {
      if (!state.pending) return {}
      const pending = { ...state.pending, resendAvailableAt }
      writePendingVerification(pending)
      return { pending }
    }),
  clearPendingVerification: () => {
    writePendingVerification(null)
    set({ pending: null })
  },
}))
