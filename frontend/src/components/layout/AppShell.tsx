import { useState, useEffect, useRef } from 'react'
import { NavLink, Link, useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '@/hooks/useAuth'
import { usePendingApplications } from '@/hooks/usePendingApplications'
import { itemActive, visibleNavigation } from '@/config/navigation'
import { notificationsApi } from '@/api/notifications'

interface AppShellProps {
  children: React.ReactNode
  title?: string
}

export default function AppShell({ children, title }: AppShellProps) {
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [unreadNotifications, setUnreadNotifications] = useState(0)
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [menuSearch, setMenuSearch] = useState('')
  const [expanded, setExpanded] = useState<Record<string, boolean>>({})
  const hamburger = useRef<HTMLButtonElement>(null)
  const groups = visibleNavigation(user?.role ?? '', menuSearch)

  useEffect(() => {
    if (!sidebarOpen) return
    const escape = (e: KeyboardEvent) => { if (e.key === 'Escape') { setSidebarOpen(false); hamburger.current?.focus() } }
    window.addEventListener('keydown', escape)
    return () => window.removeEventListener('keydown', escape)
  }, [sidebarOpen])
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
        <button className="sidebar-overlay" aria-label="Menüyü kapat" onClick={closeSidebar} />
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

        <nav id="main-navigation" aria-label="Ana menü">
          <div className="sidebar-search"><input type="search" aria-label="Menüde ara" placeholder="Menüde ara…" value={menuSearch} onChange={(e) => setMenuSearch(e.target.value)} /></div>
          {groups.length === 0 && <p className="sidebar-no-results" role="status">Eşleşen menü bulunamadı.</p>}
          <ul className="sidebar-nav">
            {groups.map((group) => {
              const activeGroup = group.items.some((item) => itemActive(item, location.pathname))
              const open = !!menuSearch.trim() || (expanded[group.id] ?? (activeGroup || group.id === 'home'))
              return <li key={group.id} className="sidebar-group">
                <button type="button" className={`sidebar-group-toggle${activeGroup ? ' current' : ''}`} aria-expanded={open} aria-controls={`nav-${group.id}`} onClick={() => setExpanded((old) => ({ ...old, [group.id]: !open }))}>
                  <span aria-hidden="true">{group.icon}</span><span>{group.label}</span><span className="sidebar-group-chevron" aria-hidden="true">{open ? '⌄' : '›'}</span>
                </button>
                <ul id={`nav-${group.id}`} className="sidebar-group-items" hidden={!open}>
                  {group.items.map((item) => <li key={item.path}>
                    <NavLink to={item.path} className={() => `sidebar-nav-item${itemActive(item, location.pathname) ? ' active' : ''}`} onClick={closeSidebar}>
                      <span className="sidebar-nav-item-icon" aria-hidden="true">{item.icon}</span><span style={{ flex: 1 }}>{item.label}</span>
                      {item.path === '/admin/applications' && pendingApplications > 0 && <span className="sidebar-nav-badge" aria-label={`${pendingApplications} bekleyen başvuru`}>{pendingApplications > 99 ? '99+' : pendingApplications}</span>}
                    </NavLink>
                  </li>)}
                </ul>
              </li>
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
            ref={hamburger}
            className="topbar-hamburger"
            aria-expanded={sidebarOpen}
            aria-controls="main-navigation"
            onClick={() => setSidebarOpen((o) => !o)}
            aria-label="Menüyü aç/kapat"
          >
            ☰
          </button>
          <div className="topbar-title">{title ?? 'Mersin Yelken Yat ve Su Sporları Kulübü'}</div>
          <Link to="/bildirimler" className={`topbar-notifications${location.pathname === '/bildirimler' ? ' active' : ''}`} aria-label={unreadNotifications > 0 ? `Bildirimler, ${unreadNotifications} okunmamış` : 'Bildirimler'} title="Sistem bildirimleri" onClick={closeSidebar}>
            <span aria-hidden="true">🔔</span>{unreadNotifications > 0 && <span className="topbar-notification-count" aria-hidden="true">{unreadNotifications > 99 ? '99+' : unreadNotifications}</span>}
          </Link>
        </header>

        <main className="main-content">
          {children}
        </main>
      </div>
    </div>
  )
}
