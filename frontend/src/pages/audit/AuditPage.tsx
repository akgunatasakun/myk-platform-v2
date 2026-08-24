import { useCallback, useEffect, useRef, useState } from 'react'
import AppShell from '@/components/layout/AppShell'
import { auditApi, AuditLogItem } from '@/api/audit'

const PAGE_SIZE = 50

const ACTION_LABELS: Record<string, string> = {
  login_success: 'Giriş',
  login_failed: 'Başarısız Giriş',
  logout: 'Çıkış',
  user_created: 'Kullanıcı Oluşturuldu',
  user_updated: 'Kullanıcı Güncellendi',
  user_deleted: 'Kullanıcı Silindi',
  user_restored: 'Kullanıcı Geri Yüklendi',
  user_password_reset: 'Parola Sıfırlandı',
  password_changed: 'Parola Değiştirildi',
  person_created: 'Kişi Oluşturuldu',
  person_updated: 'Kişi Güncellendi',
  person_deleted: 'Kişi Silindi',
  payment_created: 'Ödeme Oluşturuldu',
  payment_updated: 'Ödeme Güncellendi',
  payment_deleted: 'Ödeme Silindi',
  training_course_created: 'Eğitim Oluşturuldu',
  training_enrollment_created: 'Kayıt Yapıldı',
  training_enrollment_cancelled: 'Kayıt İptal',
  training_attendance_self_checkin: 'Öz Yoklama',
  equipment_created: 'Ekipman Oluşturuldu',
  equipment_updated: 'Ekipman Güncellendi',
  equipment_deleted: 'Ekipman Silindi',
  membership_application_created: 'Başvuru Oluşturuldu',
  membership_application_status_changed: 'Başvuru Durumu Değişti',
  club_settings_updated: 'Kulüp Ayarları Güncellendi',
}

const RESOURCE_LABELS: Record<string, string> = {
  user: 'Kullanıcı',
  person: 'Kişi',
  payment: 'Ödeme',
  training: 'Eğitim',
  equipment: 'Ekipman',
  membership: 'Üyelik',
  club: 'Kulüp',
  athlete: 'Sporcu',
}

function formatDate(iso: string) {
  return new Date(iso).toLocaleString('tr-TR', {
    day: '2-digit', month: '2-digit', year: 'numeric',
    hour: '2-digit', minute: '2-digit', second: '2-digit',
  })
}

