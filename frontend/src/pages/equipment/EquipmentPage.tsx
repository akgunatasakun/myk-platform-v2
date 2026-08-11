import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import AppShell from '@/components/layout/AppShell'
import EquipmentFormModal from './EquipmentFormModal'
import { equipmentApi } from '@/api/equipment'
import type { Equipment, EquipmentListResponse, EquipmentStatus, MaintenanceDueEquipment } from '@/types/equipment'

const STATUS_LABEL: Record<string, string> = {
  aktif: 'Aktif',
  bakimda: 'Bakımda',
  hasarli: 'Hasarlı',
  hizmetdisi: 'Hizmet Dışı',
}

const STATUS_CLASS: Record<string, string> = {
  aktif: 'badge-aktif',
  bakimda: 'badge-bakimda',
  hasarli: 'badge-hasarli',
  hizmetdisi: 'badge-hizmetdisi',
}

const STATUS_OPTIONS: { value: EquipmentStatus | ''; label: string }[] = [
  { value: '', label: 'Tüm Durumlar' },
  { value: 'aktif', label: 'Aktif' },
  { value: 'bakimda', label: 'Bakımda' },
  { value: 'hasarli', label: 'Hasarlı' },
  { value: 'hizmetdisi', label: 'Hizmet Dışı' },
]

function fmt(date: string | null) {
  if (!date) return '—'
  return new Date(date + 'T00:00:00').toLocaleDateString('tr-TR')
}

type Tab = 'all' | 'due'

const PAGE_SIZE = 20

