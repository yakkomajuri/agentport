import { create } from 'zustand'
import { api, type LogEntry } from '@/api/client'

interface LogsState {
  entries: LogEntry[]
  loading: boolean
  fetch: (params?: {
    integration?: string
    tool?: string
    limit?: number
    offset?: number
  }) => Promise<void>
}

export const useLogsStore = create<LogsState>((set) => ({
  entries: [],
  loading: false,

  fetch: async (params) => {
    set({ loading: true })
    try {
      const entries = await api.logs.list({ limit: 100, ...params })
      set({ entries })
    } finally {
      set({ loading: false })
    }
  },
}))
