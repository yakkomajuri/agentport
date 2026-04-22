import { useEffect, useState } from 'react'
import { Search } from 'lucide-react'
import { useConnectionsStore } from '@/stores/connections'
import { IntegrationCard } from '@/components/connections/IntegrationCard'
import { ConnectDialog } from '@/components/connections/ConnectDialog'
import { useIsMobile } from '@/lib/useMediaQuery'
import type { BundledIntegration } from '@/api/client'

export default function ConnectionsPage() {
  const { integrations, installed, fetchIntegrations, fetchInstalled } = useConnectionsStore()
  const [search, setSearch] = useState('')
  const [connectTarget, setConnectTarget] = useState<BundledIntegration | null>(null)
  const isMobile = useIsMobile()
  const gutter = isMobile ? 14 : 20

  useEffect(() => {
    fetchIntegrations()
    fetchInstalled()
  }, [])

  const connectedInstalledIds = new Set(
    installed.filter((i) => i.connected).map((i) => i.integration_id),
  )
  const q = search.toLowerCase()

  const connectedIntegrations = integrations.filter((i) => connectedInstalledIds.has(i.id))
  const notConnected = integrations.filter(
    (i) => !connectedInstalledIds.has(i.id) && i.name.toLowerCase().includes(q),
  )
  const browseIntegrations = notConnected.filter((i) => i.available !== false)
  const unavailableIntegrations = notConnected.filter((i) => i.available === false)

  return (
    <>
      {/* FilterBar */}
      <div
        style={{
          height: 44,
          display: 'flex',
          alignItems: 'center',
          padding: `0 ${gutter}px`,
          borderBottom: '1px solid var(--border)',
          background: 'var(--content-bg)',
          flexShrink: 0,
        }}
      >
        <span style={{ fontSize: 13, fontWeight: 500, color: 'var(--text)' }}>Integrations</span>
      </div>

      <div style={{ flex: 1, overflowY: 'auto' }}>
        {/* Connected */}
        {connectedIntegrations.length > 0 && (
          <div style={{ padding: `${gutter}px ${gutter}px 0` }}>
            <SectionLabel count={connectedIntegrations.length}>Connected</SectionLabel>
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: isMobile ? '1fr' : 'repeat(auto-fill, minmax(280px, 1fr))',
                gap: 8,
              }}
            >
              {connectedIntegrations.map((integ) => {
                return (
                  <IntegrationCard
                    key={integ.id}
                    integration={integ}
                    isInstalled
                    onConnect={() => {}}
                  />
                )
              })}
            </div>
          </div>
        )}

        {/* Divider */}
        {connectedIntegrations.length > 0 && (
          <div
            style={{ height: 1, background: 'var(--border)', margin: `${gutter}px ${gutter}px 0` }}
          />
        )}

        {/* Browse */}
        <div style={{ padding: `${gutter}px ${gutter}px ${gutter + 12}px` }}>
          <SectionLabel count={browseIntegrations.length}>Browse</SectionLabel>

          {/* Search */}
          <div
            style={{
              position: 'relative',
              display: 'flex',
              alignItems: 'center',
              marginBottom: 16,
              width: isMobile ? '100%' : 320,
            }}
          >
            <Search
              size={15}
              style={{
                position: 'absolute',
                left: 12,
                color: 'var(--text-faint)',
                pointerEvents: 'none',
              }}
            />
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search integrations..."
              style={{
                height: 36,
                padding: '0 12px 0 36px',
                border: '1px solid var(--border)',
                borderRadius: 8,
                background: 'var(--input-bg)',
                fontSize: 13,
                fontFamily: 'inherit',
                color: 'var(--text)',
                outline: 'none',
                width: '100%',
              }}
            />
          </div>

          {browseIntegrations.length > 0 ? (
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: isMobile ? '1fr' : 'repeat(auto-fill, minmax(280px, 1fr))',
                gap: 8,
              }}
            >
              {browseIntegrations.map((integ) => (
                <IntegrationCard
                  key={integ.id}
                  integration={integ}
                  isInstalled={false}
                  onConnect={() => setConnectTarget(integ)}
                />
              ))}
            </div>
          ) : (
            search && (
              <div style={{ fontSize: 13, color: 'var(--text-faint)', padding: '8px 0' }}>
                No integrations match &ldquo;{search}&rdquo;
              </div>
            )
          )}

          {unavailableIntegrations.length > 0 && (
            <div style={{ marginTop: 24 }}>
              <SectionLabel count={unavailableIntegrations.length}>Unavailable</SectionLabel>
              <div
                style={{
                  display: 'grid',
                  gridTemplateColumns: isMobile ? '1fr' : 'repeat(auto-fill, minmax(280px, 1fr))',
                  gap: 8,
                }}
              >
                {unavailableIntegrations.map((integ) => (
                  <IntegrationCard
                    key={integ.id}
                    integration={integ}
                    isInstalled={false}
                    onConnect={() => {}}
                  />
                ))}
              </div>
            </div>
          )}
        </div>

        {integrations.length === 0 && (
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              padding: 60,
              color: 'var(--text-faint)',
              fontSize: 13,
            }}
          >
            Loading integrations...
          </div>
        )}
      </div>

      <ConnectDialog
        integration={connectTarget}
        open={connectTarget !== null}
        onClose={() => setConnectTarget(null)}
      />
    </>
  )
}

function SectionLabel({ children, count }: { children: React.ReactNode; count: number }) {
  return (
    <div style={{ marginBottom: 12 }}>
      <span
        style={{
          fontSize: 10,
          fontWeight: 600,
          textTransform: 'uppercase',
          letterSpacing: 0.6,
          color: 'var(--text-faint)',
        }}
      >
        {children}
        <span style={{ fontWeight: 400 }}> &middot; {count}</span>
      </span>
    </div>
  )
}
