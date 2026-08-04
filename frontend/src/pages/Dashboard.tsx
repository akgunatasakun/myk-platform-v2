import { useEffect, useState } from 'react'
import AppShell from '@/components/layout/AppShell'
import { dashboardApi } from '@/api/dashboard'
import type { DashboardStats } from '@/api/dashboard'

interface StatCardProps {
  label: string
  value: number
  icon: string
  variant?: 'default' | 'ocean' | 'success' | 'warning'
}

function StatCard({ label, value, icon, variant = 'default' }: StatCardProps) {
  return (
    <div className={`stat-card${variant !== 'default' ? ` ${variant}` : ''}`}>
      <div className="stat-card-icon">{icon}</div>
      <div className="stat-card-value">{value.toLocaleString('tr-TR')}</div>
      <div className="stat-card-label">{label}</div>
    </div>
  )
}

export default function Dashboard() {
  const [stats, setStats] = useState<DashboardStats | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    dashboardApi
      .stats()
      .then((r) => setStats(r.data))
      .catch(() => setError('İstatistikler yüklenemedi. Lütfen sayfayı yenileyin.'))
      .finally(() => setLoading(false))
  }, [])

  return (
    <AppShell title="Genel Bakış">
      <div className="page-header">
        <h1 className="page-title">Genel Bakış</h1>
      </div>

      {loading && (
        <div className="loading-center">
          <span className="loading-spinner lg" />
        </div>
      )}

      {error && (
        <div className="alert alert-error">
          <span>⚠️</span>
          <span>{error}</span>
        </div>
      )}

      {stats && !loading && (
        <>
          <div className="stat-cards-grid">
            <StatCard
              label="Toplam Kişi"
              value={stats.toplam_kisi}
              icon="👥"
              variant="default"
            />
            <StatCard
              label="Aktif Sporcu"
              value={stats.aktif_sporcu}
              icon="⛵"
              variant="ocean"
            />
            <StatCard
              label="Aktif Üye"
              value={stats.aktif_uye}
              icon="🏅"
              variant="success"
            />
            <StatCard
              label="Antrenör"
              value={stats.antrenor_sayisi}
              icon="🎯"
              variant="default"
            />
            <StatCard
              label="Vadesi Geçen Ödeme"
              value={stats.vadesi_gecen_odeme}
              icon="💳"
              variant={stats.vadesi_gecen_odeme > 0 ? 'warning' : 'default'}
            />
            <StatCard
              label="Yaklaşan Eğitim"
              value={stats.yaklasan_egitim}
              icon="📚"
              variant="default"
            />
            <StatCard
              label="Bakım Bekleyen"
              value={stats.bakim_bekleyen_ekipman}
              icon="🔧"
              variant={stats.bakim_bekleyen_ekipman > 0 ? 'warning' : 'default'}
            />
          </div>

          <div className="card" style={{ marginTop: '8px' }}>
            <div className="card-header">Son Aktiviteler</div>
            <div className="card-body">
              {stats.son_aktiviteler.length === 0 ? (
                <div className="empty-state" style={{ padding: '24px' }}>
                  <div className="empty-state-desc">
                    Henüz aktivite kaydı bulunmuyor.
                  </div>
                </div>
              ) : null}
            </div>
          </div>
        </>
      )}
    </AppShell>
  )
}
