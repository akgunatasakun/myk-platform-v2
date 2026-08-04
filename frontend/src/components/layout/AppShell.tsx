import { useState } from 'react'
import { NavLink, useNavigate } from 'react-router-dom'
import { useAuth } from '@/hooks/useAuth'

interface NavItem {
  path: string
  label: string
  icon: string
}

const NAV_ITEMS: NavItem[] = [
  { path: '/dashboard', label: 'Genel Bakış', icon: '📊' },
  { path: '/persons', label: 'Kişiler', icon: '👥' },
  { path: '/sporcular', label: 'Sporcular', icon: '⛵' },
  { path: '/veliler', label: 'Veliler', icon: '👨‍👩‍👧' },
  { path: '/uyeler', label: 'Üyeler', icon: '🏅' },
  { path: '/antrenorler', label: 'Antrenörler', icon: '🎯' },
  { path: '/egitimler', label: 'Eğitimler', icon: '📚' },
  { path: '/gruplar', label: 'Gruplar', icon: '🗂️' },
  { path: '/yoklama', label: 'Yoklama', icon: '✅' },
  { path: '/tekneler', label: 'Tekneler', icon: '🚢' },
  { path: '/odemeler', label: 'Ödemeler', icon: '💳' },
  { path: '/raporlar', label: 'Raporlar', icon: '📈' },
  { path: '/ayarlar', label: 'Ayarlar', icon: '⚙️' },
]

interface AppShellProps {
  children: React.ReactNode
  title?: string
}

export default function AppShell({ children, title }: AppShellProps) {
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const { user, logout } = useAuth()
  const navigate = useNavigate()

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
            {NAV_ITEMS.map((item) => (
              <li key={item.path}>
                <NavLink
                  to={item.path}
                  className={({ isActive }) =>
                    `sidebar-nav-item${isActive ? ' active' : ''}`
                  }
                  onClick={closeSidebar}
                >
                  <span className="sidebar-nav-item-icon">{item.icon}</span>
                  {item.label}
                </NavLink>
              </li>
            ))}
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
