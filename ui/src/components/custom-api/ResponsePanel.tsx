import { ChevronDown } from 'lucide-react'
import { useEffect, useState } from 'react'
import type { CustomApiTestResult } from '@/api/client'

interface Props {
  result?: CustomApiTestResult
}

export function ResponsePanel({ result }: Props) {
  const [open, setOpen] = useState(false)
  useEffect(() => {
    if (result) setOpen(true)
  }, [result])

  if (!result) return null

  const text = result.content?.map((item) => item.text).join('\n') || ''
  const size = new Blob([text]).size
  const status = result.status_code ?? 'ERR'
  const family = statusFamily(status, result.isError)

  return (
    <div
      style={{
        borderTop: '1px solid var(--border)',
        background: 'var(--surface)',
      }}
    >
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        style={{
          width: '100%',
          height: 36,
          border: 'none',
          background: 'transparent',
          display: 'flex',
          alignItems: 'center',
          gap: 10,
          padding: '0 14px 0 18px',
          color: 'var(--text)',
          cursor: 'pointer',
          fontFamily: 'inherit',
          textAlign: 'left',
        }}
      >
        <span
          style={{
            fontSize: 10,
            fontWeight: 700,
            color: 'var(--text-dim)',
            textTransform: 'uppercase',
            letterSpacing: 0.5,
          }}
        >
          Response
        </span>
        <StatusPill status={status} family={family} />
        <Meta label="time">{result.duration_ms ?? 0} ms</Meta>
        <Meta label="size">{formatBytes(size)}</Meta>
        <span style={{ flex: 1 }} />
        <ChevronDown
          size={13}
          style={{
            color: 'var(--text-faint)',
            transform: open ? 'rotate(180deg)' : 'rotate(0deg)',
            transition: 'transform 120ms ease',
          }}
        />
      </button>
      {open && (
        <pre
          style={{
            margin: 0,
            maxHeight: 280,
            overflow: 'auto',
            borderTop: '1px solid var(--border)',
            background: 'var(--code-bg)',
            color: 'var(--code-text)',
            padding: '12px 16px',
            fontSize: 12,
            lineHeight: 1.55,
            fontFamily: 'var(--font-mono)',
            whiteSpace: 'pre-wrap',
            overflowWrap: 'anywhere',
          }}
        >
          {text || '(empty response)'}
        </pre>
      )}
    </div>
  )
}

type StatusFamily = 'success' | 'redirect' | 'client-error' | 'server-error' | 'error'

function statusFamily(status: number | string, isError: boolean): StatusFamily {
  if (isError && typeof status !== 'number') return 'error'
  if (typeof status === 'number') {
    if (status >= 500) return 'server-error'
    if (status >= 400) return 'client-error'
    if (status >= 300) return 'redirect'
    if (status >= 200) return 'success'
  }
  return 'error'
}

function StatusPill({ status, family }: { status: number | string; family: StatusFamily }) {
  const palette = familyPalette(family)
  return (
    <span
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: 5,
        height: 20,
        padding: '0 8px',
        borderRadius: 99,
        background: palette.bg,
        color: palette.text,
        fontFamily: 'var(--font-mono)',
        fontSize: 11,
        fontWeight: 700,
      }}
    >
      <span
        style={{
          width: 5,
          height: 5,
          borderRadius: '50%',
          background: palette.dot,
        }}
      />
      {status}
    </span>
  )
}

function familyPalette(family: StatusFamily) {
  if (family === 'success')
    return {
      bg: 'var(--badge-green-bg)',
      text: 'var(--badge-green-text)',
      dot: 'var(--badge-green-dot)',
    }
  if (family === 'redirect')
    return {
      bg: 'var(--badge-blue-bg)',
      text: 'var(--badge-blue-text)',
      dot: 'var(--badge-blue-dot)',
    }
  if (family === 'client-error')
    return {
      bg: 'var(--badge-amber-bg)',
      text: 'var(--badge-amber-text)',
      dot: 'var(--badge-amber-dot)',
    }
  return {
    bg: 'var(--badge-red-bg)',
    text: 'var(--badge-red-text)',
    dot: 'var(--badge-red-dot)',
  }
}

function Meta({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <span
      style={{
        display: 'inline-flex',
        alignItems: 'baseline',
        gap: 4,
        fontSize: 11,
        color: 'var(--text-dim)',
        fontFamily: 'var(--font-mono)',
        fontVariantNumeric: 'tabular-nums',
      }}
      title={label}
    >
      {children}
    </span>
  )
}

function formatBytes(size: number): string {
  if (size < 1024) return `${size} B`
  return `${(size / 1024).toFixed(1)} KB`
}
