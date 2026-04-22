import { useState, useEffect, type FormEvent } from 'react'
import { Trash2, Plus, Copy, Check } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { api, type ApiKey, type CreateApiKeyResponse } from '@/api/client'
import { useIsMobile } from '@/lib/useMediaQuery'

type TabId = 'claude-code' | 'cursor' | 'codex' | 'openclaw' | 'hermes'
type Lang = 'bash' | 'json' | 'toml' | 'text'

// ── Syntax tokenizer ──────────────────────────────────────────────────────────

type Token = { text: string; color?: string }

function tokenize(code: string, lang: Lang): Token[] {
  const tokens: Token[] = []

  if (lang === 'bash') {
    let first = true
    for (const part of code.split(/(\s+)/)) {
      if (/^\s+$/.test(part)) {
        tokens.push({ text: part })
      } else if (first) {
        tokens.push({ text: part, color: 'var(--syn-function)' })
        first = false
      } else if (part.startsWith('--')) {
        tokens.push({ text: part, color: 'var(--syn-constant)' })
      } else if (/^https?:\/\//.test(part)) {
        tokens.push({ text: part, color: 'var(--syn-string)' })
      } else {
        tokens.push({ text: part })
      }
    }
    return tokens
  }

  if (lang === 'json') {
    const re = /"[^"\\]*(?:\\.[^"\\]*)*"|[{}\[\],:]|\s+|[^"{}\[\],:\s]+/g
    for (const m of code.matchAll(re)) {
      const text = m[0]
      if (/^\s+$/.test(text)) {
        tokens.push({ text })
      } else if (text.startsWith('"')) {
        const after = code.slice(m.index! + text.length).match(/^(\s*)(.)/)
        if (after && after[2] === ':') {
          tokens.push({ text, color: 'var(--syn-constant)' })
        } else {
          tokens.push({ text, color: 'var(--syn-string)' })
        }
      } else if (/^[{}\[\],:]$/.test(text)) {
        tokens.push({ text, color: 'var(--text-faint)' })
      } else {
        tokens.push({ text })
      }
    }
    return tokens
  }

  if (lang === 'text') {
    return [{ text: code }]
  }

  // toml
  const lines = code.split('\n')
  lines.forEach((line, idx) => {
    if (line.startsWith('[')) {
      const m = line.match(/^(\[)([^\]]+)(\])(.*)$/)
      if (m) {
        tokens.push({ text: m[1], color: 'var(--text-faint)' })
        tokens.push({ text: m[2], color: 'var(--syn-variable)' })
        tokens.push({ text: m[3], color: 'var(--text-faint)' })
        if (m[4]) tokens.push({ text: m[4] })
      } else {
        tokens.push({ text: line, color: 'var(--syn-variable)' })
      }
    } else if (line.includes(' = ')) {
      const eqIdx = line.indexOf(' = ')
      tokens.push({ text: line.slice(0, eqIdx), color: 'var(--syn-tag)' })
      tokens.push({ text: ' = ', color: 'var(--text-faint)' })
      const val = line.slice(eqIdx + 3)
      tokens.push({
        text: val,
        color: val.startsWith('"') ? 'var(--syn-string)' : 'var(--syn-constant)',
      })
    } else {
      tokens.push({ text: line })
    }
    if (idx < lines.length - 1) tokens.push({ text: '\n' })
  })
  return tokens
}

// ── Brand icons ───────────────────────────────────────────────────────────────

function TabIcon({ src, size = 18 }: { src: string; size?: number }) {
  return (
    <img
      src={src}
      width={size}
      height={size}
      style={{ borderRadius: 4, display: 'block', objectFit: 'contain' }}
    />
  )
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function DeveloperPage() {
  const [keys, setKeys] = useState<ApiKey[]>([])
  const [newKeyName, setNewKeyName] = useState('')
  const [creating, setCreating] = useState(false)
  const [revealed, setRevealed] = useState<CreateApiKeyResponse | null>(null)
  const [copiedId, setCopiedId] = useState<string | null>(null)
  const [error, setError] = useState('')
  const [mcpCopied, setMcpCopied] = useState(false)
  const [activeTab, setActiveTab] = useState<TabId>('claude-code')
  const isMobile = useIsMobile()
  const isLocalhost =
    window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1'
  const mcpUrl = `${window.location.protocol}//${window.location.hostname}${isLocalhost ? ':4747' : ''}/mcp`

  useEffect(() => {
    api.apiKeys
      .list()
      .then(setKeys)
      .catch(() => {})
  }, [])

  async function onCreate(e: FormEvent) {
    e.preventDefault()
    if (!newKeyName.trim()) return
    setCreating(true)
    setError('')
    try {
      const res = await api.apiKeys.create(newKeyName.trim())
      setRevealed(res)
      setNewKeyName('')
      setKeys((prev) => [
        {
          id: res.id,
          name: res.name,
          key_prefix: res.key_prefix,
          created_at: res.created_at,
          last_used_at: null,
          is_active: true,
        },
        ...prev,
      ])
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create key')
    } finally {
      setCreating(false)
    }
  }

  async function onRevoke(id: string) {
    try {
      await api.apiKeys.revoke(id)
      setKeys((prev) => prev.filter((k) => k.id !== id))
      if (revealed?.id === id) setRevealed(null)
    } catch {
      // silent
    }
  }

  function copy(text: string, id: string) {
    navigator.clipboard.writeText(text)
    setCopiedId(id)
    setTimeout(() => setCopiedId(null), 2000)
  }

  function copyMcpUrl() {
    navigator.clipboard.writeText(mcpUrl)
    setMcpCopied(true)
    setTimeout(() => setMcpCopied(false), 2000)
  }

  const tabs: { id: TabId; label: string; logo: React.ReactNode }[] = [
    { id: 'claude-code', label: 'Claude Code', logo: <TabIcon src="/logos/claude.svg" /> },
    { id: 'cursor', label: 'Cursor', logo: <TabIcon src="/logos/cursor-app.png" /> },
    { id: 'codex', label: 'Codex', logo: <TabIcon src="/logos/codex.png" /> },
    { id: 'openclaw', label: 'OpenClaw', logo: <TabIcon src="/logos/openclaw.png" /> },
    {
      id: 'hermes',
      label: 'Hermes',
      logo: (
        <span
          style={{
            width: 22,
            height: 22,
            display: 'inline-flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontSize: 22,
            lineHeight: 1,
            color: '#c97b1b',
          }}
        >
          ☤
        </span>
      ),
    },
  ]

  type Step = { instruction: string; code: string; lang: Lang }
  const skillsStep: Step = {
    instruction: 'Then install the AgentPort skills:',
    code: 'npx skills add yakkomajuri/agentport-skills',
    lang: 'bash',
  }
  const autoApproveBlurb = (client: string) =>
    `Lastly, configure auto-approval for AgentPort tool calls. Since AgentPort gates approvals itself, you don't need ${client} to ask you permission to run commands.`
  const tabContent: Record<TabId, Step[]> = {
    'claude-code': [
      {
        instruction: 'Run in your terminal:',
        code: `claude mcp add agentport -s user --transport http ${mcpUrl}`,
        lang: 'bash',
      },
      skillsStep,
      {
        instruction: `${autoApproveBlurb('Claude Code')}\n\nAdd to \`~/.claude/settings.json\`:`,
        code: JSON.stringify({ permissions: { allow: ['mcp__agentport__*'] } }, null, 2),
        lang: 'json',
      },
      {
        instruction: 'Start a Claude Code session and run `/mcp` to go through the authentication flow.',
        code: '',
        lang: 'text',
      },
    ],
    cursor: [
      {
        instruction: 'Add to `~/.cursor/mcp.json`:',
        code: JSON.stringify({ mcpServers: { agentport: { url: mcpUrl } } }, null, 2),
        lang: 'json',
      },
      skillsStep,
      {
        instruction: `${autoApproveBlurb('Cursor')}\n\nEnable "Auto-run mode" in Cursor Settings → Chat.`,
        code: '',
        lang: 'text',
      },
    ],
    codex: [
      {
        instruction: 'Run in your terminal:',
        code: `codex mcp add agentport --url ${mcpUrl}`,
        lang: 'bash',
      },
      skillsStep,
      {
        instruction: `${autoApproveBlurb('Codex')}\n\nAdd to \`~/.codex/config.toml\`:`,
        code: `[mcp_servers.agentport]\ndefault_tools_approval_mode = "approve"`,
        lang: 'toml',
      },
    ],
    openclaw: [
      {
        instruction: 'Generate an API key in the API Keys section below. This API key is suitable for agents to have access to.',
        code: '',
        lang: 'text',
      },
      {
        instruction: 'Paste this prompt to OpenClaw:',
        code: `Let's install AgentPort for managing third-party integrations.\n\n1. Install the AgentPort CLI from npm with \`npm install -g agentport-cli\`\n2. Authenticate it by running \`ap auth login --api-key <your-api-key>\`\n3. Add the AgentPort skills from https://github.com/yakkomajuri/agentport-skills`,
        lang: 'text',
      },
    ],
    hermes: [
      {
        instruction: 'Generate an API key in the API Keys section below. This API key is suitable for agents to have access to.',
        code: '',
        lang: 'text',
      },
      {
        instruction: 'Paste this prompt to Hermes:',
        code: `Let's install AgentPort for managing third-party integrations.\n\n1. Install the AgentPort CLI from npm with \`npm install -g agentport-cli\`\n2. Authenticate it by running \`ap auth login --api-key <your-api-key>\`\n3. Add the AgentPort skills from https://github.com/yakkomajuri/agentport-skills`,
        lang: 'text',
      },
    ],
  }

  const currentSteps = tabContent[activeTab]

  return (
    <>
      <div
        style={{
          height: 44,
          display: 'flex',
          alignItems: 'center',
          padding: `0 ${isMobile ? 14 : 20}px`,
          borderBottom: '1px solid var(--border)',
          background: 'var(--content-bg)',
          flexShrink: 0,
        }}
      >
        <span style={{ fontSize: 13, fontWeight: 500, color: 'var(--text)' }}>Connect</span>
      </div>

      <div style={{ flex: 1, overflowY: 'auto', padding: isMobile ? '20px 14px' : '32px 40px' }}>
        {/* MCP Endpoint */}
        <SectionLabel>MCP Endpoint</SectionLabel>
        <div style={{ marginBottom: 28 }}>
          <Label style={labelStyle}>Your MCP server URL</Label>
          <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
            <Input
              value={mcpUrl}
              readOnly
              style={{
                flex: '1 1 240px',
                minWidth: 0,
                maxWidth: 480,
                background: 'var(--code-bg)',
                fontFamily: 'var(--font-mono)',
                fontSize: 12,
                color: 'var(--code-text)',
                border: '1px solid var(--border)',
              }}
            />
            <Button variant="outline" size="sm" onClick={copyMcpUrl}>
              {mcpCopied ? 'Copied!' : 'Copy'}
            </Button>
          </div>
          <p style={{ fontSize: 11, color: 'var(--text-faint)', marginTop: 6 }}>
            Point your MCP client at this URL to access all connected integrations as tools.
          </p>
        </div>

        <div style={{ height: 1, background: 'var(--border)', marginBottom: 28 }} />

        {/* Client Setup */}
        <SectionLabel>Client Setup</SectionLabel>
        <p style={{ fontSize: 12, color: 'var(--text-faint)', marginBottom: 16, marginTop: -4 }}>
          Add this server to your AI coding tool of choice.
        </p>

        {/* Tab bar */}
        <div
          style={{
            display: 'flex',
            borderBottom: '1px solid var(--border)',
            overflowX: 'auto',
            WebkitOverflowScrolling: 'touch',
          }}
        >
          {tabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 8,
                padding: isMobile ? '8px 14px' : '8px 18px',
                background: 'none',
                border: 'none',
                borderBottom:
                  activeTab === tab.id ? '2px solid var(--accent)' : '2px solid transparent',
                marginBottom: -1,
                cursor: 'pointer',
                color: activeTab === tab.id ? 'var(--text)' : 'var(--text-faint)',
                fontSize: 13,
                fontWeight: activeTab === tab.id ? 500 : 400,
                transition: 'color 0.1s',
                position: 'relative',
                zIndex: 1,
                whiteSpace: 'nowrap',
                flexShrink: 0,
              }}
            >
              {tab.logo}
              {tab.label}
            </button>
          ))}
        </div>

        {/* Tab content */}
        {currentSteps.map((step, idx) => {
          const stepId = `${activeTab}-${idx}`
          const isLast = idx === currentSteps.length - 1
          const stepNumber = (
            <span
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                justifyContent: 'center',
                width: 18,
                height: 18,
                borderRadius: '50%',
                background: 'var(--code-bg)',
                border: '1px solid var(--border)',
                color: 'var(--text-dim)',
                fontSize: 10,
                fontWeight: 600,
                fontFamily: 'var(--font-mono)',
                marginRight: 8,
                flexShrink: 0,
              }}
            >
              {idx + 1}
            </span>
          )
          const instructionRow = (
            <div
              style={{
                display: 'flex',
                alignItems: 'flex-start',
                fontSize: 13,
                lineHeight: 1.5,
                color: 'var(--text-dim)',
                margin: '12px 0 8px',
              }}
            >
              <span style={{ display: 'inline-flex', alignItems: 'center', height: 21 }}>
                {stepNumber}
              </span>
              <span style={{ whiteSpace: 'pre-line' }}>
                {step.instruction.split(/(`[^`]+`)/g).map((part, i) =>
                  part.startsWith('`') && part.endsWith('`') && part.length > 1 ? (
                    <code
                      key={i}
                      style={{
                        fontFamily: 'var(--font-mono)',
                        fontSize: 11.5,
                        background: 'var(--code-bg)',
                        border: '1px solid var(--border)',
                        borderRadius: 4,
                        padding: '1px 5px',
                        color: 'var(--code-text)',
                      }}
                    >
                      {part.slice(1, -1)}
                    </code>
                  ) : (
                    <span key={i}>{part}</span>
                  )
                )}
              </span>
            </div>
          )
          if (!step.code) {
            return (
              <div
                key={stepId}
                style={{ marginBottom: isLast ? 32 : 12 }}
              >
                {instructionRow}
              </div>
            )
          }
          return (
            <div key={stepId}>
              {instructionRow}
              <div
                style={{
                  border: '1px solid var(--border)',
                  borderRadius: 8,
                  background: 'var(--code-bg)',
                  padding: '16px 20px',
                  marginLeft: 26,
                  marginBottom: isLast ? 32 : 12,
                }}
              >
                <div style={{ position: 'relative' }}>
                  <pre
                    style={{
                      margin: 0,
                      fontFamily: 'var(--font-mono)',
                      fontSize: 12,
                      lineHeight: 1.7,
                      color: 'var(--code-text)',
                      whiteSpace: 'pre-wrap',
                      wordBreak: 'break-all',
                      paddingRight: 36,
                    }}
                  >
                    {tokenize(step.code, step.lang).map((tok, i) => (
                      <span key={i} style={tok.color ? { color: tok.color } : undefined}>
                        {tok.text}
                      </span>
                    ))}
                  </pre>
                  <button
                    onClick={() => copy(step.code, stepId)}
                    title="Copy"
                    style={{
                      position: 'absolute',
                      top: 0,
                      right: 0,
                      background: 'none',
                      border: 'none',
                      cursor: 'pointer',
                      color: copiedId === stepId ? 'var(--accent)' : 'var(--text-faint)',
                      padding: 4,
                      display: 'flex',
                      alignItems: 'center',
                      borderRadius: 4,
                    }}
                  >
                    {copiedId === stepId ? <Check size={14} /> : <Copy size={14} />}
                  </button>
                </div>
              </div>
            </div>
          )
        })}

        <div style={{ height: 1, background: 'var(--border)', marginBottom: 28 }} />

        {/* API Keys */}
        <SectionLabel>API Keys</SectionLabel>
        <p style={{ fontSize: 12, color: 'var(--text-faint)', marginBottom: 20, marginTop: -4 }}>
          API keys allow agents and the CLI to authenticate without a browser login. Keys can list
          and call tools, manage integrations, and start OAuth flows — but cannot approve requests
          or change tool settings.
        </p>

        {/* Revealed key banner */}
        {revealed && (
          <div
            style={{
              background: 'var(--code-bg)',
              border: '1px solid var(--border)',
              borderLeft: '3px solid var(--accent)',
              borderRadius: 6,
              padding: '12px 14px',
              marginBottom: 20,
            }}
          >
            <div
              style={{
                fontSize: 11,
                fontWeight: 600,
                color: 'var(--text-dim)',
                marginBottom: 8,
                textTransform: 'uppercase',
                letterSpacing: 0.5,
              }}
            >
              Save this key — it won't be shown again
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <code
                style={{
                  flex: 1,
                  fontFamily: 'var(--font-mono)',
                  fontSize: 12,
                  color: 'var(--text)',
                  wordBreak: 'break-all',
                }}
              >
                {revealed.plain_key}
              </code>
              <button
                onClick={() => copy(revealed.plain_key, 'revealed')}
                style={{
                  background: 'none',
                  border: 'none',
                  cursor: 'pointer',
                  color: copiedId === 'revealed' ? 'var(--accent)' : 'var(--text-faint)',
                  padding: 4,
                  display: 'flex',
                  alignItems: 'center',
                  flexShrink: 0,
                }}
              >
                {copiedId === 'revealed' ? <Check size={14} /> : <Copy size={14} />}
              </button>
            </div>
            <button
              onClick={() => setRevealed(null)}
              style={{
                marginTop: 10,
                background: 'none',
                border: 'none',
                cursor: 'pointer',
                fontSize: 11,
                color: 'var(--text-faint)',
                padding: 0,
              }}
            >
              I've saved it, dismiss
            </button>
          </div>
        )}

        {/* Create form */}
        <form
          onSubmit={onCreate}
          style={{
            display: 'flex',
            gap: 8,
            alignItems: 'flex-end',
            flexWrap: 'wrap',
            marginBottom: 24,
          }}
        >
          <div style={{ flex: '1 1 220px', minWidth: 0, maxWidth: 360 }}>
            <Label style={labelStyle}>Key name</Label>
            <Input
              value={newKeyName}
              onChange={(e) => setNewKeyName(e.target.value)}
              placeholder="e.g. cli-local, github-actions"
              style={inputStyle}
            />
          </div>
          <Button type="submit" disabled={creating || !newKeyName.trim()} size="sm">
            <Plus size={13} style={{ marginRight: 4 }} />
            {creating ? 'Creating…' : 'Create key'}
          </Button>
        </form>

        {error && (
          <p style={{ fontSize: 12, color: 'var(--red)', marginTop: -16, marginBottom: 16 }}>
            {error}
          </p>
        )}

        {/* Key list */}
        {keys.length === 0 ? (
          <div
            style={{
              padding: '24px 0',
              fontSize: 12,
              color: 'var(--text-faint)',
              borderTop: '1px solid var(--border)',
            }}
          >
            No API keys yet.
          </div>
        ) : (
          <div style={{ borderTop: '1px solid var(--border)' }}>
            {keys.map((key) => (
              <div
                key={key.id}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 12,
                  padding: '10px 0',
                  borderBottom: '1px solid var(--border)',
                }}
              >
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 13, color: 'var(--text)', fontWeight: 500 }}>
                    {key.name}
                  </div>
                  <div style={{ fontSize: 11, color: 'var(--text-faint)', marginTop: 2 }}>
                    <code
                      style={{
                        fontFamily: 'var(--font-mono)',
                        background: 'var(--code-bg)',
                        padding: '1px 5px',
                        borderRadius: 3,
                        fontSize: 10,
                      }}
                    >
                      {key.key_prefix}…
                    </code>
                    {key.last_used_at ? (
                      <span style={{ marginLeft: 8 }}>
                        Last used {new Date(key.last_used_at).toLocaleDateString()}
                      </span>
                    ) : (
                      <span style={{ marginLeft: 8 }}>Never used</span>
                    )}
                  </div>
                </div>
                <button
                  onClick={() => onRevoke(key.id)}
                  title="Revoke"
                  style={{
                    background: 'none',
                    border: 'none',
                    cursor: 'pointer',
                    color: 'var(--text-faint)',
                    padding: 4,
                    display: 'flex',
                    alignItems: 'center',
                    borderRadius: 4,
                  }}
                  onMouseEnter={(e) =>
                    ((e.currentTarget as HTMLButtonElement).style.color = 'var(--red)')
                  }
                  onMouseLeave={(e) =>
                    ((e.currentTarget as HTMLButtonElement).style.color = 'var(--text-faint)')
                  }
                >
                  <Trash2 size={14} />
                </button>
              </div>
            ))}
          </div>
        )}
      </div>
    </>
  )
}

function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <div
      style={{
        fontSize: 10,
        fontWeight: 600,
        textTransform: 'uppercase',
        letterSpacing: 0.6,
        color: 'var(--text-faint)',
        marginBottom: 10,
      }}
    >
      {children}
    </div>
  )
}

const labelStyle: React.CSSProperties = {
  fontSize: 12,
  fontWeight: 500,
  color: 'var(--text-dim)',
  marginBottom: 6,
  display: 'block',
}

const inputStyle: React.CSSProperties = {
  background: 'var(--input-bg)',
  border: '1px solid var(--border)',
  color: 'var(--text)',
  fontSize: 13,
}