export default function EquipmentPage() {
  const navigate = useNavigate()

  const [tab, setTab] = useState<Tab>('all')
  const [data, setData] = useState<EquipmentListResponse | null>(null)
  const [dueItems, setDueItems] = useState<MaintenanceDueEquipment[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const [statusFilter, setStatusFilter] = useState<EquipmentStatus | ''>('')
  const [skip, setSkip] = useState(0)

  const [modalOpen, setModalOpen] = useState(false)
  const [editEquipment, setEditEquipment] = useState<Equipment | undefined>(undefined)

  const fetchAll = useCallback(async (status: string, skipVal: number) => {
    setLoading(true)
    setError(null)
    try {
      const params: Record<string, unknown> = { skip: skipVal, limit: PAGE_SIZE }
      if (status) params.status = status
      const resp = await equipmentApi.list(params)
      setData(resp.data)
    } catch {
      setError('Ekipmanlar yüklenemedi.')
    } finally {
      setLoading(false)
    }
  }, [])

  const fetchDue = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const resp = await equipmentApi.maintenanceDue()
      setDueItems(resp.data.items)
    } catch {
      setError('Bakım listesi yüklenemedi.')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    if (tab === 'all') {
      fetchAll(statusFilter, skip)
    } else {
      fetchDue()
    }
  }, [tab, statusFilter, skip, fetchAll, fetchDue])

  const handleSaved = (saved: Equipment) => {
    setData((prev) => {
      if (!prev) return prev
      const exists = prev.items.some((e) => e.id === saved.id)
      if (exists) return { ...prev, items: prev.items.map((e) => (e.id === saved.id ? saved : e)) }
      return { ...prev, items: [saved, ...prev.items], total: prev.total + 1 }
    })
  }

  const openCreate = () => {
    setEditEquipment(undefined)
    setModalOpen(true)
  }

  const openEdit = (eq: Equipment, e: React.MouseEvent) => {
    e.stopPropagation()
    setEditEquipment(eq)
    setModalOpen(true)
  }

  const handleDelete = async (eq: Equipment, e: React.MouseEvent) => {
    e.stopPropagation()
    if (!window.confirm(`"${eq.name}" ekipmanını silmek istiyor musunuz?`)) return
    try {
      await equipmentApi.delete(eq.id)
      setData((prev) =>
        prev
          ? { ...prev, items: prev.items.filter((x) => x.id !== eq.id), total: prev.total - 1 }
          : prev
      )
    } catch {
      alert('Silme işlemi sırasında hata oluştu.')
    }
  }

  const totalPages = data ? Math.ceil(data.total / PAGE_SIZE) : 0
  const currentPage = Math.floor(skip / PAGE_SIZE) + 1

  const renderRow = (eq: Equipment | MaintenanceDueEquipment) => {
    const isDue = tab === 'due'
    const dueEq = isDue ? (eq as MaintenanceDueEquipment) : null

    const maintDays = dueEq?.maintenance_due
      ? dueEq.maintenance_days_remaining !== null && dueEq.maintenance_days_remaining !== undefined
        ? dueEq.maintenance_days_remaining <= 0
          ? `${Math.abs(dueEq.maintenance_days_remaining)} gün gecikti`
          : `${dueEq.maintenance_days_remaining} gün kaldı`
        : 'Bakım gerekli'
      : null

    const insDays = dueEq?.insurance_due
      ? dueEq.insurance_days_remaining !== null && dueEq.insurance_days_remaining !== undefined
        ? dueEq.insurance_days_remaining <= 0
          ? `${Math.abs(dueEq.insurance_days_remaining)} gün gecikti`
          : `${dueEq.insurance_days_remaining} gün kaldı`
        : 'Sigorta gerekli'
      : null

    return (
      <tr
        key={eq.id}
        onClick={() => navigate(`/tekneler/${eq.id}`)}
        style={{ cursor: 'pointer' }}
      >
        <td>
          <strong>{eq.name}</strong>
          {eq.brand && <div style={{ fontSize: 12, color: 'var(--color-text-muted)' }}>{eq.brand}{eq.model ? ` / ${eq.model}` : ''}</div>}
        </td>
        <td>{eq.equipment_type ?? '—'}</td>
        <td>
          <span className={`badge ${STATUS_CLASS[eq.status] ?? ''}`}>
            {STATUS_LABEL[eq.status] ?? eq.status}
          </span>
        </td>
        <td>{eq.assigned_person_name ?? '—'}</td>
        <td>{fmt(eq.next_maintenance_date)}</td>
        {isDue && (
          <td>
            {maintDays && (
              <span style={{ fontSize: 12, color: (dueEq?.maintenance_days_remaining ?? 1) <= 0 ? 'var(--color-danger)' : 'var(--color-warning)', display: 'block' }}>
                🔧 {maintDays}
              </span>
            )}
            {insDays && (
              <span style={{ fontSize: 12, color: (dueEq?.insurance_days_remaining ?? 1) <= 0 ? 'var(--color-danger)' : 'var(--color-warning)', display: 'block' }}>
                🛡 {insDays}
              </span>
            )}
          </td>
        )}
        <td>
          <div style={{ display: 'flex', gap: 6 }} onClick={(e) => e.stopPropagation()}>
            <button className="btn btn-sm btn-secondary" onClick={(e) => openEdit(eq as Equipment, e)}>
              Düzenle
            </button>
            <button className="btn btn-sm btn-danger" onClick={(e) => handleDelete(eq as Equipment, e)}>
              🗑
            </button>
          </div>
        </td>
      </tr>
    )
  }

  const items = tab === 'all' ? (data?.items ?? []) : dueItems
  const isEmpty = !loading && items.length === 0

  return (
    <AppShell title="Ekipmanlar">
      <div className="page-header">
        <h1 className="page-title">Ekipmanlar</h1>
        <button className="btn btn-primary" onClick={openCreate}>
          + Yeni Ekipman
        </button>
      </div>

      {/* Tab */}
      <div style={{ display: 'flex', gap: 8, marginBottom: 16 }}>
        <button
          className={`btn btn-sm ${tab === 'all' ? 'btn-primary' : 'btn-ghost'}`}
          onClick={() => { setTab('all'); setSkip(0) }}
        >
          Tüm Ekipmanlar {data && `(${data.total})`}
        </button>
        <button
          className={`btn btn-sm ${tab === 'due' ? 'btn-primary' : 'btn-ghost'}`}
          onClick={() => setTab('due')}
        >
          ⚠️ Bakım/Sigorta Yaklaşanlar {tab === 'due' && `(${dueItems.length})`}
        </button>
      </div>

      {/* Filtreler (sadece "Tüm" tabında) */}
      {tab === 'all' && (
        <div className="filter-bar">
          <select
            className="form-select"
            style={{ width: 'auto', minWidth: 160 }}
            value={statusFilter}
            onChange={(e) => { setStatusFilter(e.target.value as EquipmentStatus | ''); setSkip(0) }}
          >
            {STATUS_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>{o.label}</option>
            ))}
          </select>
        </div>
      )}

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
            <div className="empty-state-icon">🛟</div>
            <div className="empty-state-title">
              {tab === 'due' ? 'Bakım/Sigorta Yaklaşan Ekipman Yok' : 'Ekipman Bulunamadı'}
            </div>
            <div className="empty-state-desc">
              {tab === 'all'
                ? 'Henüz kayıtlı ekipman yok. Yeni ekipman ekleyin.'
                : 'Yaklaşan bakım veya sigorta yenileme gereksinimi bulunmuyor.'}
            </div>
          </div>
        ) : (
          <>
            <table className="data-table">
              <thead>
                <tr>
                  <th>Ekipman</th>
                  <th>Tür</th>
                  <th>Durum</th>
                  <th>Zimmetli</th>
                  <th>Sonraki Bakım</th>
                  {tab === 'due' && <th>Uyarı</th>}
                  <th>İşlemler</th>
                </tr>
              </thead>
              <tbody>
                {items.map(renderRow)}
              </tbody>
            </table>

            {/* Pagination (sadece "all" tab) */}
            {tab === 'all' && data && data.total > PAGE_SIZE && (
              <div className="pagination">
                <span>
                  {data.total} ekipmandan {skip + 1}–{Math.min(skip + PAGE_SIZE, data.total)} arası gösteriliyor
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

      <EquipmentFormModal
        isOpen={modalOpen}
        onClose={() => setModalOpen(false)}
        equipment={editEquipment}
        onSaved={handleSaved}
      />
    </AppShell>
  )
}
