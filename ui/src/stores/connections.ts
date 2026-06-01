import { create } from 'zustand'
import {
  api,
  type BundledIntegration,
  type CreateCustomApiRequest,
  type CreateCustomMcpRequest,
  type CustomApiIntegration,
  type CustomMcpIntegration,
  type InstalledIntegration,
  type UpdateCustomApiRequest,
} from '@/api/client'

interface ConnectionsState {
  integrations: BundledIntegration[]
  installed: InstalledIntegration[]
  customMcp: CustomMcpIntegration[]
  customApi: CustomApiIntegration[]
  loading: boolean
  fetchIntegrations: () => Promise<void>
  fetchInstalled: () => Promise<void>
  fetchCustomMcp: () => Promise<void>
  fetchCustomApi: () => Promise<void>
  install: (data: {
    integration_id: string
    auth_method: string
    token?: string
  }) => Promise<InstalledIntegration>
  remove: (integrationId: string) => Promise<void>
  createCustomMcp: (data: CreateCustomMcpRequest) => Promise<CustomMcpIntegration>
  removeCustomMcp: (id: string) => Promise<void>
  createCustomApi: (data: CreateCustomApiRequest) => Promise<CustomApiIntegration>
  updateCustomApi: (id: string, data: UpdateCustomApiRequest) => Promise<CustomApiIntegration>
  removeCustomApi: (id: string) => Promise<void>
}

export const useConnectionsStore = create<ConnectionsState>((set, get) => ({
  integrations: [],
  installed: [],
  customMcp: [],
  customApi: [],
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

  fetchCustomMcp: async () => {
    const customMcp = await api.customMcp.list()
    set({ customMcp })
  },

  fetchCustomApi: async () => {
    const customApi = await api.customApi.list()
    set({ customApi })
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

  createCustomMcp: async (data) => {
    const result = await api.customMcp.create(data)
    // Refresh both: the catalog now includes the new integration, and our
    // local custom list needs the row for delete actions.
    await Promise.all([get().fetchCustomMcp(), get().fetchIntegrations()])
    return result
  },

  removeCustomMcp: async (id) => {
    await api.customMcp.remove(id)
    await Promise.all([get().fetchCustomMcp(), get().fetchIntegrations()])
  },

  createCustomApi: async (data) => {
    const result = await api.customApi.create(data)
    await Promise.all([get().fetchCustomApi(), get().fetchIntegrations()])
    return result
  },

  updateCustomApi: async (id, data) => {
    const result = await api.customApi.update(id, data)
    await Promise.all([get().fetchCustomApi(), get().fetchIntegrations()])
    return result
  },

  removeCustomApi: async (id) => {
    await api.customApi.remove(id)
    await Promise.all([get().fetchCustomApi(), get().fetchIntegrations()])
  },
}))
