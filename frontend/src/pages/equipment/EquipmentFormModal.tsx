import { useEffect, useState } from 'react'
import { equipmentApi } from '@/api/equipment'
import { personsApi } from '@/api/persons'
import { PERSON_LIST_LIMIT } from '@/api/constants'
import type { Equipment, EquipmentCreate, EquipmentStatus, EquipmentUpdate } from '@/types/equipment'
import type { Person } from '@/types/person'

interface Props {
  isOpen: boolean
  onClose: () => void
  equipment?: Equipment
  onSaved: (saved: Equipment) => void
}

const STATUS_OPTIONS: { value: EquipmentStatus; label: string }[] = [
  { value: 'aktif', label: 'Aktif' },
  { value: 'bakimda', label: 'Bakımda' },
  { value: 'hasarli', label: 'Hasarlı' },
  { value: 'hizmetdisi', label: 'Hizmet Dışı' },
]

function emptyForm() {
  return {
    name: '',
    equipment_type: '',
    serial_no: '',
    brand: '',
    model: '',
    purchase_date: '',
    purchase_cost: '',
    status: 'aktif' as EquipmentStatus,
    assigned_person_id: '',
    last_maintenance_date: '',
    next_maintenance_date: '',
    insurance_expiry_date: '',
    notes: '',
    is_active: true,
  }
}

