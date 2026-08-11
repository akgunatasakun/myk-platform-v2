import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import AppShell from '@/components/layout/AppShell'
import TrainingFormModal from './TrainingFormModal'
import { trainingApi } from '@/api/training'
import type { TrainingCourse, TrainingCourseListResponse, CourseStatus } from '@/types/training'

const STATUS_LABEL: Record<string, string> = {
  planlandi: 'Planlandı',
  aktif: 'Aktif',
  tamamlandi: 'Tamamlandı',
  iptal: 'İptal',
}

const STATUS_CLASS: Record<string, string> = {
  planlandi: 'badge-planlandi',
  aktif: 'badge-aktif',
  tamamlandi: 'badge-tamamlandi',
  iptal: 'badge-iptal',
}

const STATUS_OPTIONS: { value: CourseStatus | ''; label: string }[] = [
  { value: '', label: 'Tüm Durumlar' },
  { value: 'planlandi', label: 'Planlandı' },
  { value: 'aktif', label: 'Aktif' },
  { value: 'tamamlandi', label: 'Tamamlandı' },
  { value: 'iptal', label: 'İptal' },
]

function fmt(date: string | null) {
  if (!date) return '—'
  return new Date(date + 'T00:00:00').toLocaleDateString('tr-TR')
}

function fmtFee(fee: string) {
  const n = parseFloat(fee)
  if (!n) return 'Ücretsiz'
  return `${n.toLocaleString('tr-TR', { minimumFractionDigits: 0 })} ₺`
}

const PAGE_SIZE = 20

