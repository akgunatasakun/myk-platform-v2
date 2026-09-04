/**
 * /sporcular — Sporcu listesi
 *
 * Backend: GET /api/v1/athletes
 * Özellikler:
 *   - Arama (isim)
 *   - Aktif/pasif filtresi
 *   - Uyarı sekmesi (belge/lisans/vize dolmak üzere veya eksik)
 *   - Satıra tıkla → /sporcular/:person_id
 */
import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import AppShell from '@/components/layout/AppShell'
import { athletesApi } from '@/api/athletes'
import type { AthleteAlertItem, AthleteListItem, DocumentStatus } from '@/types/athlete'
import { formatPersonAge } from '@/utils/personAge'

const PAGE_SIZE = 20

function DocBadge({ status }: { status: DocumentStatus }) {
  if (status === 'gecerli') return <span style={{ color: 'var(--color-success)', fontWeight: 700 }}>✓</span>
  if (status === 'yaklasan') return <span style={{ color: 'var(--color-warning)', fontWeight: 700 }}>!</span>
  if (status === 'dolmus') return <span style={{ color: 'var(--color-danger)', fontWeight: 700 }}>✗</span>
  return <span style={{ color: 'var(--color-text-muted)' }}>—</span>
}

function fmtDate(d?: string | null) {
  if (!d) return '—'
  return new Date(d + 'T00:00:00').toLocaleDateString('tr-TR')
}

type Tab = 'list' | 'alerts'