export default function EquipmentFormModal({ isOpen, onClose, equipment, onSaved }: Props) {
  const isEdit = !!equipment
  const [form, setForm] = useState(emptyForm())
  const [persons, setPersons] = useState<Person[]>([])
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!isOpen) return

    if (equipment) {
      setForm({
        name: equipment.name,
        equipment_type: equipment.equipment_type ?? '',
        serial_no: equipment.serial_no ?? '',
        brand: equipment.brand ?? '',
        model: equipment.model ?? '',
        purchase_date: equipment.purchase_date ?? '',
        purchase_cost: equipment.purchase_cost ?? '',
        status: equipment.status,
        assigned_person_id: equipment.assigned_person_id ?? '',
        last_maintenance_date: equipment.last_maintenance_date ?? '',
        next_maintenance_date: equipment.next_maintenance_date ?? '',
        insurance_expiry_date: equipment.insurance_expiry_date ?? '',
        notes: equipment.notes ?? '',
        is_active: equipment.is_active,
      })
    } else {
      setForm(emptyForm())
    }
    setError(null)

    // Person listesini yükle (zimmet için)
    personsApi.list({ limit: PERSON_LIST_LIMIT, is_active: true })
      .then((r) => setPersons(r.data.items))
      .catch((err) => console.error('Kişi listesi yüklenemedi:', err))
  }, [isOpen, equipment])

  const set = (field: string, value: unknown) =>
    setForm((f) => ({ ...f, [field]: value }))

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setSaving(true)
    setError(null)

    const nullStr = (v: string) => v.trim() || null
    const nullNum = (v: string) => (v.trim() ? parseFloat(v) : null)

    const payload: EquipmentCreate | EquipmentUpdate = {
      name: form.name.trim(),
      equipment_type: nullStr(form.equipment_type),
      serial_no: nullStr(form.serial_no),
      brand: nullStr(form.brand),
      model: nullStr(form.model),
      purchase_date: nullStr(form.purchase_date),
      purchase_cost: nullNum(form.purchase_cost),
      status: form.status,
      assigned_person_id: nullStr(form.assigned_person_id),
      last_maintenance_date: nullStr(form.last_maintenance_date),
      next_maintenance_date: nullStr(form.next_maintenance_date),
      insurance_expiry_date: nullStr(form.insurance_expiry_date),
      notes: nullStr(form.notes),
      is_active: form.is_active,
    }

    try {
      let saved: Equipment
      if (isEdit) {
        const resp = await equipmentApi.update(equipment.id, payload)
        saved = resp.data
      } else {
        const resp = await equipmentApi.create(payload as EquipmentCreate)
        saved = resp.data
      }
      onSaved(saved)
      onClose()
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      setError(typeof msg === 'string' ? msg : 'Kayıt sırasında hata oluştu.')
    } finally {
      setSaving(false)
    }
  }

  if (!isOpen) return null

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" style={{ maxWidth: 640 }} onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2 className="modal-title">{isEdit ? 'Ekipmanı Düzenle' : 'Yeni Ekipman'}</h2>
          <button className="modal-close" onClick={onClose}>✕</button>
        </div>

        {error && (
          <div className="alert alert-error" style={{ margin: '0 0 16px' }}>
            <span>⚠️</span><span>{error}</span>
          </div>
        )}

        <form onSubmit={handleSubmit}>
          <div className="modal-body">
            {/* Zorunlu */}
            <div className="form-group">
              <label className="form-label">Ad *</label>
              <input
                className="form-input"
                value={form.name}
                onChange={(e) => set('name', e.target.value)}
                required
                placeholder="Örn: Optimist 01"
              />
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
              <div className="form-group">
                <label className="form-label">Ekipman Türü</label>
                <input
                  className="form-input"
                  value={form.equipment_type}
                  onChange={(e) => set('equipment_type', e.target.value)}
                  placeholder="Tekne, yelken, can yeleği…"
                />
              </div>
              <div className="form-group">
                <label className="form-label">Seri No</label>
                <input
                  className="form-input"
                  value={form.serial_no}
                  onChange={(e) => set('serial_no', e.target.value)}
                  placeholder="Opsiyonel"
                />
              </div>

              <div className="form-group">
                <label className="form-label">Marka</label>
                <input
                  className="form-input"
                  value={form.brand}
                  onChange={(e) => set('brand', e.target.value)}
                />
              </div>
              <div className="form-group">
                <label className="form-label">Model</label>
                <input
                  className="form-input"
                  value={form.model}
                  onChange={(e) => set('model', e.target.value)}
                />
              </div>

              <div className="form-group">
                <label className="form-label">Satın Alma Tarihi</label>
                <input
                  type="date"
                  className="form-input"
                  value={form.purchase_date}
                  onChange={(e) => set('purchase_date', e.target.value)}
                />
              </div>
              <div className="form-group">
                <label className="form-label">Satın Alma Bedeli (₺)</label>
                <input
                  type="number"
                  min="0"
                  step="0.01"
                  className="form-input"
                  value={form.purchase_cost}
                  onChange={(e) => set('purchase_cost', e.target.value)}
                  placeholder="0.00"
                />
              </div>

              <div className="form-group">
                <label className="form-label">Durum</label>
                <select
                  className="form-select"
                  value={form.status}
                  onChange={(e) => set('status', e.target.value as EquipmentStatus)}
                >
                  {STATUS_OPTIONS.map((o) => (
                    <option key={o.value} value={o.value}>{o.label}</option>
                  ))}
                </select>
              </div>

              <div className="form-group">
                <label className="form-label">Zimmetli Kişi</label>
                <select
                  className="form-select"
                  value={form.assigned_person_id}
                  onChange={(e) => set('assigned_person_id', e.target.value)}
                >
                  <option value="">— Zimmet Yok —</option>
                  {persons.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.first_name} {p.last_name}
                    </option>
                  ))}
                </select>
              </div>

              <div className="form-group">
                <label className="form-label">Son Bakım Tarihi</label>
                <input
                  type="date"
                  className="form-input"
                  value={form.last_maintenance_date}
                  onChange={(e) => set('last_maintenance_date', e.target.value)}
                />
              </div>
              <div className="form-group">
                <label className="form-label">Sonraki Bakım Tarihi</label>
                <input
                  type="date"
                  className="form-input"
                  value={form.next_maintenance_date}
                  onChange={(e) => set('next_maintenance_date', e.target.value)}
                />
              </div>

              <div className="form-group">
                <label className="form-label">Sigorta Bitiş Tarihi</label>
                <input
                  type="date"
                  className="form-input"
                  value={form.insurance_expiry_date}
                  onChange={(e) => set('insurance_expiry_date', e.target.value)}
                />
              </div>

              <div className="form-group" style={{ display: 'flex', alignItems: 'center', gap: 10, paddingTop: 24 }}>
                <input
                  type="checkbox"
                  id="eq-is-active"
                  checked={form.is_active}
                  onChange={(e) => set('is_active', e.target.checked)}
                  style={{ width: 18, height: 18 }}
                />
                <label htmlFor="eq-is-active" className="form-label" style={{ marginBottom: 0 }}>
                  Aktif
                </label>
              </div>
            </div>

            <div className="form-group">
              <label className="form-label">Notlar</label>
              <textarea
                className="form-input"
                rows={3}
                value={form.notes}
                onChange={(e) => set('notes', e.target.value)}
                placeholder="Opsiyonel açıklama"
              />
            </div>
          </div>

          <div className="modal-footer">
            <button type="button" className="btn btn-ghost" onClick={onClose} disabled={saving}>
              İptal
            </button>
            <button type="submit" className="btn btn-primary" disabled={saving || !form.name.trim()}>
              {saving ? <span className="loading-spinner" /> : isEdit ? 'Güncelle' : 'Kaydet'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
