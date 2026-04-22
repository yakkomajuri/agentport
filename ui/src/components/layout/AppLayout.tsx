import { useEffect, useState } from 'react'
import { Navigate, Outlet, useLocation } from 'react-router-dom'
import { Sidebar } from './Sidebar'
import { Header } from './Header'
import { ImpersonationBanner } from './ImpersonationBanner'
import { useAuthStore } from '@/stores/auth'
import { useIsMobile } from '@/lib/useMediaQuery'

export function AppLayout() {
  const token = useAuthStore((s) => s.token)
  const isMobile = useIsMobile()
  const { pathname } = useLocation()
  const [drawerOpen, setDrawerOpen] = useState(false)

  // Close drawer when the route changes or when we grow out of mobile.
  useEffect(() => {
    setDrawerOpen(false)
  }, [pathname, isMobile])

  if (!token) return <Navigate to="/login" replace />

  return (
    <div
      style={{
        display: 'flex',
        height: '100dvh',
        overflow: 'hidden',
        position: 'relative',
      }}
    >
      {!isMobile && <Sidebar />}

      {isMobile && drawerOpen && (
        <>
          <div
            onClick={() => setDrawerOpen(false)}
            style={{
              position: 'fixed',
              inset: 0,
              background: 'rgba(0,0,0,0.4)',
              zIndex: 60,
            }}
          />
          <div
            style={{
              position: 'fixed',
              top: 0,
              left: 0,
              bottom: 0,
              zIndex: 61,
              display: 'flex',
              boxShadow: '0 10px 40px rgba(0,0,0,0.25)',
            }}
          >
            <Sidebar mobile onNavigate={() => setDrawerOpen(false)} />
          </div>
        </>
      )}

      <div
        style={{
          flex: 1,
          minWidth: 0,
          display: 'flex',
          flexDirection: 'column',
          overflow: 'hidden',
        }}
      >
        <Header onOpenDrawer={isMobile ? () => setDrawerOpen(true) : undefined} />
        <ImpersonationBanner />
        <main
          style={{
            flex: 1,
            background: 'var(--content-bg)',
            overflow: 'hidden',
            display: 'flex',
            flexDirection: 'column',
            minWidth: 0,
          }}
        >
          <Outlet />
        </main>
      </div>
    </div>
  )
}
