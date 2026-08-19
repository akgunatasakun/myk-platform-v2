import { useCallback, useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import AppShell from '@/components/layout/AppShell'
import MaintenanceFormModal from './MaintenanceFormModal'
import EquipmentFormModal from './EquipmentFormModal'
import { equipmentApi } from '@/api/equipment'
import type { Equipment, MaintenanceRecord } from '@/types/equipment'

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

function fmt(date: string | null) {
  if (!date) return '—'
  return new Date(date + 'T00:00:00').toLocaleDateString('tr-TR')
}

function fmtCost(val: string | null) {
  if (!val) return '—'
  return `${parseFloat(val).toLocaleString('tr-TR', { minimumFractionDigits: 2 })} ₺`
}

export default function EquipmentDetailPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()

  const [equipment, setEquipment] = useState<Equipment | null>(null)
  const [records, setRecords] = useState<MaintenanceRecord[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const [editOpen, setEditOpen] = useState(false)
  const [maintOpen, setMaintOpen] = useState(false)
  const [editRecord, setEditRecord] = useState<MaintenanceRecord | undefined>(undefined)

  const load = useCallback(async () => {
    if (!id) return
    setLoading(true)
    setError(null)
    try {
      const [eqResp, mResp] = await Promise.all([
        equipmentApi.get(id),
        equipmentApi.listMaintenance(id),
      ])
      setEquipment(eqResp.data)
      setRecords(mResp.data.items)
    } catch {
      setError('Ekipman yüklenemedi.')
    } finally {
      setLoading(false)
    }
  }, [id])

  useEffect(() => { load() }, [load])

  const handleDelete = async () => {
    if (!equipment) return
    if (!window.confirm(`"${equipment.name}" ekipmanını silmek istiyor musunuz?`)) return
    try {
      await equipmentApi.delete(equipment.id)
      navigate('/tekneler')
    } catch {
      alert('Silme işlemi sırasında hata oluştu.')
    }
  }

  const openEditRecord = (r: MaintenanceRecord) => {
    setEditRecord(r)
    setMaintOpen(true)
  }

  const openNewRecord = () => {
    setEditRecord(undefined)
    setMaintOpen(true)
  }

  const handleMaintSaved = (saved: MaintenanceRecord) => {
    setRecords((prev) => {
      const exists = prev.some((r) => r.id === saved.id)
      if (exists) return prev.map((r) => (r.id === saved.id ? saved : r))
      return [saved, ...prev]
    })
    // Ekipman summary güncelleme için tekrar yükle
    if (id) equipmentApi.get(id).then((r) => setEquipment(r.data)).catch(() => {})
  }

  if (loading) {
    return (
      <AppShell title="Ekipman Detayı">
        <div className="loading-center"><span className="loading-spinner lg" /></div>
      </AppShell>
    )
  }

  if (error || !equipment) {
    return (
      <AppShell title="Ekipman Detayı">
        <div className="alert alert-error"><span>⚠️</span><span>{error ?? 'Ekipman bulunamadı.'}</span></div>
      </AppShell>
    )
  }

  return (
    <AppShell title={equipment.name}>
      {/* Üst bar */}
      <div className="page-header">
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <button className="btn btn-ghost btn-sm" onClick={() => navigate('/tekneler')}>
            ← Geri
          </button>
          <h1 className="page-title" style={{ margin: 0 }}>{equipment.name}</h1>
          <span className={`badge ${STATUS_CLASS[equipment.status] ?? ''}`}>
            {STATUS_LABEL[equipment.status] ?? equipment.status}
          </span>
          {!equipment.is_active && <span className="badge badge-pasif">Pasif</span>}
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <button className="btn btn-secondary" onClick={() => setEditOpen(true)}>
            Düzenle
          </button>
          <button className="btn btn-danger" onClick={handleDelete}>
            Sil
          </button>
        </div>
      </div>

      {/* Bilgi kartları */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: 16, marginBottom: 24 }}>
        {/* Genel */}
        <div className="card">
          <div className="card-header"><div className="card-title">🚤 Genel Bilgiler</div></div>
          <div className="card-body">
            <Row label="Tür" value={equipment.equipment_type} />
            <Row label="Marka" value={equipment.brand} />
            <Row label="Model" value={equipment.model} />
            <Row label="Seri No" value={equipment.serial_no} />
          </div>
        </div>

        {/* Satın Alma */}
        <div className="card">
          <div className="card-header"><div className="card-title">💰 Satın Alma</div></div>
          <div className="card-body">
            <Row label="Tarih" value={fmt(equipment.purchase_date)} />
            <Row label="Bedel" value={fmtCost(equipment.purchase_cost)} />
          </div>
        </div>

        {/* Zimmet */}
        <div className="card">
          <div className="card-header"><div className="card-title">👤 Zimmet</div></div>
          <div className="card-body">
            <Row label="Zimmetli" value={equipment.assigned_person_name} />
          </div>
        </div>

        {/* Bakım */}
        <div className="card">
          <div className="card-header"><div className="card-title">🔧 Bakım & Sigorta</div></div>
          <div className="card-body">
            <Row label="Son Bakım" value={fmt(equipment.last_maintenance_date)} />
            <Row label="Sonraki Bakım" value={fmt(equipment.next_maintenance_date)} />
            <Row label="Sigorta Bitişi" value={fmt(equipment.insurance_expiry_date)} />
          </div>
        </div>
      </div>

      {equipment.notes && (
        <div className="card" style={{ marginBottom: 24 }}>
          <div className="card-header"><div className="card-title">📝 Notlar</div></div>
          <div className="card-body">
            <p style={{ margin: 0, whiteSpace: 'pre-wrap' }}>{equipment.notes}</p>
          </div>
        </div>
      )}

      {/* Bakım Geçmişi */}
      <div className="page-header" style={{ marginBottom: 12 }}>
        <h2 style={{ fontSize: 18, fontWeight: 700, margin: 0 }}>🗂 Bakım Geçmişi</h2>
        <button className="btn btn-primary btn-sm" onClick={openNewRecord}>
          + Yeni Bakım Kaydı
        </button>
      </div>

      <div className="table-container">
        {records.length === 0 ? (
          <div className="empty-state">
            <div className="empty-state-icon">🔧</div>
            <div className="empty-state-title">Bakım Kaydı Yok</div>
            <div className="empty-state-desc">Bu ekipman için henüz bakım kaydı eklenmemiş.</div>
          </div>
        ) : (
          <table className="data-table">
            <thead>
              <tr>
                <th>Tarih</th>
                <th>Tür</th>
                <th>Açıklama</th>
                <th>Maliyet</th>
                <th>Yapan</th>
                <th>Sonraki Bakım</th>
                <th>İşlem</th>
              </tr>
            </thead>
            <tbody>
              {records.map((r) => (
                <tr key={r.id}>
                  <td>{fmt(r.maintenance_date)}</td>
                  <td>{r.maintenance_type ?? '—'}</td>
                  <td>{r.description ?? '—'}</td>
                  <td>{fmtCost(r.cost)}</td>
                  <td>{r.performed_by ?? '—'}</td>
                  <td>{fmt(r.next_maintenance_date)}</td>
                  <td>
                    <button
                      className="btn btn-sm btn-secondary"
                      onClick={() => openEditRecord(r)}
                    >
                      Düzenle
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <EquipmentFormModal
        isOpen={editOpen}
        onClose={() => setEditOpen(false)}
        equipment={equipment}
        onSaved={(saved) => setEquipment(saved)}
      />

      <MaintenanceFormModal
        isOpen={maintOpen}
        onClose={() => setMaintOpen(false)}
        equipmentId={equipment.id}
        record={editRecord}
        onSaved={handleMaintSaved}
      />
    </AppShell>
  )
}

function Row({ label, value }: { label: string; value: string | null | undefined }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', padding: '6px 0', borderBottom: '1px solid var(--color-border)' }}>
      <span style={{ color: 'var(--color-text-muted)', fontSize: 13 }}>{label}</span>
      <span style={{ fontWeight: 500, fontSize: 13 }}>{value || '—'}</span>
    </div>
  )
}
