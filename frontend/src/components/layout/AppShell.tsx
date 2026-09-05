import { useState, useEffect } from 'react'
import { NavLink, useNavigate } from 'react-router-dom'
import { useAuth } from '@/hooks/useAuth'
import { usePendingApplications } from '@/hooks/usePendingApplications'
import { notificationsApi } from '@/api/notifications'

interface NavItem {
  path: string
  label: string
  icon: string
  roles?: string[]
}

// Rol grupları — tek yerde tanımlı
const ADMIN       = ['super_admin', 'kulup_yonetici']
const MANAGEMENT  = [...ADMIN, 'baskan', 'yk_uyesi']
const SECRETARIAT = [...MANAGEMENT, 'genel_sekreter', 'muhasebe']
const STAFF       = [...SECRETARIAT, 'sportif_direktor', 'basantrenor', 'antrenor',
                      'personel', 'saglik_sorumlusu', 'guvenlik_operasyon']
const COACHES     = [...MANAGEMENT, 'sportif_direktor', 'basantrenor', 'antrenor', 'genel_sekreter']

const NAV_ITEMS: NavItem[] = [
  // Herkes
  { path: '/dashboard',          label: 'Genel Bakış',       icon: '📊' },
  { path: '/bildirimler',        label: 'Bildirimler',        icon: '🔔' },
  { path: '/belgeler',           label: 'Belgeler',           icon: '📂' },

  // Yönetim + Personel
  { path: '/admin/applications', label: 'Başvurular',         icon: '📋', roles: SECRETARIAT },
  { path: '/persons',            label: 'Kişiler',            icon: '👥', roles: STAFF },
  { path: '/users',              label: 'Kullanıcılar',       icon: '🔐', roles: [...MANAGEMENT, 'genel_sekreter'] },
  { path: '/audit',              label: 'Denetim Kayıtları',  icon: '🛡️', roles: ADMIN },

  // Kişi grupları — staff tam, rol sahibi kendi kaydını görür
  { path: '/sporcular',          label: 'Sporcular',          icon: '⛵', roles: [...STAFF, 'sporcu'] },
  { path: '/veliler',            label: 'Veliler',            icon: '👨‍👩‍👧', roles: [...SECRETARIAT, 'veli'] },
  { path: '/uyeler',             label: 'Üyeler',             icon: '🏅', roles: [...SECRETARIAT, 'uye'] },
  { path: '/antrenorler',        label: 'Antrenörler',        icon: '🎯', roles: [...SECRETARIAT, 'basantrenor', 'antrenor'] },

  // Eğitim
  { path: '/akademi',            label: 'Deniz Akademisi',    icon: '🪢', roles: [...STAFF, 'sporcu', 'veli'] },
  { path: '/egitimler',          label: 'Eğitimler',          icon: '📚', roles: [...STAFF, 'sporcu', 'veli'] },
  { path: '/kutuphane',          label: 'Eğitim Kütüphanesi', icon: '📖', roles: COACHES },
  { path: '/antrenor-evrak-kuyrugu', label: 'Evrak Kuyruğu', icon: '📋', roles: [...ADMIN, 'basantrenor', 'antrenor'] },
  { path: '/yoklama',            label: 'Yoklama',            icon: '✅', roles: COACHES },
  { path: '/katilim',            label: 'Katılım (Öz)',       icon: '🙋', roles: ['sporcu'] },

  // Operasyonel
  { path: '/tekneler',           label: 'Ekipmanlar',         icon: '🛟', roles: STAFF },
  { path: '/odemeler',           label: 'Ödemeler',           icon: '💳', roles: [...SECRETARIAT, 'sporcu', 'veli', 'uye'] },
  { path: '/raporlar',           label: 'Raporlar',           icon: '📈', roles: SECRETARIAT },
  { path: '/takvim',             label: 'Takvim',             icon: '📅', roles: [...STAFF, 'sporcu', 'veli', 'uye'] },
  { path: '/ayarlar',            label: 'Ayarlar',            icon: '⚙️', roles: ADMIN },
]