export default function TrainingPage() {
  const navigate = useNavigate()

  const [data, setData] = useState<TrainingCourseListResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const [statusFilter, setStatusFilter] = useState<CourseStatus | ''>('')
  const [activeOnly, setActiveOnly] = useState(true)
  const [skip, setSkip] = useState(0)

  const [modalOpen, setModalOpen] = useState(false)
  const [editCourse, setEditCourse] = useState<TrainingCourse | undefined>(undefined)

  const fetch = useCallback(async (status: string, active: boolean, skipVal: number) => {
    setLoading(true)
    setError(null)
    try {
      const params: Record<string, unknown> = {
        skip: skipVal,
        limit: PAGE_SIZE,
        active_only: active,
      }
      if (status) params.status = status
      const resp = await trainingApi.listCourses(params)
      setData(resp.data)
    } catch {
      setError('Eğitimler yüklenemedi.')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetch(statusFilter, activeOnly, skip)
  }, [statusFilter, activeOnly, skip, fetch])

  const handleSaved = (saved: TrainingCourse) => {
    setData((prev) => {
      if (!prev) return prev
      const exists = prev.items.some((c) => c.id === saved.id)
      if (exists) return { ...prev, items: prev.items.map((c) => (c.id === saved.id ? saved : c)) }
      return { ...prev, items: [saved, ...prev.items], total: prev.total + 1 }
    })
  }

  const handleDelete = async (course: TrainingCourse, e: React.MouseEvent) => {
    e.stopPropagation()
    if (!window.confirm(`"${course.name}" eğitimini silmek istiyor musunuz?`)) return
    try {
      await trainingApi.deleteCourse(course.id)
      setData((prev) =>
        prev
          ? { ...prev, items: prev.items.filter((c) => c.id !== course.id), total: prev.total - 1 }
          : prev
      )
    } catch {
      alert('Silme işlemi sırasında hata oluştu.')
    }
  }

  const openCreate = () => { setEditCourse(undefined); setModalOpen(true) }
  const openEdit = (course: TrainingCourse, e: React.MouseEvent) => {
    e.stopPropagation()
    setEditCourse(course)
    setModalOpen(true)
  }

  const totalPages = data ? Math.ceil(data.total / PAGE_SIZE) : 0
  const currentPage = Math.floor(skip / PAGE_SIZE) + 1
  const items = data?.items ?? []
  const isEmpty = !loading && items.length === 0

  return (
    <AppShell title="Eğitimler">
      <div className="page-header">
        <h1 className="page-title">Eğitimler</h1>
        <button className="btn btn-primary" onClick={openCreate}>
          + Yeni Eğitim
        </button>
      </div>

      <div className="filter-bar">
        <select
          className="form-select"
          style={{ width: 'auto', minWidth: 160 }}
          value={statusFilter}
          onChange={(e) => { setStatusFilter(e.target.value as CourseStatus | ''); setSkip(0) }}
        >
          {STATUS_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>{o.label}</option>
          ))}
        </select>

        <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 14, cursor: 'pointer' }}>
          <input
            type="checkbox"
            checked={activeOnly}
            onChange={(e) => { setActiveOnly(e.target.checked); setSkip(0) }}
          />
          Sadece aktif eğitimler
        </label>
      </div>

      {error && (
        <div className="alert alert-error">
          <span>⚠️</span><span>{error}</span>
        </div>
      )}

      <div className="table-container">
        {loading ? (
          <div className="loading-center"><span className="loading-spinner lg" /></div>
        ) : isEmpty ? (
          <div className="empty-state">
            <div className="empty-state-icon">📚</div>
            <div className="empty-state-title">Eğitim Bulunamadı</div>
            <div className="empty-state-desc">
              {activeOnly
                ? 'Aktif eğitim yok. Filtreyi kaldırın veya yeni eğitim ekleyin.'
                : 'Henüz kayıtlı eğitim yok. Yeni eğitim ekleyin.'}
            </div>
          </div>
        ) : (
          <>
            <table className="data-table">
              <thead>
                <tr>
                  <th>Eğitim</th>
                  <th>Sınıf / Seviye</th>
                  <th>Eğitmen</th>
                  <th>Tarihler</th>
                  <th>Katılımcı</th>
                  <th>Ücret</th>
                  <th>Durum</th>
                  <th>İşlemler</th>
                </tr>
              </thead>
              <tbody>
                {items.map((c) => (
                  <tr
                    key={c.id}
                    onClick={() => navigate(`/egitimler/${c.id}`)}
                    style={{ cursor: 'pointer' }}
                  >
                    <td>
                      <strong>{c.name}</strong>
                      {c.schedule_text && (
                        <div style={{ fontSize: 12, color: 'var(--color-text-muted)' }}>
                          {c.schedule_text}
                        </div>
                      )}
                    </td>
                    <td>
                      {c.class_name && <div>{c.class_name}</div>}
                      {c.level && <div style={{ fontSize: 12, color: 'var(--color-text-muted)' }}>{c.level}</div>}
                      {!c.class_name && !c.level && '—'}
                    </td>
                    <td>{c.instructor_name ?? '—'}</td>
                    <td>
                      {c.start_date
                        ? <>{fmt(c.start_date)}{c.end_date ? ` – ${fmt(c.end_date)}` : ''}</>
                        : '—'}
                    </td>
                    <td>
                      {c.capacity > 0
                        ? `${c.enrollment_count} / ${c.capacity}`
                        : c.enrollment_count}
                    </td>
                    <td>{fmtFee(c.fee)}</td>
                    <td>
                      <span className={`badge ${STATUS_CLASS[c.status] ?? ''}`}>
                        {STATUS_LABEL[c.status] ?? c.status}
                      </span>
                    </td>
                    <td>
                      <div style={{ display: 'flex', gap: 6 }} onClick={(e) => e.stopPropagation()}>
                        <button className="btn btn-sm btn-secondary" onClick={(e) => openEdit(c, e)}>
                          Düzenle
                        </button>
                        <button className="btn btn-sm btn-danger" onClick={(e) => handleDelete(c, e)}>
                          🗑
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>

            {data && data.total > PAGE_SIZE && (
              <div className="pagination">
                <span>
                  {data.total} eğitimden {skip + 1}–{Math.min(skip + PAGE_SIZE, data.total)} arası gösteriliyor
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

      <TrainingFormModal
        isOpen={modalOpen}
        onClose={() => setModalOpen(false)}
        course={editCourse}
        onSaved={handleSaved}
      />
    </AppShell>
  )
}
