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
  patchToolRuleCounts: (toolName: string, total: number, enabled: number) => void
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

  patchToolRuleCounts: (toolName, total, enabled) =>
    set((state) => ({
      tools: state.tools.map((t) =>
        t.name === toolName
          ? {
              ...t,
              policy_rule_count: total,
              policy_enabled_rule_count: enabled,
              policy_display_mode: enabled > 0 ? 'conditional' : 'default_only',
            }
          : t,
      ),
    })),

  clear: () => set({ tools: [], loading: false, error: null }),
}))
