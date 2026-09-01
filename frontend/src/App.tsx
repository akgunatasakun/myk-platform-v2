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
import AkademiPage from '@/pages/akademi/AkademiPage'
import ProgramPage from '@/pages/akademi/ProgramPage'
import LessonPage from '@/pages/akademi/LessonPage'
import EquipmentPage from '@/pages/equipment/EquipmentPage'
import EquipmentDetailPage from '@/pages/equipment/EquipmentDetailPage'
import TrainingPage from '@/pages/training/TrainingPage'
import TrainingDetailPage from '@/pages/training/TrainingDetailPage'
import AttendancePage from '@/pages/training/AttendancePage'
import SelfCheckinPage from '@/pages/training/SelfCheckinPage'
import PaymentsPage from '@/pages/payments/PaymentsPage'
import ReportsPage from '@/pages/payments/ReportsPage'
import AthletesPage from '@/pages/athletes/AthletesPage'
import AthleteDetailPage from '@/pages/athletes/AthleteDetailPage'
import GuardiansPage from '@/pages/guardians/GuardiansPage'
import GuardianDetailPage from '@/pages/guardians/GuardianDetailPage'
import MembersPage from '@/pages/members/MembersPage'
import MemberDetailPage from '@/pages/members/MemberDetailPage'
import CoachesPage from '@/pages/coaches/CoachesPage'
import CoachDetailPage from '@/pages/coaches/CoachDetailPage'
import SettingsPage from '@/pages/settings/SettingsPage'
import NotificationsPage from '@/pages/notifications/NotificationsPage'
import CalendarPage from '@/pages/calendar/CalendarPage'
import DocumentsPage from '@/pages/documents/DocumentsPage'
import DocumentDetailPage from '@/pages/documents/DocumentDetailPage'
import KutuphanePage from '@/pages/kutuphane/KutuphanePage'
import UsersPage from '@/pages/users/UsersPage'
import AuditPage from '@/pages/audit/AuditPage'
import Forbidden from '@/pages/Forbidden'
import NotFound from '@/pages/NotFound'

// Rol grupları — AppShell ile senkron
const ADMIN       = ['super_admin', 'kulup_yonetici']
const MANAGEMENT  = [...ADMIN, 'baskan', 'yk_uyesi']
const SECRETARIAT = [...MANAGEMENT, 'genel_sekreter', 'muhasebe']
const STAFF       = [...SECRETARIAT, 'sportif_direktor', 'basantrenor', 'antrenor',
                      'personel', 'saglik_sorumlusu', 'guvenlik_operasyon']
const COACHES     = [...MANAGEMENT, 'sportif_direktor', 'basantrenor', 'antrenor', 'genel_sekreter']

// Route bazlı izin haritası — sadece kısıtlı rotalar (undefined = herkes)
const ROUTE_ROLES: Record<string, string[]> = {
  '/admin/applications':  SECRETARIAT,
  '/admin/applications/': SECRETARIAT,
  '/persons':             STAFF,
  '/persons/':            STAFF,
  '/users':               [...MANAGEMENT, 'genel_sekreter'],
  '/audit':               ADMIN,
  '/sporcular':           [...STAFF, 'sporcu'],
  '/sporcular/':          [...STAFF, 'sporcu'],
  '/veliler':             [...SECRETARIAT, 'veli'],
  '/veliler/':            [...SECRETARIAT, 'veli'],
  '/uyeler':              [...SECRETARIAT, 'uye'],
  '/uyeler/':             [...SECRETARIAT, 'uye'],
  '/antrenorler':         [...SECRETARIAT, 'basantrenor', 'antrenor'],
  '/antrenorler/':        [...SECRETARIAT, 'basantrenor', 'antrenor'],
  '/akademi':             [...STAFF, 'sporcu', 'veli'],
  '/akademi/':            [...STAFF, 'sporcu', 'veli'],
  '/egitimler':           [...STAFF, 'sporcu', 'veli'],
  '/egitimler/':          [...STAFF, 'sporcu', 'veli'],
  '/yoklama':             COACHES,
  '/katilim':             ['sporcu'],
  '/tekneler':            STAFF,
  '/tekneler/':           STAFF,
  '/odemeler':            [...SECRETARIAT, 'sporcu', 'veli', 'uye'],
  '/raporlar':            SECRETARIAT,
  '/takvim':              [...STAFF, 'sporcu', 'veli', 'uye'],
  '/kutuphane':           [...MANAGEMENT, 'sportif_direktor', 'basantrenor', 'antrenor', 'genel_sekreter'],
  '/ayarlar':             ADMIN,
}

