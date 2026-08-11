import { useEffect, useState } from 'react'
import { equipmentApi } from '@/api/equipment'
import type { MaintenanceRecord, MaintenanceRecordCreate, MaintenanceRecordUpdate } from '@/types/equipment'

interface Props {
  isOpen: boolean
  onClose: () => void
  equipmentId: string
  record?: MaintenanceRecord        // varsa düzenleme modu
  onSaved: (record: MaintenanceRecord) => void
}

function emptyForm() {
  return {
    maintenance_date: new Date().toISOString().slice(0, 10),
    maintenance_type: '',
    description: '',
    cost: '',
    performed_by: '',
    next_maintenance_date: '',
    notes: '',
  }
}

export default function MaintenanceFormModal({ isOpen, onClose, equipmentId, record, onSaved }: Props) {
  const isEdit = !!record
  const [form, setForm] = useState(emptyForm())
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!isOpen) return
    if (record) {
      setForm({
        maintenance_date: record.maintenance_date,
        maintenance_type: record.maintenance_type ?? '',
        description: record.description ?? '',
        cost: record.cost ?? '',
        performed_by: record.performed_by ?? '',
        next_maintenance_date: record.next_maintenance_date ?? '',
        notes: record.notes ?? '',
      })
    } else {
      setForm(emptyForm())
    }
    setError(null)
  }, [isOpen, record])

  const set = (field: string, value: string) =>
    setForm((f) => ({ ...f, [field]: value }))

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setSaving(true)
    setError(null)

    const nullStr = (v: string) => v.trim() || null
    const nullNum = (v: string) => (v.trim() ? parseFloat(v) : null)

    const payload: MaintenanceRecordCreate | MaintenanceRecordUpdate = {
      maintenance_date: form.maintenance_date,
      maintenance_type: nullStr(form.maintenance_type),
      description: nullStr(form.description),
      cost: nullNum(form.cost),
      performed_by: nullStr(form.performed_by),
      next_maintenance_date: nullStr(form.next_maintenance_date),
      notes: nullStr(form.notes),
    }

    try {
      let saved: MaintenanceRecord
      if (isEdit) {
        const resp = await equipmentApi.updateMaintenance(equipmentId, record.id, payload)
        saved = resp.data
      } else {
        const resp = await equipmentApi.createMaintenance(equipmentId, payload as MaintenanceRecordCreate)
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
      <div className="modal" style={{ maxWidth: 520 }} onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2 className="modal-title">{isEdit ? 'Bakım Kaydını Düzenle' : 'Yeni Bakım Kaydı'}</h2>
          <button className="modal-close" onClick={onClose}>✕</button>
        </div>

        {error && (
          <div className="alert alert-error" style={{ margin: '0 0 16px' }}>
            <span>⚠️</span><span>{error}</span>
          </div>
        )}

        <form onSubmit={handleSubmit}>
          <div className="modal-body">
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
              <div className="form-group">
                <label className="form-label">Bakım Tarihi *</label>
                <input
                  type="date"
                  className="form-input"
                  value={form.maintenance_date}
                  onChange={(e) => set('maintenance_date', e.target.value)}
                  required
                />
              </div>
              <div className="form-group">
                <label className="form-label">Bakım Türü</label>
                <input
                  className="form-input"
                  value={form.maintenance_type}
                  onChange={(e) => set('maintenance_type', e.target.value)}
                  placeholder="periyodik, arıza, genel…"
                />
              </div>

              <div className="form-group">
                <label className="form-label">Maliyet (₺)</label>
                <input
                  type="number"
                  min="0"
                  step="0.01"
                  className="form-input"
                  value={form.cost}
                  onChange={(e) => set('cost', e.target.value)}
                  placeholder="0.00"
                />
              </div>
              <div className="form-group">
                <label className="form-label">Yapan Kişi / Firma</label>
                <input
                  className="form-input"
                  value={form.performed_by}
                  onChange={(e) => set('performed_by', e.target.value)}
                />
              </div>

              <div className="form-group" style={{ gridColumn: '1 / -1' }}>
                <label className="form-label">Açıklama</label>
                <textarea
                  className="form-input"
                  rows={2}
                  value={form.description}
                  onChange={(e) => set('description', e.target.value)}
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
                <label className="form-label">Notlar</label>
                <input
                  className="form-input"
                  value={form.notes}
                  onChange={(e) => set('notes', e.target.value)}
                />
              </div>
            </div>
          </div>

          <div className="modal-footer">
            <button type="button" className="btn btn-ghost" onClick={onClose} disabled={saving}>
              İptal
            </button>
            <button type="submit" className="btn btn-primary" disabled={saving}>
              {saving ? <span className="loading-spinner" /> : isEdit ? 'Güncelle' : 'Kaydet'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
