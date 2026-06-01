import type { CustomApiTestResult } from '@/api/client'

export type ParamLocation = 'path' | 'query' | 'body'

export interface DraftParam {
  id: string
  name: string
  type: string
  description: string
  required: boolean
  defaultValue: string
  enumText: string
  items: string
  location: ParamLocation
  sample: string
  orphaned?: boolean
}

export interface DraftTool {
  id: string
  name: string
  description: string
  method: string
  path: string
  params: DraftParam[]
  expanded: boolean
  running?: boolean
  result?: CustomApiTestResult
}