function isRouteAllowed(pathname: string, role: string): boolean {
  // Tam eşleşme veya prefix eşleşmesi
  const matched = Object.entries(ROUTE_ROLES).find(([prefix]) =>
    pathname === prefix || pathname.startsWith(prefix.endsWith('/') ? prefix : prefix + '/')
  )
  if (!matched) return true  // Haritada yok → herkese açık
  return matched[1].includes(role)
}

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, isLoading, user } = useAuth()
  const location = useLocation()

  if (isLoading) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100vh' }}>
        <span className="loading-spinner lg" />
      </div>
    )
  }

  if (!isAuthenticated) return <Navigate to="/login" replace />

  // İlk girişte parola değiştirme zorunlu
  if (user?.must_change_password && location.pathname !== '/change-password') {
    return <Navigate to="/change-password" replace />
  }

  // Phase 2: route guard — yetkisiz rol URL ile bile giremez
  if (user?.role && !isRouteAllowed(location.pathname, user.role)) {
    return <Navigate to="/403" replace />
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
        {/* Sprint 18: Kullanıcı yönetimi */}
        <Route
          path="/users"
          element={
            <ProtectedRoute>
              <UsersPage />
            </ProtectedRoute>
          }
        />
        {/* Sprint 19: Denetim kayıtları */}
        <Route
          path="/audit"
          element={
            <ProtectedRoute>
              <AuditPage />
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
              <AthletesPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/sporcular/:id"
          element={
            <ProtectedRoute>
              <AthleteDetailPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/veliler"
          element={
            <ProtectedRoute>
              <GuardiansPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/veliler/:id"
          element={
            <ProtectedRoute>
              <GuardianDetailPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/uyeler"
          element={
            <ProtectedRoute>
              <MembersPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/uyeler/:id"
          element={
            <ProtectedRoute>
              <MemberDetailPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/antrenorler"
          element={
            <ProtectedRoute>
              <CoachesPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/antrenorler/:id"
          element={
            <ProtectedRoute>
              <CoachDetailPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/akademi"
          element={
            <ProtectedRoute>
              <AkademiPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/akademi/program/:slug"
          element={
            <ProtectedRoute>
              <ProgramPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/akademi/ders/:slug"
          element={
            <ProtectedRoute>
              <LessonPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/egitimler"
          element={
            <ProtectedRoute>
              <TrainingPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/egitimler/:id"
          element={
            <ProtectedRoute>
              <TrainingDetailPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/yoklama"
          element={
            <ProtectedRoute>
              <AttendancePage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/katilim"
          element={
            <ProtectedRoute>
              <SelfCheckinPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/tekneler"
          element={
            <ProtectedRoute>
              <EquipmentPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/tekneler/:id"
          element={
            <ProtectedRoute>
              <EquipmentDetailPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/odemeler"
          element={
            <ProtectedRoute>
              <PaymentsPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/raporlar"
          element={
            <ProtectedRoute>
              <ReportsPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/ayarlar"
          element={
            <ProtectedRoute>
              <SettingsPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/bildirimler"
          element={
            <ProtectedRoute>
              <NotificationsPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/takvim"
          element={
            <ProtectedRoute>
              <CalendarPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/belgeler"
          element={
            <ProtectedRoute>
              <DocumentsPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/belgeler/:id"
          element={
            <ProtectedRoute>
              <DocumentDetailPage />
            </ProtectedRoute>
          }
        />
        {/* Eğitim Kütüphanesi — antrenör/yönetici */}
        <Route
          path="/kutuphane"
          element={
            <ProtectedRoute>
              <KutuphanePage />
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
