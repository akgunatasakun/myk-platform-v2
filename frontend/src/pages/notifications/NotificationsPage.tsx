/**
 * Bildirimler sayfası — domain event feed
 *
 * - Okunmamışlar üstte
 * - Tümünü okundu işaretle butonu
 * - Tek satır okundu işaretleme
 * - Severity'e göre renk kodlama
 */
import { useEffect, useState, useCallback } from 'react'
import AppShell from '@/components/layout/AppShell'
import { notificationsApi } from '@/api/notifications'
import type { Notification, Severity } from '@/types/notifications'
import { EVENT_LABELS, AGGREGATE_EMOJIS, EVENT_SEVERITY } from '@/types/notifications'

// ── Yardımcılar ────────────────────────────────────────────────────────────────

function fmtDateTime(dt: string) {
  return new Date(dt).toLocaleString('tr-TR', {
    day: 'numeric',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function severityStyle(sev: Severity, read: boolean): React.CSSProperties {
  const opacity = read ? 0.6 : 1
  if (sev === 'danger')  return { borderLeft: '4px solid #dc2626', opacity }
  if (sev === 'warning') return { borderLeft: '4px solid #d97706', opacity }
  return                        { borderLeft: '4px solid #3b82f6', opacity }
}

function NotificationRow({
  n,
  onMarkRead,
}: {
  n: Notification
  onMarkRead: (id: string) => void
}) {
  const read = n.acknowledged_at !== null
  const label = EVENT_LABELS[n.event_type] ?? n.event_type
  const emoji = AGGREGATE_EMOJIS[n.aggregate_type] ?? '📝'
  const sev: Severity = EVENT_SEVERITY[n.event_type] ?? 'info'

  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'flex-start',
        gap: 12,
        padding: '12px 16px',
        borderBottom: '1px solid var(--color-border)',
        background: read ? 'transparent' : 'var(--color-surface-raised, #f8fafc)',
        ...severityStyle(sev, read),
      }}
    >
      <span style={{ fontSize: 20, flexShrink: 0, marginTop: 2 }}>{emoji}</span>

      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 2 }}>
          <span style={{ fontWeight: read ? 400 : 600, fontSize: 14 }}>{label}</span>
          {!read && (
            <span
              style={{
                fontSize: 10,
                background: '#3b82f6',
                color: '#fff',
                borderRadius: 10,
                padding: '1px 6px',
                fontWeight: 700,
                letterSpacing: '0.03em',
              }}
            >
              YENİ
            </span>
          )}
        </div>

        {/* Payload özeti */}
        {n.payload && Object.keys(n.payload).length > 0 && (
          <div style={{ fontSize: 12, color: 'var(--color-text-muted)', marginBottom: 2 }}>
            {Object.entries(n.payload)
              .filter(([, v]) => v !== null && v !== undefined)
              .slice(0, 3)
              .map(([k, v]) => `${k}: ${v}`)
              .join('  ·  ')}
          </div>
        )}

        <div style={{ fontSize: 11, color: 'var(--color-text-muted)' }}>
          {fmtDateTime(n.created_at)}
          {read && n.acknowledged_at && (
            <span style={{ marginLeft: 8 }}>· okundu {fmtDateTime(n.acknowledged_at)}</span>
          )}
        </div>
      </div>

      {!read && (
        <button
          onClick={() => onMarkRead(n.id)}
          style={{
            fontSize: 12,
            color: 'var(--color-primary)',
            background: 'none',
            border: 'none',
            cursor: 'pointer',
            flexShrink: 0,
            padding: '2px 0',
          }}
        >
          Okundu
        </button>
      )}
    </div>
  )
}

// ── Ana bileşen ────────────────────────────────────────────────────────────────

export default function NotificationsPage() {
  const [notifications, setNotifications] = useState<Notification[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [unreadOnlyFilter, setUnreadOnlyFilter] = useState(false)
  const [markingAll, setMarkingAll] = useState(false)

  const load = useCallback(() => {
    setLoading(true)
    notificationsApi
      .list({ limit: 100, unread_only: unreadOnlyFilter })
      .then((r) => setNotifications(r.data))
      .catch(() => setError('Bildirimler yüklenemedi.'))
      .finally(() => setLoading(false))
  }, [unreadOnlyFilter])

  useEffect(() => {
    load()
  }, [load])

  const handleMarkRead = async (id: string) => {
    try {
      const r = await notificationsApi.markRead(id)
      setNotifications((prev) =>
        prev.map((n) => (n.id === id ? r.data : n))
      )
    } catch {
      // sessizce geç
    }
  }

  const handleMarkAll = async () => {
    setMarkingAll(true)
    try {
      await notificationsApi.markAllRead()
      load()
    } finally {
      setMarkingAll(false)
    }
  }

  const unreadCount = notifications.filter((n) => n.acknowledged_at === null).length

  return (
    <AppShell title="Bildirimler">
      <div className="page-header">
        <h1 className="page-title">🔔 Bildirimler</h1>

        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          {/* Filtre */}
          <button
            className={`btn ${unreadOnlyFilter ? 'btn-primary' : 'btn-secondary'}`}
            onClick={() => setUnreadOnlyFilter((v) => !v)}
            style={{ fontSize: 13 }}
          >
            {unreadOnlyFilter ? '✓ Sadece okunmamış' : 'Sadece okunmamış'}
          </button>

          {/* Tümünü okundu */}
          {unreadCount > 0 && (
            <button
              className="btn btn-secondary"
              onClick={handleMarkAll}
              disabled={markingAll}
              style={{ fontSize: 13 }}
            >
              {markingAll ? 'İşleniyor…' : `Tümünü okundu (${unreadCount})`}
            </button>
          )}
        </div>
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

      {!loading && !error && (
        <div className="card">
          {notifications.length === 0 ? (
            <div
              className="card-body"
              style={{
                textAlign: 'center',
                padding: '40px 16px',
                color: 'var(--color-text-muted)',
              }}
            >
              {unreadOnlyFilter ? 'Okunmamış bildirim yok.' : 'Henüz bildirim bulunmuyor.'}
            </div>
          ) : (
            <div className="card-body" style={{ padding: 0 }}>
              {notifications.map((n) => (
                <NotificationRow
                  key={n.id}
                  n={n}
                  onMarkRead={handleMarkRead}
                />
              ))}
            </div>
          )}
        </div>
      )}
    </AppShell>
  )
}
