import { ArrowRight } from 'lucide-react'

interface Props {
  preview: string
}

export function RequestPreview({ preview }: Props) {
  const trimmed = preview.startsWith('-> ') ? preview.slice(3) : preview

  return (
    <div
      style={{
        padding: '0 18px 12px',
      }}
    >
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 8,
          padding: '8px 12px',
          borderRadius: 6,
          background: 'var(--code-bg)',
          color: 'var(--syn-comment)',
          fontFamily: 'var(--font-mono)',
          fontSize: 12,
          lineHeight: 1.4,
          minWidth: 0,
          overflow: 'hidden',
        }}
      >
        <ArrowRight size={12} style={{ flexShrink: 0, color: 'var(--text-faint)' }} />
        <span
          style={{
            color: 'var(--code-text)',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
            minWidth: 0,
          }}
        >
          {trimmed}
        </span>
      </div>
    </div>
  )
}
