import { BrowserRouter, Navigate, Route, Routes, useLocation } from 'react-router-dom'
import { useAuth, useAuthInit } from '@/hooks/useAuth'
import Login from '@/pages/Login'
import Dashboard from '@/pages/Dashboard'
import PersonsPage from '@/pages/persons/PersonsPage'
import PersonDetailPage from '@/pages/persons/PersonDetailPage'
import ApplicationsPage from '@/pages/applications/ApplicationsPage'
import ApplicationDetailPage from '@/pages/applications/ApplicationDetailPage'
import ApplicationFormPage from '@/pages/public/ApplicationFormPage'
import ChangePasswordPage from '@/pages/change-password/ChangePasswordPage'
import ComingSoon from '@/pages/ComingSoon'
import Forbidden from '@/pages/Forbidden'
import NotFound from '@/pages/NotFound'

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, isLoading, user } = useAuth()
  const location = useLocation()

  if (isLoading) {
    return (
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          height: '100vh',
        }}
      >
        <span className="loading-spinner lg" />
      </div>
    )
  }

  if (!isAuthenticated) return <Navigate to="/login" replace />

  // İlk girişte parola değiştirme zorunlu — /change-password dışındaki tüm route'ları engelle.
  if (user?.must_change_password && location.pathname !== '/change-password') {
    return <Navigate to="/change-password" replace />
  }

  return <>{children}</>
}

export default function App() {
  useAuthInit()

  return (
    <BrowserRouter>
      <Routes>
        {/* Public — kimlik doğrulama gerektirmez */}
        <Route path="/login" element={<Login />} />
        <Route path="/403" element={<Forbidden />} />
        <Route path="/basvuru" element={<ApplicationFormPage />} />

        {/* Zorunlu parola değiştirme — authenticated, AppShell yok */}
        <Route
          path="/change-password"
          element={
            <ProtectedRoute>
              <ChangePasswordPage />
            </ProtectedRoute>
          }
        />

        {/* Protected */}
        <Route
          path="/dashboard"
          element={
            <ProtectedRoute>
              <Dashboard />
            </ProtectedRoute>
          }
        />
        <Route
          path="/persons"
          element={
            <ProtectedRoute>
              <PersonsPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/persons/:id"
          element={
            <ProtectedRoute>
              <PersonDetailPage />
            </ProtectedRoute>
          }
        />
        {/* Üyelik Başvuruları */}
        <Route
          path="/admin/applications"
          element={
            <ProtectedRoute>
              <ApplicationsPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/admin/applications/:id"
          element={
            <ProtectedRoute>
              <ApplicationDetailPage />
            </ProtectedRoute>
          }
        />

        <Route
          path="/sporcular"
          element={
            <ProtectedRoute>
              <ComingSoon />
            </ProtectedRoute>
          }
        />
        <Route
          path="/veliler"
          element={
            <ProtectedRoute>
              <ComingSoon />
            </ProtectedRoute>
          }
        />
        <Route
          path="/uyeler"
          element={
            <ProtectedRoute>
              <ComingSoon />
            </ProtectedRoute>
          }
        />
        <Route
          path="/antrenorler"
          element={
            <ProtectedRoute>
              <ComingSoon />
            </ProtectedRoute>
          }
        />
        <Route
          path="/egitimler"
          element={
            <ProtectedRoute>
              <ComingSoon />
            </ProtectedRoute>
          }
        />
        <Route
          path="/gruplar"
          element={
            <ProtectedRoute>
              <ComingSoon />
            </ProtectedRoute>
          }
        />
        <Route
          path="/yoklama"
          element={
            <ProtectedRoute>
              <ComingSoon />
            </ProtectedRoute>
          }
        />
        <Route
          path="/tekneler"
          element={
            <ProtectedRoute>
              <ComingSoon />
            </ProtectedRoute>
          }
        />
        <Route
          path="/odemeler"
          element={
            <ProtectedRoute>
              <ComingSoon />
            </ProtectedRoute>
          }
        />
        <Route
          path="/raporlar"
          element={
            <ProtectedRoute>
              <ComingSoon />
            </ProtectedRoute>
          }
        />
        <Route
          path="/ayarlar"
          element={
            <ProtectedRoute>
              <ComingSoon />
            </ProtectedRoute>
          }
        />

        {/* Redirects */}
        <Route path="/" element={<Navigate to="/dashboard" replace />} />

        {/* 404 */}
        <Route
          path="*"
          element={
            <ProtectedRoute>
              <NotFound />
            </ProtectedRoute>
          }
        />
      </Routes>
    </BrowserRouter>
  )
}
