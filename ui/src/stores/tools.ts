import { create } from 'zustand'
import { api, type Tool } from '@/api/client'

interface ToolsState {
  tools: Tool[]
  allTools: Tool[]
  loading: boolean
  allLoading: boolean
  error: string | null
  fetchForIntegration: (integrationId: string) => Promise<void>
  fetchAll: () => Promise<void>
  patchToolMode: (toolName: string, mode: string) => void
  clear: () => void
}

export const useToolsStore = create<ToolsState>((set) => ({
  tools: [],
  allTools: [],
  loading: false,
  allLoading: false,
  error: null,

  fetchForIntegration: async (integrationId) => {
    set({ loading: true, tools: [], error: null })
    try {
      const tools = await api.tools.listForIntegration(integrationId)
      set({ tools, error: null })
    } catch (error) {
      set({
        error: error instanceof Error ? error.message : 'Failed to load tools',
      })
    } finally {
      set({ loading: false })
    }
  },

  fetchAll: async () => {
    set({ allLoading: true })
    try {
      const allTools = await api.tools.listAll()
      set({ allTools })
    } finally {
      set({ allLoading: false })
    }
  },

  patchToolMode: (toolName, mode) =>
    set((state) => ({
      tools: state.tools.map((t) => (t.name === toolName ? { ...t, execution_mode: mode } : t)),
    })),

  clear: () => set({ tools: [], loading: false, error: null }),
}))
