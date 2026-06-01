import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useLocation, useNavigate, useParams } from 'react-router-dom'
import { Plus } from 'lucide-react'
import {
  api,
  type ApiParam,
  type ApiToolDefinition,
  type CustomApiIntegration,
  type CustomApiTestResult,
} from '@/api/client'
import { ConnectionPanel } from '@/components/custom-api/ConnectionPanel'
import { IntegrationHeader } from '@/components/custom-api/IntegrationHeader'
import { TitleBlock } from '@/components/custom-api/TitleBlock'
import { ToolCard } from '@/components/custom-api/ToolCard'
import type { DraftParam, DraftTool, ParamLocation } from '@/components/custom-api/types'
import { useIsMobile } from '@/lib/useMediaQuery'
import { useConnectionsStore } from '@/stores/connections'

const PATH_PARAM_RE = /\{([a-zA-Z_][a-zA-Z0-9_]*)\}/g

function initialInstallToken(state: unknown): string {
  if (typeof state !== 'object' || state === null) return ''
  const token = (state as { installToken?: unknown }).installToken
  return typeof token === 'string' ? token : ''
}

function isNoAuthConfig(tokenHeader: string, tokenFormat: string): boolean {
  return !tokenHeader.trim() && !tokenFormat.trim()
}

export default function CustomApiBuilderPage() {
  const { integrationDbId } = useParams<{ integrationDbId: string }>()
  const navigate = useNavigate()
  const location = useLocation()
  const isMobile = useIsMobile()
  const installed = useConnectionsStore((s) => s.installed)
  const install = useConnectionsStore((s) => s.install)
  const updateCustomApi = useConnectionsStore((s) => s.updateCustomApi)
  const fetchInstalled = useConnectionsStore((s) => s.fetchInstalled)

  const [customIntegrationId, setCustomIntegrationId] = useState('')
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [baseUrl, setBaseUrl] = useState('')
  const [tokenHeader, setTokenHeader] = useState('Authorization')
  const [tokenFormat, setTokenFormat] = useState('Bearer {token}')
  const [testToken, setTestToken] = useState(() => initialInstallToken(location.state))
  const [tools, setTools] = useState<DraftTool[]>([])
  const [snapshot, setSnapshot] = useState('')
  const [loading, setLoading] = useState(true)
  const [installing, setInstalling] = useState(false)
  const [error, setError] = useState('')
  const lastAutosaveAttemptRef = useRef('')
  const saveQueueRef = useRef<Promise<void>>(Promise.resolve())

  const currentSnapshot = useMemo(
    () => stateSnapshot({ name, description, baseUrl, tokenHeader, tokenFormat, tools }),
    [name, description, baseUrl, tokenHeader, tokenFormat, tools],
  )
  const dirty = currentSnapshot !== snapshot
  const installedEntry = customIntegrationId
    ? installed.find((item) => item.integration_id === customIntegrationId)
    : undefined
  const needsInstall = !!customIntegrationId && !installedEntry

  useEffect(() => {
    if (!integrationDbId) return
    let cancelled = false
    setLoading(true)
    Promise.all([api.customApi.get(integrationDbId), fetchInstalled()])
      .then(([item]) => {
        if (cancelled) return
        const loadedTools = item.tools.length ? item.tools.map(toolToDraft) : [newTool(1)]
        setCustomIntegrationId(item.integration_id)
        setName(item.name)
        setDescription(item.description ?? '')
        setBaseUrl(item.base_url)
        setTokenHeader(item.token_header)
        setTokenFormat(item.token_format)
        setTools(loadedTools)
        setSnapshot(
          stateSnapshot({
            name: item.name,
            description: item.description ?? '',
            baseUrl: item.base_url,
            tokenHeader: item.token_header,
            tokenFormat: item.token_format,
            tools: loadedTools,
          }),
        )
      })
      .catch((err) => setError(err instanceof Error ? err.message : 'Failed to load custom API'))
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [fetchInstalled, integrationDbId])

  const applySavedCustomApi = useCallback(
    (saved: CustomApiIntegration) => {
      const loadedTools = saved.tools.length ? saved.tools.map(toolToDraft) : tools
      setCustomIntegrationId(saved.integration_id)
      setName(saved.name)
      setDescription(saved.description ?? '')
      setBaseUrl(saved.base_url)
      setTokenHeader(saved.token_header)
      setTokenFormat(saved.token_format)
      setTools(loadedTools)
      setSnapshot(
        stateSnapshot({
          name: saved.name,
          description: saved.description ?? '',
          baseUrl: saved.base_url,
          tokenHeader: saved.token_header,
          tokenFormat: saved.token_format,
          tools: loadedTools,
        }),
      )
    },
    [tools],
  )

  const saveCustomApi = useCallback(
    async ({
      applyResponse = true,
      reportError = true,
    }: {
      applyResponse?: boolean
      reportError?: boolean
    } = {}) => {
      if (!integrationDbId) return null
      const submittedSnapshot = currentSnapshot

      if (!name.trim()) {
        if (reportError) setError('Name is required')
        return null
      }
      if (!baseUrl.trim()) {
        if (reportError) setError('Base URL is required')
        return null
      }

      const payload = {
        name: name.trim(),
        description: description.trim() || null,
        base_url: baseUrl.trim(),
        token_header: tokenHeader.trim(),
        token_format: tokenFormat,
        tools: tools.map(apiToolFromDraft),
      }

      const run = async () => {
        const saved = await updateCustomApi(integrationDbId, payload)
        if (applyResponse) {
          applySavedCustomApi(saved)
        } else {
          setCustomIntegrationId(saved.integration_id)
          setSnapshot(submittedSnapshot)
        }
        lastAutosaveAttemptRef.current = ''
        return saved
      }

      const queued = saveQueueRef.current.catch(() => undefined).then(run)
      saveQueueRef.current = queued.then(
        () => undefined,
        () => undefined,
      )
      return queued
    },
    [
      applySavedCustomApi,
      baseUrl,
      currentSnapshot,
      description,
      integrationDbId,
      name,
      tokenFormat,
      tokenHeader,
      tools,
      updateCustomApi,
    ],
  )

  useEffect(() => {
    if (loading || !dirty || currentSnapshot === lastAutosaveAttemptRef.current) return
    const timer = window.setTimeout(() => {
      lastAutosaveAttemptRef.current = currentSnapshot
      void saveCustomApi({ applyResponse: false, reportError: false }).catch(() => {})
    }, 700)
    return () => window.clearTimeout(timer)
  }, [currentSnapshot, dirty, loading, saveCustomApi])

  async function handleBack() {
    if (dirty) {
      await saveCustomApi({ applyResponse: false, reportError: false }).catch(() => {})
    }
    navigate('/integrations')
  }

  async function handleInstall() {
    const installingWithToken = needsInstall && !isNoAuthConfig(tokenHeader, tokenFormat)
    if (installingWithToken && !testToken) {
      setError('Token is required to install this integration')
      return
    }

    setInstalling(true)
    setError('')
    try {
      const saved = await saveCustomApi()
      if (!saved) return

      if (needsInstall) {
        const authMethod = isNoAuthConfig(saved.token_header, saved.token_format) ? 'none' : 'token'
        await install({
          integration_id: saved.integration_id,
          auth_method: authMethod,
          token: authMethod === 'token' ? testToken : undefined,
        })
        setTestToken('')
        navigate(`/integrations/${encodeURIComponent(saved.integration_id)}`, { replace: true })
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save custom API')
    } finally {
      setInstalling(false)
    }
  }

  function updateTool(next: DraftTool) {
    setTools((items) =>
      items.map((item) => {
        if (item.id !== next.id) return item
        if (item.path !== next.path) return syncPathParams(next, next.path)
        return next
      }),
    )
  }

  function patchTool(toolId: string, update: Partial<DraftTool>) {
    setTools((items) => items.map((item) => (item.id === toolId ? { ...item, ...update } : item)))
  }

  async function runTool(tool: DraftTool) {
    const validationError = validateRunInput(tool, baseUrl, tokenHeader, tokenFormat)
    if (validationError) {
      setToolResult(tool.id, {
        content: [{ type: 'text', text: validationError }],
        isError: true,
        status_code: null,
        duration_ms: 0,
      })
      return
    }
    patchTool(tool.id, { running: true, result: undefined })
    const started = performance.now()
    try {
      const result = await api.customApi.test({
        base_url: baseUrl.trim(),
        token_header: tokenHeader.trim(),
        token_format: tokenFormat,
        token: testToken,
        integration_db_id: integrationDbId,
        tool: apiToolFromDraft(tool),
        args: sampleArgs(tool),
      })
      setToolResult(tool.id, result)
    } catch (err) {
      setToolResult(tool.id, {
        content: [{ type: 'text', text: err instanceof Error ? err.message : 'Test failed' }],
        isError: true,
        status_code: null,
        duration_ms: Math.round(performance.now() - started),
      })
    } finally {
      patchTool(tool.id, { running: false })
    }
  }

  function setToolResult(toolId: string, result: CustomApiTestResult) {
    setTools((items) => items.map((item) => (item.id === toolId ? { ...item, result } : item)))
  }

  if (loading) {
    return (
      <div
        style={{
          flex: 1,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          color: 'var(--text-faint)',
        }}
      >
        Loading...
      </div>
    )
  }

  return (
    <>
      <IntegrationHeader
        installing={installing}
        showInstall={needsInstall}
        error={error}
        onInstall={handleInstall}
        onBack={handleBack}
      />
      <div
        style={{
          flex: 1,
          overflow: 'auto',
          padding: isMobile ? '20px 14px 48px' : '32px 28px 64px',
        }}
      >
        <div
          style={{
            maxWidth: 880,
            margin: '0 auto',
            display: 'flex',
            flexDirection: 'column',
            gap: 24,
          }}
        >
          <TitleBlock
            name={name}
            description={description}
            onNameChange={setName}
            onDescriptionChange={setDescription}
          />

          <ConnectionPanel
            baseUrl={baseUrl}
            tokenHeader={tokenHeader}
            tokenFormat={tokenFormat}
            testToken={testToken}
            tokenLabel={needsInstall ? 'Token' : 'Override token'}
            tokenPlaceholder={
              needsInstall ? 'Paste token...' : 'Leave blank to use the installed token'
            }
            onBaseUrlChange={setBaseUrl}
            onTokenHeaderChange={setTokenHeader}
            onTokenFormatChange={setTokenFormat}
            onTestTokenChange={setTestToken}
          />

          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            <div
              style={{
                display: 'flex',
                alignItems: 'baseline',
                gap: 8,
                padding: '0 2px 0',
              }}
            >
              <span
                style={{
                  fontSize: 11,
                  fontWeight: 700,
                  color: 'var(--text-dim)',
                  textTransform: 'uppercase',
                  letterSpacing: 0.5,
                }}
              >
                Tools
              </span>
              <span
                style={{
                  fontSize: 12,
                  color: 'var(--text-faint)',
                  fontVariantNumeric: 'tabular-nums',
                }}
              >
                {tools.length}
              </span>
              <span style={{ flex: 1 }} />
              <span
                style={{
                  fontSize: 11,
                  color: 'var(--text-faint)',
                  fontStyle: 'italic',
                }}
              >
                each tool is one endpoint the agent can call
              </span>
            </div>

            {tools.map((tool) => {
              const pathParams = extractPathParams(tool.path)
              return (
                <ToolCard
                  key={tool.id}
                  tool={tool}
                  pathParams={pathParams}
                  requestPreview={requestPreview(baseUrl, tool)}
                  onChange={updateTool}
                  onRemove={() => setTools((items) => items.filter((item) => item.id !== tool.id))}
                  onRun={() => runTool(tool)}
                />
              )
            })}

            <button
              type="button"
              onClick={() => setTools((items) => [...items, newTool(items.length + 1)])}
              style={{
                alignSelf: 'stretch',
                height: 40,
                borderRadius: 8,
                border: '1px dashed var(--border-strong)',
                background: 'transparent',
                color: 'var(--text-dim)',
                display: 'inline-flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: 7,
                padding: '0 11px',
                cursor: 'pointer',
                fontFamily: 'inherit',
                fontSize: 12,
                fontWeight: 600,
              }}
            >
              <Plus size={14} />
              Add tool
            </button>
          </div>
        </div>
      </div>
    </>
  )
}

interface Snapshot {
  name: string
  description: string
  baseUrl: string
  tokenHeader: string
  tokenFormat: string
  tools: SnapshotTool[]
}

type SnapshotTool = Omit<DraftTool, 'id' | 'expanded' | 'running' | 'result'> & {
  params: SnapshotParam[]
}
type SnapshotParam = Omit<DraftParam, 'id' | 'sample'>

function stateSnapshot(data: Snapshot): string {
  return JSON.stringify({
    ...data,
    tools: data.tools.map((tool) => ({
      name: tool.name,
      description: tool.description,
      method: tool.method,
      path: tool.path,
      params: tool.params.map((param) => ({
        name: param.name,
        type: param.type,
        description: param.description,
        required: param.required,
        defaultValue: param.defaultValue,
        enumText: param.enumText,
        items: param.items,
        location: param.location,
        orphaned: param.orphaned,
      })),
    })),
  })
}

function newTool(index: number): DraftTool {
  return {
    id: crypto.randomUUID(),
    name: index === 1 ? 'get_item' : `tool_${index}`,
    description: '',
    method: 'GET',
    path: index === 1 ? '/v1/items/{id}' : '/',
    expanded: true,
    params:
      index === 1
        ? [
            {
              id: crypto.randomUUID(),
              name: 'id',
              type: 'string',
              description: '',
              required: true,
              defaultValue: '',
              enumText: '',
              items: '',
              location: 'path',
              sample: '123',
            },
          ]
        : [],
  }
}

function toolToDraft(tool: ApiToolDefinition): DraftTool {
  const pathParams = new Set(extractPathParams(tool.path))
  return {
    id: crypto.randomUUID(),
    name: tool.name,
    description: tool.description,
    method: tool.method,
    path: tool.path,
    expanded: true,
    params: (tool.params ?? []).map((param) => ({
      id: crypto.randomUUID(),
      name: param.name,
      type: param.type ?? 'string',
      description: param.description ?? '',
      required: !!param.required,
      defaultValue: param.default == null ? '' : String(param.default),
      enumText: param.enum?.join(', ') ?? '',
      items: param.items ?? '',
      location: pathParams.has(param.name) ? 'path' : param.query ? 'query' : 'body',
      sample: '',
    })),
  }
}

function apiToolFromDraft(tool: DraftTool): ApiToolDefinition {
  return {
    name: tool.name.trim(),
    description: tool.description.trim() || tool.name.trim(),
    method: tool.method,
    path: tool.path.trim() || '/',
    params: tool.params.map(apiParamFromDraft),
  }
}

function apiParamFromDraft(param: DraftParam): ApiParam {
  const result: ApiParam = {
    name: param.name.trim(),
    type: param.type,
    required: param.required,
    query: param.location === 'query',
  }
  if (param.description.trim()) result.description = param.description.trim()
  if (param.defaultValue.trim()) result.default = parseValue(param.defaultValue, param.type)
  const enumValues = param.enumText
    .split(',')
    .map((item) => item.trim())
    .filter(Boolean)
  if (enumValues.length) result.enum = enumValues
  if (param.type === 'array' && param.items.trim()) result.items = param.items.trim()
  return result
}

function validateRunInput(
  tool: DraftTool,
  baseUrl: string,
  tokenHeader: string,
  tokenFormat: string,
): string | null {
  if (!baseUrl.trim()) return 'Base URL is required.'
  const noAuth = !tokenHeader.trim() && !tokenFormat.trim()
  if (!noAuth) {
    if (!tokenHeader.trim()) return 'Token header is required.'
    if (!tokenFormat.includes('{token}')) return 'Token format must contain {token}.'
    // Token may be empty here — the server falls back to the installed token.
  }
  if (!tool.name.trim()) return 'Tool name is required.'
  if (!tool.path.trim().startsWith('/')) return 'Path must start with /.'
  return null
}

function syncPathParams(tool: DraftTool, path: string): DraftTool {
  const tokens = extractPathParams(path)
  const tokenSet = new Set(tokens)
  const existingNames = new Set(tool.params.map((param) => param.name))
  const params = tool.params.map((param) => {
    if (tokenSet.has(param.name))
      return { ...param, location: 'path' as ParamLocation, required: true, orphaned: false }
    if (param.location === 'path')
      return { ...param, location: 'body' as ParamLocation, orphaned: true }
    return param
  })
  for (const token of tokens) {
    if (!existingNames.has(token)) {
      params.push({
        id: crypto.randomUUID(),
        name: token,
        type: 'string',
        description: '',
        required: true,
        defaultValue: '',
        enumText: '',
        items: '',
        location: 'path',
        sample: '',
      })
    }
  }
  return { ...tool, path, params }
}

function extractPathParams(path: string): string[] {
  const params: string[] = []
  for (const match of path.matchAll(PATH_PARAM_RE)) {
    if (!params.includes(match[1])) params.push(match[1])
  }
  return params
}

function requestPreview(baseUrl: string, tool: DraftTool): string {
  const args = sampleArgs(tool)
  let path = tool.path || '/'
  for (const name of extractPathParams(path)) {
    const value = args[name]
    path = path.replace(`{${name}}`, encodeURIComponent(value == null ? name : String(value)))
  }
  const query = tool.params
    .filter((param) => param.location === 'query' && param.sample.trim())
    .map((param) => `${encodeURIComponent(param.name)}=${encodeURIComponent(param.sample)}`)
    .join('&')
  const base = baseUrl || 'https://api.example.com'
  return `-> ${tool.method} ${base.replace(/\/$/, '')}${path}${query ? `?${query}` : ''}`
}

function sampleArgs(tool: DraftTool): Record<string, unknown> {
  const args: Record<string, unknown> = {}
  for (const param of tool.params) {
    if (!param.sample.trim()) continue
    args[param.name] = parseValue(param.sample, param.type)
  }
  return args
}

function parseValue(value: string, type: string): unknown {
  if (type === 'integer') {
    const parsed = Number.parseInt(value, 10)
    return Number.isNaN(parsed) ? value : parsed
  }
  if (type === 'number') {
    const parsed = Number.parseFloat(value)
    return Number.isNaN(parsed) ? value : parsed
  }
  if (type === 'boolean') return value === 'true'
  if (type === 'array' || type === 'object') {
    try {
      return JSON.parse(value)
    } catch {
      return value
    }
  }
  return value
}
