import { useCallback, useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import AppShell from '@/components/layout/AppShell'
import { applicationsApi } from '@/api/applications'
import type { ApplicationListResponse, ApplicationStatus } from '@/types/application'

// ─── Durum meta bilgileri ─────────────────────────────────────────────────────

interface StatusMeta {
  label: string
  badgeClass: string
}

const STATUS_META: Record<ApplicationStatus, StatusMeta> = {
  draft:     { label: 'Taslak',    badgeClass: 'badge-status-draft'     },
  submitted: { label: 'Beklemede', badgeClass: 'badge-status-submitted' },
  approved:  { label: 'Onaylandı', badgeClass: 'badge-status-approved'  },
  rejected:  { label: 'Reddedildi', badgeClass: 'badge-status-rejected' },
  cancelled: { label: 'İptal',     badgeClass: 'badge-status-cancelled' },
}

function StatusBadge({ status }: { status: ApplicationStatus }) {
  const meta = STATUS_META[status] ?? { label: status, badgeClass: 'badge-default' }
  return <span className={`badge ${meta.badgeClass}`}>{meta.label}</span>
}

// ─── Yardımcı: tarih formatlama ───────────────────────────────────────────────

function formatDate(iso: string | null | undefined): string {
  if (!iso) return '—'
  return new Date(iso).toLocaleDateString('tr-TR', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
  })
}

// ─── Sayfa ────────────────────────────────────────────────────────────────────

const PAGE_SIZE = 20

const STATUS_FILTER_OPTIONS: Array<{ value: string; label: string }> = [
  { value: '',          label: 'Tüm Durumlar' },
  { value: 'submitted', label: 'Beklemede'    },
  { value: 'approved',  label: 'Onaylandı'   },
  { value: 'rejected',  label: 'Reddedildi'  },
  { value: 'cancelled', label: 'İptal'        },
  { value: 'draft',     label: 'Taslak'       },
]

export default function ApplicationsPage() {
  const navigate = useNavigate()

  const [data, setData] = useState<ApplicationListResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const [statusFilter, setStatusFilter] = useState('')
  const [skip, setSkip] = useState(0)

  // Status filter değişince skip'i sıfırla
  const prevStatusRef = useRef(statusFilter)

  const fetchApplications = useCallback(
    async (status: string, skipVal: number) => {
      setLoading(true)
      setError(null)
      try {
        const params: Record<string, unknown> = { skip: skipVal, limit: PAGE_SIZE }
        if (status) params.status = status
        const resp = await applicationsApi.list(params)
        setData(resp.data)
      } catch {
        setError('Başvurular yüklenemedi.')
      } finally {
        setLoading(false)
      }
    },
    []
  )

  // Status filter değişince sayfa 0'a dön
  useEffect(() => {
    if (prevStatusRef.current !== statusFilter) {
      prevStatusRef.current = statusFilter
      setSkip(0)
      fetchApplications(statusFilter, 0)
    }
  }, [statusFilter, fetchApplications])

  // İlk yükleme ve skip değişimi
  useEffect(() => {
    fetchApplications(statusFilter, skip)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [skip])

  const totalPages = data ? Math.ceil(data.total / PAGE_SIZE) : 0
  const currentPage = Math.floor(skip / PAGE_SIZE) + 1

  return (
    <AppShell title="Üyelik Başvuruları">
      <div className="page-header">
        <h1 className="page-title">Üyelik Başvuruları</h1>
        {data && (
          <span style={{ color: 'var(--color-muted)', fontSize: 13 }}>
            {data.total} başvuru
          </span>
        )}
      </div>

      {/* Status filtre tab'ları */}
      <div className="app-filter-tabs" role="tablist" aria-label="Durum filtresi">
        {STATUS_FILTER_OPTIONS.map((opt) => (
          <button
            key={opt.value}
            role="tab"
            aria-selected={statusFilter === opt.value}
            className={`app-filter-tab${statusFilter === opt.value ? ' active' : ''}`}
            onClick={() => setStatusFilter(opt.value)}
          >
            {opt.label}
          </button>
        ))}
      </div>

      {/* Error */}
      {error && (
        <div className="alert alert-error">
          <span>⚠️</span>
          <span>{error}</span>
          <button
            className="btn btn-sm btn-secondary"
            style={{ marginLeft: 'auto' }}
            onClick={() => fetchApplications(statusFilter, skip)}
          >
            Tekrar Dene
          </button>
        </div>
      )}

      {/* Table */}
      <div className="table-container">
        {loading ? (
          <div className="loading-center">
            <span className="loading-spinner lg" />
          </div>
        ) : !data || data.items.length === 0 ? (
          <div className="empty-state">
            <div className="empty-state-icon">📋</div>
            <div className="empty-state-title">Başvuru Bulunamadı</div>
            <div className="empty-state-desc">
              {statusFilter
                ? `"${STATUS_META[statusFilter as ApplicationStatus]?.label ?? statusFilter}" durumunda başvuru yok.`
                : 'Henüz üyelik başvurusu yapılmamış.'}
            </div>
          </div>
        ) : (
          <>
            <table className="data-table">
              <thead>
                <tr>
                  <th>Başvuru No</th>
                  <th>Ad Soyad</th>
                  <th>Tarih</th>
                  <th>Durum</th>
                </tr>
              </thead>
              <tbody>
                {data.items.map((app) => (
                  <tr
                    key={app.id}
                    onClick={() => navigate(`/admin/applications/${app.id}`)}
                    style={{ cursor: 'pointer' }}
                  >
                    <td>
                      <span style={{ fontFamily: 'monospace', fontSize: 12 }}>
                        {app.application_number ?? '—'}
                      </span>
                    </td>
                    <td>
                      <strong>
                        {app.first_name || app.last_name
                          ? `${app.first_name ?? ''} ${app.last_name ?? ''}`.trim()
                          : '—'}
                      </strong>
                    </td>
                    <td>
                      <span style={{ whiteSpace: 'nowrap' }}>
                        {formatDate(app.submitted_at ?? app.created_at)}
                      </span>
                    </td>
                    <td>
                      <StatusBadge status={app.status} />
                      {app.program_preference && (
                        <span className="badge badge-default" style={{ marginLeft: 6, fontSize: 11 }}>
                          {app.program_preference.toUpperCase()}
                        </span>
                      )}
                      {app.preferred_course_name && (
                        <div style={{ marginTop: 5, fontSize: 12, color: 'var(--color-muted)' }}>
                          Eğitim: {app.preferred_course_name}
                        </div>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>

            {/* Pagination */}
            {data.total > PAGE_SIZE && (
              <div className="pagination">
                <span>
                  {data.total} başvurudan {skip + 1}–{Math.min(skip + PAGE_SIZE, data.total)} arası
                  gösteriliyor
                </span>
                <div className="pagination-controls">
                  <button
                    className="btn btn-sm btn-secondary"
                    disabled={skip === 0}
                    onClick={() => setSkip((s) => Math.max(0, s - PAGE_SIZE))}
                  >
                    ← Önceki
                  </button>
                  <span style={{ padding: '5px 10px', fontSize: 13 }}>
                    {currentPage} / {totalPages}
                  </span>
                  <button
                    className="btn btn-sm btn-secondary"
                    disabled={skip + PAGE_SIZE >= data.total}
                    onClick={() => setSkip((s) => s + PAGE_SIZE)}
                  >
                    Sonraki →
                  </button>
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </AppShell>
  )
}