interface AppShellProps {
  children: React.ReactNode
  title?: string
}

export default function AppShell({ children, title }: AppShellProps) {
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [unreadNotifications, setUnreadNotifications] = useState(0)
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const pendingApplications = usePendingApplications()

  // Bildirim badge sayısını çek (60 saniyede bir yenile)
  useEffect(() => {
    let cancelled = false
    const fetch = () => {
      notificationsApi.unreadCount()
        .then((r) => { if (!cancelled) setUnreadNotifications(r.data.count) })
        .catch(() => { /* sessizce geç */ })
    }
    fetch()
    const interval = setInterval(fetch, 60_000)
    return () => { cancelled = true; clearInterval(interval) }
  }, [])

  const handleLogout = async () => {
    await logout()
    navigate('/login')
  }

  const closeSidebar = () => setSidebarOpen(false)

  const initials = user?.full_name
    ? user.full_name.split(' ').map((n: string) => n[0]).slice(0, 2).join('').toUpperCase()
    : '?'

  return (
    <div className="app-shell">
      {/* Mobile overlay */}
      {sidebarOpen && (
        <div className="sidebar-overlay" onClick={closeSidebar} />
      )}

      {/* Sidebar */}
      <aside className={`sidebar${sidebarOpen ? ' open' : ''}`}>
        <div className="sidebar-logo">
          <img src="/logo-icon.png" alt="Mersin Yelken" className="sidebar-logo-img" />
          <div className="sidebar-logo-text">
            <span className="sidebar-logo-title">Mersin Yelken</span>
            <span className="sidebar-logo-sub">Yönetim Sistemi</span>
          </div>
        </div>

        <nav>
          <ul className="sidebar-nav">
            {NAV_ITEMS.filter((item) => !item.roles || (user?.role && item.roles.includes(user.role))).map((item) => {
              const showAppBadge =
                item.path === '/admin/applications' && pendingApplications > 0
              const showNotifBadge =
                item.path === '/bildirimler' && unreadNotifications > 0
              return (
                <li key={item.path}>
                  <NavLink
                    to={item.path}
                    className={({ isActive }) =>
                      `sidebar-nav-item${isActive ? ' active' : ''}`
                    }
                    onClick={closeSidebar}
                  >
                    <span className="sidebar-nav-item-icon">{item.icon}</span>
                    <span style={{ flex: 1 }}>{item.label}</span>
                    {showAppBadge && (
                      <span className="sidebar-nav-badge">
                        {pendingApplications > 99 ? '99+' : pendingApplications}
                      </span>
                    )}
                    {showNotifBadge && (
                      <span className="sidebar-nav-badge">
                        {unreadNotifications > 99 ? '99+' : unreadNotifications}
                      </span>
                    )}
                  </NavLink>
                </li>
              )
            })}
          </ul>
        </nav>

        <div className="sidebar-footer">
          <div className="sidebar-user">
            <div className="sidebar-user-avatar">{initials}</div>
            <div className="sidebar-user-info">
              <div className="sidebar-user-name">{user?.full_name ?? 'Kullanıcı'}</div>
              <div className="sidebar-user-role">{user?.role ?? ''}</div>
            </div>
          </div>
          <button className="sidebar-logout-btn" onClick={handleLogout}>
            Çıkış Yap
          </button>
        </div>
      </aside>

      {/* Main area */}
      <div className="app-shell-body">
        <header className="topbar">
          <button
            className="topbar-hamburger"
            onClick={() => setSidebarOpen((o) => !o)}
            aria-label="Menüyü aç/kapat"
          >
            ☰
          </button>
          <div className="topbar-title">{title ?? 'Mersin Yelken Yat ve Su Sporları Kulübü'}</div>
        </header>

        <main className="main-content">
          {children}
        </main>
      </div>
    </div>
  )
}
