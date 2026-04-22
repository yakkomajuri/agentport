import { create } from 'zustand'
import { api, type BundledIntegration, type InstalledIntegration } from '@/api/client'

interface ConnectionsState {
  integrations: BundledIntegration[]
  installed: InstalledIntegration[]
  loading: boolean
  fetchIntegrations: () => Promise<void>
  fetchInstalled: () => Promise<void>
  install: (data: {
    integration_id: string
    auth_method: string
    token?: string
  }) => Promise<InstalledIntegration>
  remove: (integrationId: string) => Promise<void>
}

export const useConnectionsStore = create<ConnectionsState>((set, get) => ({
  integrations: [],
  installed: [],
  loading: false,

  fetchIntegrations: async () => {
    const integrations = await api.integrations.list()
    set({ integrations })
  },

  fetchInstalled: async () => {
    set({ loading: true })
    try {
      const installed = await api.installed.list()
      set({ installed })
    } finally {
      set({ loading: false })
    }
  },

  install: async (data) => {
    const result = await api.installed.create(data)
    await get().fetchInstalled()
    return result
  },

  remove: async (integrationId) => {
    await api.installed.remove(integrationId)
    await get().fetchInstalled()
  },
}))
