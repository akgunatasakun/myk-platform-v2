/**
 * Dashboard 2.0 — Genel Bakış
 *
 * Bölümler:
 *   1. KPI kartları (sayaçlar)
 *   2. Uyarı satırları (tıklanabilir, renkli)
 *   3. Bugünün oturumları
 *   4. Yaklaşan eğitimler (7 gün)
 *   5. Son aktiviteler (audit feed)
 */
import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import AppShell from '@/components/layout/AppShell'
import { dashboardApi } from '@/api/dashboard'
import type { AktiviteOut, DashboardStats, OturumOut } from '@/api/dashboard'

// ── Yardımcı ─────────────────────────────────────────────────────────────────

function fmtTime(t?: string | null) {
  if (!t) return null
  return t.substring(0, 5)
}

function fmtDate(d: string) {
  return new Date(d + 'T00:00:00').toLocaleDateString('tr-TR', {
    weekday: 'short',
    day: 'numeric',
    month: 'short',
  })
}

function fmtDateTime(dt: string) {
  return new Date(dt).toLocaleString('tr-TR', {
    day: 'numeric',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function fmtTL(amount: number) {
  return amount.toLocaleString('tr-TR', { style: 'currency', currency: 'TRY' })
}

const ACTION_LABELS: Record<string, string> = {
  person_created: 'Kişi oluşturuldu',
  person_updated: 'Kişi güncellendi',
  person_deleted: 'Kişi silindi',
  role_added: 'Rol eklendi',
  role_removed: 'Rol kaldırıldı',
  application_submitted: 'Başvuru alındı',
  application_approved: 'Başvuru onaylandı',
  application_rejected: 'Başvuru reddedildi',
  payment_created: 'Ödeme kaydedildi',
  payment_updated: 'Ödeme güncellendi',
  equipment_created: 'Ekipman eklendi',
  equipment_updated: 'Ekipman güncellendi',
  training_course_created: 'Eğitim oluşturuldu',
  training_course_updated: 'Eğitim güncellendi',
  training_session_created: 'Oturum oluşturuldu',
  attendance_saved: 'Yoklama kaydedildi',
  athlete_profile_created: 'Sporcu profili oluşturuldu',
  athlete_profile_updated: 'Sporcu profili güncellendi',
  club_settings_updated: 'Kulüp ayarları güncellendi',
  sports_branch_created: 'Branş eklendi',
  sports_branch_updated: 'Branş güncellendi',
  setup_completed: 'Sistem kuruldu',
}

const RESOURCE_EMOJIS: Record<string, string> = {
  person: '👤',
  payment: '💳',
  equipment: '🛟',
  training_course: '📚',
  training_session: '🗓️',
  membership_application: '📋',
  athlete_profile: '⛵',
  club: '🏢',
  sports_branch: '⚓',
}

// ── KPI Kartı ─────────────────────────────────────────────────────────────────

interface StatCardProps {
  label: string
  value: number | string
  icon: string
  variant?: 'default' | 'ocean' | 'success' | 'warning'
  onClick?: () => void
  subtitle?: string
}

function StatCard({ label, value, icon, variant = 'default', onClick, subtitle }: StatCardProps) {
  const numVal = typeof value === 'number' ? value : undefined
  return (
    <div
      className={`stat-card${variant !== 'default' ? ` ${variant}` : ''}`}
      onClick={onClick}
      style={onClick ? { cursor: 'pointer' } : undefined}
    >
      <div className="stat-card-icon">{icon}</div>
      <div className="stat-card-value">
        {typeof numVal === 'number' ? numVal.toLocaleString('tr-TR') : value}
      </div>
      <div className="stat-card-label">{label}</div>
      {subtitle && (
        <div style={{ fontSize: 11, color: 'var(--color-text-muted)', marginTop: 2 }}>
          {subtitle}
        </div>
      )}
    </div>
  )
}

// ── Uyarı satırı ─────────────────────────────────────────────────────────────

interface AlertRowProps {
  icon: string
  text: string
  onClick: () => void
  color?: string
}

function AlertRow({ icon, text, onClick, color = 'var(--color-warning, #b45309)' }: AlertRowProps) {
  return (
    <div
      onClick={onClick}
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 10,
        padding: '10px 14px',
        borderRadius: 8,
        background: '#fffbeb',
        border: '1px solid #fde68a',
        cursor: 'pointer',
        marginBottom: 8,
      }}
    >
      <span style={{ fontSize: 18 }}>{icon}</span>
      <span style={{ fontSize: 14, color, fontWeight: 500, flex: 1 }}>{text}</span>
      <span style={{ color: 'var(--color-text-muted)', fontSize: 12 }}>→</span>
    </div>
  )
}

// ── Oturum satırı ─────────────────────────────────────────────────────────────

function OturumRow({ s, onClick }: { s: OturumOut; onClick: () => void }) {
  const baslangic = fmtTime(s.start_time)
  const bitis = fmtTime(s.end_time)
  const saat = baslangic ? (bitis ? `${baslangic} – ${bitis}` : baslangic) : null

  return (
    <tr onClick={onClick} style={{ cursor: 'pointer' }}>
      <td>
        <strong>{s.course_name}</strong>
      </td>
      <td style={{ fontSize: 13, color: 'var(--color-text-muted)' }}>
        {saat ?? '—'}
      </td>
      <td style={{ fontSize: 13 }}>{s.instructor_name ?? '—'}</td>
      <td>
        <span
          className="badge"
          style={{
            background: s.status === 'yapildi' ? '#f0fdf4' : '#eff6ff',
            color: s.status === 'yapildi' ? '#166534' : '#1d4ed8',
            fontSize: 11,
          }}
        >
          {s.status}
        </span>
      </td>
    </tr>
  )
}

// ── Ana bileşen ───────────────────────────────────────────────────────────────

export default function Dashboard() {
  const navigate = useNavigate()
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
          {/* ── KPI kartları ─────────────────────────────────────────────── */}
          <div className="stat-cards-grid">
            <StatCard
              label="Toplam Kişi"
              value={stats.toplam_kisi}
              icon="👥"
              onClick={() => navigate('/persons')}
            />
            <StatCard
              label="Aktif Sporcu"
              value={stats.aktif_sporcu}
              icon="⛵"
              variant="ocean"
              onClick={() => navigate('/sporcular')}
            />
            <StatCard
              label="Aktif Üye"
              value={stats.aktif_uye}
              icon="🏅"
              variant="success"
              onClick={() => navigate('/uyeler')}
            />
            <StatCard
              label="Antrenör"
              value={stats.antrenor_sayisi}
              icon="🎯"
              onClick={() => navigate('/antrenorler')}
            />
            <StatCard
              label="Aktif / Planlanan Kurs"
              value={stats.aktif_kurs_sayisi}
              icon="📚"
              onClick={() => navigate('/egitimler')}
            />
            <StatCard
              label="Yaklaşan Oturum"
              value={stats.yaklasan_egitim}
              icon="🗓️"
              subtitle="bugün + 7 gün"
              onClick={() => navigate('/egitimler')}
            />
            <StatCard
              label="Bakım / Hasarlı"
              value={stats.bakim_bekleyen_ekipman}
              icon="🔧"
              variant={stats.bakim_bekleyen_ekipman > 0 ? 'warning' : 'default'}
              onClick={() => navigate('/tekneler')}
            />
          </div>

          {/* ── Uyarılar ─────────────────────────────────────────────────── */}
          {(stats.bekleyen_basvuru > 0 ||
            stats.vadesi_gecen_odeme > 0 ||
            stats.bakim_bekleyen_ekipman > 0) && (
            <div style={{ marginBottom: 24 }}>
              {stats.bekleyen_basvuru > 0 && (
                <AlertRow
                  icon="📋"
                  text={`${stats.bekleyen_basvuru} bekleyen üyelik başvurusu`}
                  onClick={() => navigate('/admin/applications')}
                  color="#1d4ed8"
                />
              )}
              {stats.vadesi_gecen_odeme > 0 && (
                <AlertRow
                  icon="💳"
                  text={`${stats.vadesi_gecen_odeme} vadesi geçmiş ödeme — ${fmtTL(stats.vadesi_gecen_odeme_toplami)}`}
                  onClick={() => navigate('/odemeler')}
                />
              )}
              {stats.bakim_bekleyen_ekipman > 0 && (
                <AlertRow
                  icon="🔧"
                  text={`${stats.bakim_bekleyen_ekipman} ekipman bakım / hasar uyarısı`}
                  onClick={() => navigate('/tekneler')}
                />
              )}
            </div>
          )}

          {/* ── Bugünün oturumları ────────────────────────────────────────── */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20, marginBottom: 20 }}>
            <div className="card">
              <div className="card-header">
                Bugünün Oturumları
                {stats.bugunun_oturumlari.length > 0 && (
                  <span
                    className="badge"
                    style={{
                      marginLeft: 8,
                      background: '#eff6ff',
                      color: '#1d4ed8',
                      fontSize: 11,
                    }}
                  >
                    {stats.bugunun_oturumlari.length}
                  </span>
                )}
              </div>
              <div className="card-body" style={{ padding: 0 }}>
                {stats.bugunun_oturumlari.length === 0 ? (
                  <div style={{ padding: '20px 16px', color: 'var(--color-text-muted)', fontSize: 14 }}>
                    Bugün planlanmış oturum yok.
                  </div>
                ) : (
                  <table className="data-table">
                    <thead>
                      <tr>
                        <th>Kurs</th>
                        <th>Saat</th>
                        <th>Eğitmen</th>
                        <th>Durum</th>
                      </tr>
                    </thead>
                    <tbody>
                      {stats.bugunun_oturumlari.map((s) => (
                        <OturumRow
                          key={s.session_id}
                          s={s}
                          onClick={() => navigate(`/egitimler/${s.course_id}`)}
                        />
                      ))}
                    </tbody>
                  </table>
                )}
              </div>
            </div>

            {/* ── Yaklaşan eğitimler ─────────────────────────────────────── */}
            <div className="card">
              <div className="card-header">
                Yaklaşan Eğitimler
                <span
                  style={{
                    fontSize: 12,
                    color: 'var(--color-text-muted)',
                    fontWeight: 400,
                    marginLeft: 6,
                  }}
                >
                  (7 gün)
                </span>
              </div>
              <div className="card-body" style={{ padding: 0 }}>
                {stats.yaklasan_oturumlar.length === 0 ? (
                  <div style={{ padding: '20px 16px', color: 'var(--color-text-muted)', fontSize: 14 }}>
                    Önümüzdeki 7 günde planlanmış oturum yok.
                  </div>
                ) : (
                  <table className="data-table">
                    <thead>
                      <tr>
                        <th>Kurs</th>
                        <th>Tarih</th>
                        <th>Saat</th>
                        <th>Eğitmen</th>
                      </tr>
                    </thead>
                    <tbody>
                      {stats.yaklasan_oturumlar.map((s) => (
                        <tr
                          key={s.session_id}
                          onClick={() => navigate(`/egitimler/${s.course_id}`)}
                          style={{ cursor: 'pointer' }}
                        >
                          <td>
                            <strong>{s.course_name}</strong>
                          </td>
                          <td style={{ fontSize: 13 }}>{fmtDate(s.session_date)}</td>
                          <td style={{ fontSize: 13, color: 'var(--color-text-muted)' }}>
                            {fmtTime(s.start_time) ?? '—'}
                          </td>
                          <td style={{ fontSize: 13 }}>{s.instructor_name ?? '—'}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </div>
            </div>
          </div>

          {/* ── Son aktiviteler ───────────────────────────────────────────── */}
          <div className="card">
            <div className="card-header">Son Aktiviteler</div>
            <div className="card-body" style={{ padding: 0 }}>
              {stats.son_aktiviteler.length === 0 ? (
                <div style={{ padding: '20px 16px', color: 'var(--color-text-muted)', fontSize: 14 }}>
                  Henüz aktivite kaydı bulunmuyor.
                </div>
              ) : (
                <div>
                  {stats.son_aktiviteler.map((a: AktiviteOut) => {
                    const emoji = RESOURCE_EMOJIS[a.resource_type] ?? '📝'
                    const label = ACTION_LABELS[a.action] ?? a.action
                    return (
                      <div
                        key={a.id}
                        style={{
                          display: 'flex',
                          alignItems: 'center',
                          gap: 12,
                          padding: '10px 16px',
                          borderBottom: '1px solid var(--color-border)',
                        }}
                      >
                        <span style={{ fontSize: 18, flexShrink: 0 }}>{emoji}</span>
                        <div style={{ flex: 1, minWidth: 0 }}>
                          <div style={{ fontSize: 14, fontWeight: 500 }}>{label}</div>
                          {a.resource_id && (
                            <div
                              style={{
                                fontSize: 11,
                                color: 'var(--color-text-muted)',
                                fontFamily: 'monospace',
                                overflow: 'hidden',
                                textOverflow: 'ellipsis',
                                whiteSpace: 'nowrap',
                              }}
                            >
                              {a.resource_type} · {a.resource_id.substring(0, 8)}…
                            </div>
                          )}
                        </div>
                        <span
                          style={{
                            fontSize: 12,
                            color: 'var(--color-text-muted)',
                            flexShrink: 0,
                          }}
                        >
                          {fmtDateTime(a.created_at)}
                        </span>
                      </div>
                    )
                  })}
                </div>
              )}
            </div>
          </div>
        </>
      )}
    </AppShell>
  )
}