export default function AthletesPage() {
  const navigate = useNavigate()
  const [tab, setTab] = useState<Tab>('list')

  // List tab
  const [items, setItems] = useState<AthleteListItem[]>([])
  const [total, setTotal] = useState(0)
  const [skip, setSkip] = useState(0)
  const [search, setSearch] = useState('')
  const [isActive, setIsActive] = useState<boolean | undefined>(true)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // Alerts tab
  const [alerts, setAlerts] = useState<AthleteAlertItem[]>([])
  const [alertsLoading, setAlertsLoading] = useState(false)

  const fetchList = useCallback(async (q: string, active: boolean | undefined, s: number) => {
    setLoading(true)
    setError(null)
    try {
      const params: Record<string, unknown> = { skip: s, limit: PAGE_SIZE }
      if (q) params.search = q
      if (active !== undefined) params.is_active = active
      const r = await athletesApi.list(params)
      setItems(r.data.items)
      setTotal(r.data.total)
    } catch {
      setError('Sporcular yüklenemedi.')
    } finally {
      setLoading(false)
    }
  }, [])

  const fetchAlerts = useCallback(async () => {
    setAlertsLoading(true)
    try {
      const r = await athletesApi.alerts()
      setAlerts(r.data)
    } catch {
      // sessizce geç
    } finally {
      setAlertsLoading(false)
    }
  }, [])

  useEffect(() => {
    if (tab === 'list') fetchList(search, isActive, skip)
    else fetchAlerts()
  }, [tab, search, isActive, skip, fetchList, fetchAlerts])

  const totalPages = Math.ceil(total / PAGE_SIZE)
  const currentPage = Math.floor(skip / PAGE_SIZE) + 1

  return (
    <AppShell title="Sporcular">
      <div className="page-header">
        <h1 className="page-title">Sporcular</h1>
      </div>

      {/* Tabs */}
      <div style={{ display: 'flex', gap: 8, marginBottom: 16 }}>
        <button
          className={`btn btn-sm ${tab === 'list' ? 'btn-primary' : 'btn-ghost'}`}
          onClick={() => setTab('list')}
        >
          Tüm Sporcular {tab === 'list' && total > 0 && `(${total})`}
        </button>
        <button
          className={`btn btn-sm ${tab === 'alerts' ? 'btn-primary' : 'btn-ghost'}`}
          onClick={() => setTab('alerts')}
          style={tab !== 'alerts' && alerts.length > 0 ? { color: 'var(--color-danger)', borderColor: 'var(--color-danger)' } : {}}
        >
          ⚠️ Uyarılar {alerts.length > 0 && `(${alerts.length})`}
        </button>
      </div>

      {tab === 'list' && (
        <>
          {/* Filtreler */}
          <div className="filter-bar" style={{ marginBottom: 16 }}>
            <input
              className="form-input"
              style={{ maxWidth: 280 }}
              placeholder="İsim ara…"
              value={search}
              onChange={(e) => { setSearch(e.target.value); setSkip(0) }}
            />
            <select
              className="form-select"
              style={{ width: 'auto' }}
              value={isActive === undefined ? '' : String(isActive)}
              onChange={(e) => {
                const v = e.target.value
                setIsActive(v === '' ? undefined : v === 'true')
                setSkip(0)
              }}
            >
              <option value="true">Aktif</option>
              <option value="false">Pasif</option>
              <option value="">Tümü</option>
            </select>
          </div>

          {error && <div className="alert alert-error"><span>⚠️</span><span>{error}</span></div>}

          <div className="table-container">
            {loading ? (
              <div className="loading-center"><span className="loading-spinner lg" /></div>
            ) : items.length === 0 ? (
              <div className="empty-state">
                <div className="empty-state-icon">⛵</div>
                <div className="empty-state-title">Sporcu Bulunamadı</div>
                <div className="empty-state-desc">Henüz sporcu rolü atanmış kişi yok.</div>
              </div>
            ) : (
              <>
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Sporcu</th>
                      <th>Sınıf / Seviye</th>
                      <th>Lisans</th>
                      <th>Vize</th>
                      <th>Sağlık</th>
                      <th>Lisans No</th>
                      <th>Durum</th>
                    </tr>
                  </thead>
                  <tbody>
                    {items.map((a) => (
                      <tr
                        key={a.person_id}
                        style={{ cursor: 'pointer' }}
                        onClick={() => navigate(`/sporcular/${a.person_id}`)}
                      >
                        <td>
                          <div style={{ fontWeight: 600 }}>
                            {a.first_name} {a.last_name}
                          </div>
                          <div style={{ fontSize: 11, color: 'var(--color-text-muted)' }}>
                            {formatPersonAge(a.birth_date)}
                          </div>
                          {!a.has_profile && (
                            <div style={{ fontSize: 11, color: 'var(--color-warning)' }}>profil eksik</div>
                          )}
                        </td>
                        <td>
                          <div>{a.class_name ?? '—'}</div>
                          {a.level && (
                            <div style={{ fontSize: 11, color: 'var(--color-text-muted)' }}>{a.level}</div>
                          )}
                        </td>
                        <td>
                          <DocBadge status={a.license_status} />
                          {a.license_expiry_date && (
                            <div style={{ fontSize: 11, color: 'var(--color-text-muted)' }}>
                              {fmtDate(a.license_expiry_date)}
                            </div>
                          )}
                        </td>
                        <td>
                          <DocBadge status={a.visa_status} />
                          {a.visa_expiry_date && (
                            <div style={{ fontSize: 11, color: 'var(--color-text-muted)' }}>
                              {fmtDate(a.visa_expiry_date)}
                            </div>
                          )}
                        </td>
                        <td>
                          <DocBadge status={a.health_status} />
                          {a.health_report_expiry_date && (
                            <div style={{ fontSize: 11, color: 'var(--color-text-muted)' }}>
                              {fmtDate(a.health_report_expiry_date)}
                            </div>
                          )}
                        </td>
                        <td style={{ fontSize: 13 }}>{a.license_no ?? '—'}</td>
                        <td>
                          <span className={`badge ${a.is_active ? 'badge-aktif' : 'badge-pasif'}`}>
                            {a.is_active ? 'Aktif' : 'Pasif'}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>

                {total > PAGE_SIZE && (
                  <div className="pagination">
                    <span>{total} kayıttan {skip + 1}–{Math.min(skip + PAGE_SIZE, total)} arası</span>
                    <div className="pagination-controls">
                      <button
                        className="btn btn-sm btn-secondary"
                        disabled={skip === 0}
                        onClick={() => setSkip((s) => Math.max(0, s - PAGE_SIZE))}
                      >← Önceki</button>
                      <span style={{ padding: '5px 10px', fontSize: 13 }}>{currentPage} / {totalPages}</span>
                      <button
                        className="btn btn-sm btn-secondary"
                        disabled={skip + PAGE_SIZE >= total}
                        onClick={() => setSkip((s) => s + PAGE_SIZE)}
                      >Sonraki →</button>
                    </div>
                  </div>
                )}
              </>
            )}
          </div>
        </>
      )}

      {tab === 'alerts' && (
        <>
          {alertsLoading ? (
            <div className="loading-center"><span className="loading-spinner lg" /></div>
          ) : alerts.length === 0 ? (
            <div className="empty-state">
              <div className="empty-state-icon">✅</div>
              <div className="empty-state-title">Uyarı Yok</div>
              <div className="empty-state-desc">Tüm sporcuların belgeleri güncel.</div>
            </div>
          ) : (
            <div className="table-container">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Sporcu</th>
                    <th>Sınıf</th>
                    <th>Lisans</th>
                    <th>Vize</th>
                    <th>Sağlık</th>
                    <th>Uyarılar</th>
                  </tr>
                </thead>
                <tbody>
                  {alerts.map((a) => (
                    <tr
                      key={a.person_id}
                      style={{ cursor: 'pointer' }}
                      onClick={() => navigate(`/sporcular/${a.person_id}`)}
                    >
                      <td>
                        <strong>{a.first_name} {a.last_name}</strong>
                      </td>
                      <td>{a.class_name ?? '—'}</td>
                      <td>
                        <DocBadge status={a.license_status} />
                        {a.license_expiry_date && (
                          <div style={{ fontSize: 11, color: 'var(--color-text-muted)' }}>{fmtDate(a.license_expiry_date)}</div>
                        )}
                      </td>
                      <td>
                        <DocBadge status={a.visa_status} />
                        {a.visa_expiry_date && (
                          <div style={{ fontSize: 11, color: 'var(--color-text-muted)' }}>{fmtDate(a.visa_expiry_date)}</div>
                        )}
                      </td>
                      <td>
                        <DocBadge status={a.health_status} />
                        {a.health_report_expiry_date && (
                          <div style={{ fontSize: 11, color: 'var(--color-text-muted)' }}>{fmtDate(a.health_report_expiry_date)}</div>
                        )}
                      </td>
                      <td>
                        <div style={{ fontSize: 12 }}>
                          {a.alerts.map((msg, i) => (
                            <div key={i} style={{ color: 'var(--color-danger)' }}>• {msg}</div>
                          ))}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}
    </AppShell>
  )
}
