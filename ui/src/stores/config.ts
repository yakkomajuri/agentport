import { create } from 'zustand'
import { api } from '@/api/client'

interface ConfigState {
  isSelfHosted: boolean
  billingEnabled: boolean
  loaded: boolean
  fetch: () => Promise<void>
}

export const useConfigStore = create<ConfigState>((set, get) => ({
  isSelfHosted: false,
  billingEnabled: false,
  loaded: false,
  fetch: async () => {
    if (get().loaded) return
    try {
      const cfg = await api.config.get()
      set({
        isSelfHosted: cfg.is_self_hosted,
        billingEnabled: cfg.billing_enabled,
        loaded: true,
      })
    } catch {
      set({ loaded: true })
    }
  },
}))