export default function AuditPage() {
  const [items, setItems] = useState<AuditLogItem[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [skip, setSkip] = useState(0)

  // Filtreler
  const [action, setAction] = useState('')
  const [resourceType, setResourceType] = useState('')
  const [successFilter, setSuccessFilter] = useState('')
  const [fromDt, setFromDt] = useState('')
  const [toDt, setToDt] = useState('')

  // Seçili satır (changes)
  const [selected, setSelected] = useState<AuditLogItem | null>(null)

  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const fetchLogs = useCallback(
    async (skipVal: number, act: string, res: string, succ: string, from: string, to: string) => {
      setLoading(true)
      setError(null)
      try {
        const params: Record<string, unknown> = { skip: skipVal, limit: PAGE_SIZE }
        if (act) params.action = act
        if (res) params.resource_type = res
        if (succ !== '') params.success = succ === 'true'
        if (from) params.from = new Date(from).toISOString()
        if (to) params.to = new Date(to).toISOString()
        const resp = await auditApi.list(params)
        setItems(resp.data.items)
        setTotal(resp.data.total)
      } catch {
        setError('Denetim kayıtları yüklenemedi.')
      } finally {
        setLoading(false)
      }
    },
    []
  )

  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(() => {
      setSkip(0)
      fetchLogs(0, action, resourceType, successFilter, fromDt, toDt)
    }, 300)
    return () => { if (debounceRef.current) clearTimeout(debounceRef.current) }
  }, [action, resourceType, successFilter, fromDt, toDt, fetchLogs])

  useEffect(() => {
    fetchLogs(skip, action, resourceType, successFilter, fromDt, toDt)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [skip])

  const totalPages = Math.ceil(total / PAGE_SIZE)
  const currentPage = Math.floor(skip / PAGE_SIZE) + 1

  return (
    <AppShell title="Denetim Kayıtları">
      <div className="page-header">
        <h1 className="page-title">Denetim Kayıtları</h1>
        <span style={{ color: 'var(--color-text-secondary)', fontSize: 13 }}>
          {total} kayıt
        </span>
      </div>

      {/* Filtreler */}
      <div className="filter-bar" style={{ flexWrap: 'wrap', gap: 8 }}>
        <select
          className="form-select"
          style={{ width: 'auto', minWidth: 180 }}
          value={action}
          onChange={(e) => setAction(e.target.value)}
        >
          <option value="">Tüm Aksiyonlar</option>
          {Object.entries(ACTION_LABELS).map(([val, label]) => (
            <option key={val} value={val}>{label}</option>
          ))}
        </select>

        <select
          className="form-select"
          style={{ width: 'auto', minWidth: 140 }}
          value={resourceType}
          onChange={(e) => setResourceType(e.target.value)}
        >
          <option value="">Tüm Kaynaklar</option>
          {Object.entries(RESOURCE_LABELS).map(([val, label]) => (
            <option key={val} value={val}>{label}</option>
          ))}
        </select>

        <select
          className="form-select"
          style={{ width: 'auto', minWidth: 120 }}
          value={successFilter}
          onChange={(e) => setSuccessFilter(e.target.value)}
        >
          <option value="">Tüm Sonuçlar</option>
          <option value="true">Başarılı</option>
          <option value="false">Başarısız</option>
        </select>

        <input
          type="datetime-local"
          className="form-input"
          style={{ width: 'auto' }}
          value={fromDt}
          onChange={(e) => setFromDt(e.target.value)}
          title="Başlangıç tarihi"
        />
        <input
          type="datetime-local"
          className="form-input"
          style={{ width: 'auto' }}
          value={toDt}
          onChange={(e) => setToDt(e.target.value)}
          title="Bitiş tarihi"
        />

        {(action || resourceType || successFilter || fromDt || toDt) && (
          <button
            className="btn btn-sm btn-secondary"
            onClick={() => { setAction(''); setResourceType(''); setSuccessFilter(''); setFromDt(''); setToDt('') }}
          >
            ✕ Temizle
          </button>
        )}
      </div>

      {error && (
        <div className="alert alert-error"><span>⚠️</span><span>{error}</span></div>
      )}

      <div className="table-container">
        {loading ? (
          <div className="loading-center"><span className="loading-spinner lg" /></div>
        ) : items.length === 0 ? (
          <div className="empty-state">
            <div className="empty-state-icon">🔍</div>
            <div className="empty-state-title">Kayıt Bulunamadı</div>
            <div className="empty-state-desc">Seçilen filtrelerle eşleşen denetim kaydı yok.</div>
          </div>
        ) : (
          <>
            <table className="data-table">
              <thead>
                <tr>
                  <th>Zaman</th>
                  <th>Aksiyon</th>
                  <th>Kaynak</th>
                  <th>Kaynak ID</th>
                  <th>IP</th>
                  <th>Sonuç</th>
                  <th>Detay</th>
                </tr>
              </thead>
              <tbody>
                {items.map((row) => (
                  <tr
                    key={row.id}
                    style={{ cursor: row.changes ? 'pointer' : 'default' }}
                    onClick={() => row.changes && setSelected(row)}
                    title={row.changes ? 'Değişiklikleri görmek için tıkla' : undefined}
                  >
                    <td style={{ whiteSpace: 'nowrap', fontSize: 12 }}>
                      {formatDate(row.created_at)}
                    </td>
                    <td>
                      <span className={`badge ${row.success ? 'badge-active' : 'badge-danger'}`}>
                        {ACTION_LABELS[row.action] ?? row.action}
                      </span>
                    </td>
                    <td>
                      <span className="badge badge-uye">
                        {RESOURCE_LABELS[row.resource_type] ?? row.resource_type}
                      </span>
                    </td>
                    <td style={{ fontSize: 11, color: 'var(--color-text-secondary)' }}>
                      {row.resource_id ? row.resource_id.slice(0, 8) + '…' : '—'}
                    </td>
                    <td style={{ fontSize: 12 }}>{row.ip_address ?? '—'}</td>
                    <td>
                      {row.success
                        ? <span style={{ color: 'var(--color-success)' }}>✓</span>
                        : <span style={{ color: 'var(--color-danger)' }}>✗</span>}
                    </td>
                    <td style={{ fontSize: 11, color: 'var(--color-text-secondary)' }}>
                      {row.error_detail ?? (row.changes ? '📋' : '—')}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>

            {totalPages > 1 && (
              <div className="pagination">
                <button
                  className="btn btn-sm btn-secondary"
                  disabled={currentPage === 1}
                  onClick={() => setSkip((p) => Math.max(0, p - PAGE_SIZE))}
                >←</button>
                <span className="pagination-info">
                  {currentPage} / {totalPages} ({total} kayıt)
                </span>
                <button
                  className="btn btn-sm btn-secondary"
                  disabled={currentPage >= totalPages}
                  onClick={() => setSkip((p) => p + PAGE_SIZE)}
                >→</button>
              </div>
            )}
          </>
        )}
      </div>

      {/* Changes modal */}
      {selected && (
        <div
          style={{
            position: 'fixed', inset: 0, background: 'rgba(0,0,0,.5)',
            display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000,
          }}
          onClick={() => setSelected(null)}
        >
          <div
            style={{
              background: 'var(--color-bg-surface)', borderRadius: 8, padding: 24,
              maxWidth: 640, width: '90%', maxHeight: '80vh', overflow: 'auto',
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
              <strong>{ACTION_LABELS[selected.action] ?? selected.action} — Değişiklikler</strong>
              <button className="btn btn-sm btn-secondary" onClick={() => setSelected(null)}>✕</button>
            </div>
            <pre style={{ fontSize: 12, overflow: 'auto', whiteSpace: 'pre-wrap' }}>
              {JSON.stringify(selected.changes, null, 2)}
            </pre>
          </div>
        </div>
      )}
    </AppShell>
  )
}
