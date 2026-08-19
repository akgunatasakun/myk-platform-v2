/**
 * /katilim — Yetişkin Sporcu Self Check-in Ekranı
 *
 * Sporcu kendi adult_self_checkin modlu kurslarındaki bugünkü/yaklaşan
 * oturumları görür ve "Katıldım" butonuyla check-in kaydı oluşturur.
 *
 * Sadece sporcu rolündeki kullanıcılar içindir. Antrenör yoklama için
 * /yoklama sayfasını kullanır.
 */
import { useCallback, useEffect, useState } from 'react'
import AppShell from '@/components/layout/AppShell'
import { trainingApi } from '@/api/training'
import type { SelfCheckinSession } from '@/types/training'

const STATUS_BADGE: Record<string, { label: string; color: string }> = {
  var: { label: 'Katıldım ✓', color: 'var(--color-success)' },
  yok: { label: 'Katılmadım', color: 'var(--color-danger)' },
  izinli: { label: 'İzinli', color: 'var(--color-warning)' },
  gecikti: { label: 'Geç Kaldım', color: 'var(--color-text-muted)' },
}

function fmtDate(d: string) {
  return new Date(d + 'T00:00:00').toLocaleDateString('tr-TR', {
    weekday: 'long',
    day: 'numeric',
    month: 'long',
  })
}

function todayInIstanbul() {
  return new Intl.DateTimeFormat('en-CA', {
    timeZone: 'Europe/Istanbul',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).format(new Date())
}

interface SessionCardProps {
  session: SelfCheckinSession
  onCheckin: (session: SelfCheckinSession) => Promise<void>
  loading: boolean
}

function SessionCard({ session, onCheckin, loading }: SessionCardProps) {
  const statusBadge = session.my_status ? STATUS_BADGE[session.my_status] : null

  return (
    <div
      className="card"
      style={{
        marginBottom: 12,
        borderLeft: `4px solid ${session.window_open ? 'var(--color-primary)' : 'var(--color-border)'}`,
      }}
    >
      <div className="card-body" style={{ padding: '16px 20px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 12 }}>
          <div style={{ flex: 1 }}>
            <div style={{ fontWeight: 600, fontSize: 15 }}>{session.course_name}</div>
            <div style={{ marginTop: 4, color: 'var(--color-text-muted)', fontSize: 13 }}>
              {fmtDate(session.session_date)}
              {session.start_time && (
                <> · {session.start_time.slice(0, 5)}{session.end_time ? ` – ${session.end_time.slice(0, 5)}` : ''}</>
              )}
            </div>
            <div style={{ marginTop: 6, fontSize: 12, color: 'var(--color-text-muted)' }}>
              {session.window_open
                ? `⏱ ${session.window_note}`
                : `🔒 Check-in kapalı — ${session.window_note}`}
            </div>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 8 }}>
            {statusBadge ? (
              <span
                style={{
                  padding: '4px 12px',
                  borderRadius: 20,
                  fontSize: 13,
                  fontWeight: 600,
                  background: statusBadge.color + '22',
                  color: statusBadge.color,
                  border: `1px solid ${statusBadge.color}44`,
                }}
              >
                {statusBadge.label}
              </span>
            ) : session.window_open ? (
              <button
                className="btn btn-primary btn-sm"
                disabled={loading}
                onClick={() => onCheckin(session)}
                style={{ minWidth: 100 }}
              >
                {loading ? '…' : 'Katıldım'}
              </button>
            ) : (
              <span style={{ fontSize: 12, color: 'var(--color-text-muted)' }}>
                Henüz kaydın yok
              </span>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

export default function SelfCheckinPage() {
  const [sessions, setSessions] = useState<SelfCheckinSession[]>([])
  const [loading, setLoading] = useState(true)
  const [checkinLoading, setCheckinLoading] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [successMsg, setSuccessMsg] = useState<string | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const r = await trainingApi.getSelfCheckinSessions()
      setSessions(r.data)
    } catch {
      setError('Oturum listesi yüklenemedi. Sayfayı yenileyin.')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  const handleCheckin = async (session: SelfCheckinSession) => {
    setCheckinLoading(session.session_id)
    setSuccessMsg(null)
    setError(null)
    try {
      await trainingApi.selfCheckin(session.course_id, session.session_id)
      setSuccessMsg(`"${session.course_name}" için ${fmtDate(session.session_date)} oturumuna katılımınız kaydedildi.`)
      // Listeyi güncelle
      setSessions((prev) =>
        prev.map((s) =>
          s.session_id === session.session_id ? { ...s, my_status: 'var' } : s
        )
      )
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      setError(detail ?? 'Check-in sırasında hata oluştu.')
    } finally {
      setCheckinLoading(null)
    }
  }

  const today = todayInIstanbul()
  const todaySessions = sessions.filter((s) => s.session_date === today)
  const upcomingSessions = sessions.filter((s) => s.session_date > today)

  return (
    <AppShell title="Katılım">
      <div className="page-header">
        <h1 className="page-title">Katılım</h1>
      </div>

      {error && (
        <div className="alert alert-error" style={{ marginBottom: 16 }}>
          <span>⚠️</span><span>{error}</span>
        </div>
      )}

      {successMsg && (
        <div className="alert alert-success" style={{ marginBottom: 16 }}>
          <span>✅</span><span>{successMsg}</span>
        </div>
      )}

      {loading ? (
        <div className="loading-center"><span className="loading-spinner lg" /></div>
      ) : sessions.length === 0 ? (
        <div className="empty-state">
          <div className="empty-state-icon">🏄</div>
          <div className="empty-state-title">Yaklaşan Oturum Yok</div>
          <div className="empty-state-desc">
            Önümüzdeki 14 günde self check-in modlu aktif bir eğitim oturumunuz bulunmuyor.
          </div>
        </div>
      ) : (
        <>
          {todaySessions.length > 0 && (
            <section style={{ marginBottom: 24 }}>
              <h2 style={{ fontSize: 14, fontWeight: 600, color: 'var(--color-text-muted)', marginBottom: 10, textTransform: 'uppercase', letterSpacing: 1 }}>
                Bugün
              </h2>
              {todaySessions.map((s) => (
                <SessionCard
                  key={s.session_id}
                  session={s}
                  onCheckin={handleCheckin}
                  loading={checkinLoading === s.session_id}
                />
              ))}
            </section>
          )}

          {upcomingSessions.length > 0 && (
            <section>
              <h2 style={{ fontSize: 14, fontWeight: 600, color: 'var(--color-text-muted)', marginBottom: 10, textTransform: 'uppercase', letterSpacing: 1 }}>
                Yaklaşan Oturumlar
              </h2>
              {upcomingSessions.map((s) => (
                <SessionCard
                  key={s.session_id}
                  session={s}
                  onCheckin={handleCheckin}
                  loading={checkinLoading === s.session_id}
                />
              ))}
            </section>
          )}
        </>
      )}
    </AppShell>
  )
}
