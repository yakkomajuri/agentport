import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Check, Info } from 'lucide-react'
import type { BundledIntegration } from '@/api/client'
import { LOGOS } from './logos'

interface Props {
  integration: BundledIntegration
  isInstalled: boolean
  onConnect: () => void
}

export function IntegrationCard({ integration, isInstalled, onConnect }: Props) {
  const navigate = useNavigate()
  const slug = integration.id
  const logo = LOGOS[integration.id]
  const unavailable = integration.available === false
  const [tooltipVisible, setTooltipVisible] = useState(false)

  return (
    <div
      onClick={() => !unavailable && navigate(`/integrations/${encodeURIComponent(slug)}`)}
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 14,
        padding: '14px 16px',
        border: '1px solid var(--border)',
        borderRadius: 8,
        background: 'var(--card-bg)',
        cursor: unavailable ? 'default' : 'pointer',
        boxShadow: 'var(--card-shadow)',
        transition: 'box-shadow 150ms, border-color 150ms',
      }}
      onMouseEnter={(e) => {
        if (unavailable) return
        e.currentTarget.style.boxShadow = 'var(--card-shadow-hover)'
        e.currentTarget.style.borderColor = 'var(--border-strong)'
      }}
      onMouseLeave={(e) => {
        if (unavailable) return
        e.currentTarget.style.boxShadow = 'var(--card-shadow)'
        e.currentTarget.style.borderColor = 'var(--border)'
      }}
    >
      <div
        style={{
          width: 40,
          height: 40,
          borderRadius: 8,
          border: '1px solid var(--border)',
          background: 'var(--surface)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          fontSize: 18,
          fontWeight: 600,
          flexShrink: 0,
          opacity: unavailable ? 0.4 : 1,
        }}
      >
        {logo ? (
          <img
            src={logo.src}
            alt={integration.name}
            style={{
              width: 22,
              height: 22,
              objectFit: 'contain',
              filter: logo.darkInvert ? 'var(--logo-invert-filter)' : undefined,
            }}
          />
        ) : (
          integration.name.charAt(0).toUpperCase()
        )}
      </div>
      <div style={{ flex: 1, minWidth: 0, opacity: unavailable ? 0.4 : 1 }}>
        <div style={{ fontSize: 15, fontWeight: 500, color: 'var(--text)' }}>
          {integration.name}
        </div>
      </div>
      <div
        style={{ flexShrink: 0 }}
        onClick={(e) => {
          e.stopPropagation()
          if (!unavailable && !isInstalled) onConnect()
        }}
      >
        {isInstalled ? (
          <span
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: 5,
              fontSize: 12,
              fontWeight: 500,
              color: 'var(--green-dim)',
            }}
          >
            <Check size={13} strokeWidth={2.5} />
            Connected
          </span>
        ) : unavailable ? (
          <div style={{ position: 'relative' }}>
            <button
              onMouseEnter={() => setTooltipVisible(true)}
              onMouseLeave={() => setTooltipVisible(false)}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                justifyContent: 'center',
                width: 30,
                height: 30,
                borderRadius: 6,
                background: 'var(--surface)',
                color: 'var(--text)',
                border: '1px solid var(--border-strong)',
                cursor: 'help',
              }}
            >
              <Info size={14} />
            </button>
            {tooltipVisible && integration.available_reason && (
              <div
                style={{
                  position: 'absolute',
                  right: 0,
                  bottom: 'calc(100% + 8px)',
                  width: 'min(300px, calc(100vw - 40px))',
                  padding: '10px 12px',
                  borderRadius: 6,
                  background: 'var(--card-bg)',
                  border: '1px solid var(--border-strong)',
                  boxShadow: '0 4px 16px rgba(0,0,0,0.2)',
                  fontSize: 11,
                  color: 'var(--text)',
                  lineHeight: 1.6,
                  zIndex: 10,
                  pointerEvents: 'none',
                  overflowWrap: 'break-word',
                  wordBreak: 'break-word',
                }}
              >
                {integration.available_reason}
              </div>
            )}
          </div>
        ) : (
          <button
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              padding: '0 14px',
              height: 30,
              borderRadius: 6,
              fontSize: 12,
              fontWeight: 500,
              background: 'transparent',
              color: 'var(--text-dim)',
              border: '1px solid var(--border)',
              cursor: 'pointer',
              transition: 'background 150ms, border-color 150ms, color 150ms',
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.background = 'var(--accent)'
              e.currentTarget.style.borderColor = 'var(--accent)'
              e.currentTarget.style.color = 'var(--content-bg)'
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.background = 'transparent'
              e.currentTarget.style.borderColor = 'var(--border)'
              e.currentTarget.style.color = 'var(--text-dim)'
            }}
          >
            Connect
          </button>
        )}
      </div>
    </div>
  )
}
