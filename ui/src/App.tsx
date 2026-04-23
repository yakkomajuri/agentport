import { lazy, Suspense, useEffect } from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { AppLayout } from '@/components/layout/AppLayout'
import { useConfigStore } from '@/stores/config'

const LoginPage = lazy(() => import('@/pages/LoginPage'))
const SignupPage = lazy(() => import('@/pages/SignupPage'))
const ForgotPasswordPage = lazy(() => import('@/pages/ForgotPasswordPage'))
const ResetPasswordPage = lazy(() => import('@/pages/ResetPasswordPage'))
const VerifyEmailPage = lazy(() => import('@/pages/VerifyEmailPage'))
const GoogleCallbackPage = lazy(() => import('@/pages/GoogleCallbackPage'))
const ConnectionsPage = lazy(() => import('@/pages/ConnectionsPage'))
const ConnectionDetailPage = lazy(() => import('@/pages/ConnectionDetailPage'))
const DeveloperPage = lazy(() => import('@/pages/DeveloperPage'))
const SettingsPage = lazy(() => import('@/pages/SettingsPage'))
const BillingPage = lazy(() => import('@/pages/BillingPage'))
const AdminPage = lazy(() => import('@/pages/AdminPage'))
const ApprovePage = lazy(() => import('@/pages/ApprovePage'))
const OAuthConsentPage = lazy(() => import('@/pages/OAuthConsentPage'))
const OAuthSuccessPage = lazy(() => import('@/pages/OAuthSuccessPage'))
const PlaygroundPage = lazy(() => import('@/pages/PlaygroundPage'))

export default function App() {
  const isSelfHosted = useConfigStore((s) => s.isSelfHosted)
  const fetchConfig = useConfigStore((s) => s.fetch)

  useEffect(() => {
    fetchConfig()
  }, [fetchConfig])

  return (
    <BrowserRouter>
      <Suspense
        fallback={
          <div
            style={{
              height: '100vh',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: 'var(--text-faint)',
              fontSize: 13,
            }}
          >
            Loading...
          </div>
        }
      >
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/signup" element={<SignupPage />} />
          <Route path="/forgot-password" element={<ForgotPasswordPage />} />
          <Route path="/reset-password" element={<ResetPasswordPage />} />
          <Route path="/verify-email" element={<VerifyEmailPage />} />
          <Route path="/login/google/callback" element={<GoogleCallbackPage />} />
          <Route path="/approve/:id" element={<ApprovePage />} />
          <Route path="/oauth/authorize" element={<OAuthConsentPage />} />
          <Route path="/oauth/success" element={<OAuthSuccessPage />} />
          <Route element={<AppLayout />}>
            <Route path="/integrations" element={<ConnectionsPage />} />
            <Route path="/integrations/:integrationId" element={<ConnectionDetailPage />} />
            <Route path="/connect" element={<DeveloperPage />} />
            <Route path="/settings" element={<SettingsPage />} />
            {!isSelfHosted && <Route path="/settings/billing" element={<BillingPage />} />}
            <Route path="/admin" element={<AdminPage />} />
            <Route path="/playground" element={<PlaygroundPage />} />
          </Route>
          <Route path="*" element={<Navigate to="/integrations" replace />} />
        </Routes>
      </Suspense>
    </BrowserRouter>
  )
}
