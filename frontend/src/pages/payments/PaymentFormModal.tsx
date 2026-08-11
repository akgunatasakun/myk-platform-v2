/**
 * Ödeme oluşturma (tüm alanlar) ve güncelleme (kısıtlı alanlar) modal.
 *
 * Backend PaymentUpdate yalnızca şu alanları kabul eder:
 *   status, paid_at, payment_method, receipt_no, notes
 * Dolayısıyla düzenleme modunda diğer alanlar disabled gösterilir.
 */
import { useEffect, useState } from 'react'
import { paymentsApi } from '@/api/payments'
import { personsApi } from '@/api/persons'
import type { Payment, PaymentCreate, PaymentUpdate, PaymentStatus } from '@/types/payment'
import type { Person } from '@/types/person'

interface Props {
  isOpen: boolean
  onClose: () => void
  payment?: Payment      // undefined → create, defined → edit
  onSaved: (payment: Payment) => void
}

const EMPTY_CREATE: PaymentCreate = {
  person_id: null,
  amount: '',
  payment_type: null,
  payment_method: null,
  due_date: null,
  paid_at: null,
  status: 'pending',
  receipt_no: null,
  notes: null,
}

export default function PaymentFormModal({ isOpen, onClose, payment, onSaved }: Props) {
  const isEdit = !!payment

  // Create form state
  const [createForm, setCreateForm] = useState<PaymentCreate>(EMPTY_CREATE)
  // Edit form state (kısıtlı)
  const [editForm, setEditForm] = useState<PaymentUpdate>({})

  const [persons, setPersons] = useState<Person[]>([])
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!isOpen) return
    setError(null)
    if (payment) {
      setEditForm({
        status: payment.status,
        paid_at: payment.paid_at ?? undefined,
        payment_method: payment.payment_method ?? undefined,
        receipt_no: payment.receipt_no ?? undefined,
        notes: payment.notes ?? undefined,
      })
    } else {
      setCreateForm(EMPTY_CREATE)
    }
  }, [isOpen, payment])

  useEffect(() => {
    if (!isOpen || isEdit) return
    personsApi.list({ limit: 200, is_active: true }).then((r) => setPersons(r.data.items)).catch(() => {})
  }, [isOpen, isEdit])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setSaving(true)
    setError(null)
    try {
      let saved: Payment
      if (isEdit && payment) {
        const resp = await paymentsApi.update(payment.id, editForm)
        saved = resp.data
      } else {
        if (!createForm.amount || parseFloat(createForm.amount) <= 0) {
          setError('Tutar 0\'dan büyük olmalıdır.')
          setSaving(false)
          return
        }
        const resp = await paymentsApi.create(createForm)
        saved = resp.data
      }
      onSaved(saved)
      onClose()
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      setError(msg ?? 'Kayıt sırasında hata oluştu.')
    } finally {
      setSaving(false)
    }
  }

  if (!isOpen) return null

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" style={{ maxWidth: 540 }} onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2 className="modal-title">{isEdit ? 'Ödeme Güncelle' : 'Yeni Ödeme'}</h2>
          <button className="modal-close" onClick={onClose}>×</button>
        </div>

        <form onSubmit={handleSubmit}>
          <div className="modal-body">
            {error && (
              <div className="alert alert-error" style={{ marginBottom: 12 }}>
                <span>⚠️</span><span>{error}</span>
              </div>
            )}

            {/* ── EDIT MODE ────────────────────────────────────────────────── */}
            {isEdit && payment ? (
              <>
                {/* Salt okunur bilgiler */}
                <div className="card" style={{ marginBottom: 16 }}>
                  <div className="card-body" style={{ padding: '10px 14px' }}>
                    <div style={{ display: 'flex', gap: 24, flexWrap: 'wrap' }}>
                      <span style={{ fontSize: 13 }}>
                        <span style={{ color: 'var(--color-text-muted)' }}>Kişi: </span>
                        <strong>{payment.person_name ?? '—'}</strong>
                      </span>
                      <span style={{ fontSize: 13 }}>
                        <span style={{ color: 'var(--color-text-muted)' }}>Tutar: </span>
                        <strong>{parseFloat(payment.amount).toLocaleString('tr-TR', { minimumFractionDigits: 2 })} ₺</strong>
                      </span>
                      <span style={{ fontSize: 13 }}>
                        <span style={{ color: 'var(--color-text-muted)' }}>Tür: </span>
                        <strong>{payment.payment_type ?? '—'}</strong>
                      </span>
                    </div>
                  </div>
                </div>

                {/* Güncellenebilir alanlar */}
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                  <div className="form-group">
                    <label className="form-label">Durum</label>
                    <select
                      className="form-select"
                      value={editForm.status ?? 'pending'}
                      onChange={(e) => setEditForm((f) => ({ ...f, status: e.target.value as PaymentStatus }))}
                    >
                      <option value="pending">Bekliyor</option>
                      <option value="paid">Ödendi</option>
                    </select>
                  </div>
                  <div className="form-group">
                    <label className="form-label">Ödeme Tarihi</label>
                    <input
                      type="date"
                      className="form-input"
                      value={editForm.paid_at ?? ''}
                      onChange={(e) => setEditForm((f) => ({ ...f, paid_at: e.target.value || null }))}
                    />
                  </div>
                </div>

                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                  <div className="form-group">
                    <label className="form-label">Ödeme Yöntemi</label>
                    <input
                      className="form-input"
                      value={editForm.payment_method ?? ''}
                      onChange={(e) => setEditForm((f) => ({ ...f, payment_method: e.target.value || null }))}
                      placeholder="örn. Nakit, Havale"
                    />
                  </div>
                  <div className="form-group">
                    <label className="form-label">Makbuz No</label>
                    <input
                      className="form-input"
                      value={editForm.receipt_no ?? ''}
                      onChange={(e) => setEditForm((f) => ({ ...f, receipt_no: e.target.value || null }))}
                    />
                  </div>
                </div>

                <div className="form-group">
                  <label className="form-label">Notlar</label>
                  <textarea
                    className="form-input"
                    rows={2}
                    value={editForm.notes ?? ''}
                    onChange={(e) => setEditForm((f) => ({ ...f, notes: e.target.value || null }))}
                  />
                </div>
              </>
            ) : (
              /* ── CREATE MODE ─────────────────────────────────────────────── */
              <>
                <div className="form-group">
                  <label className="form-label">Kişi</label>
                  <select
                    className="form-select"
                    value={createForm.person_id ?? ''}
                    onChange={(e) => setCreateForm((f) => ({ ...f, person_id: e.target.value || null }))}
                  >
                    <option value="">— Seçiniz (opsiyonel) —</option>
                    {persons.map((p) => (
                      <option key={p.id} value={p.id}>{p.first_name} {p.last_name}</option>
                    ))}
                  </select>
                </div>

                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                  <div className="form-group">
                    <label className="form-label">Tutar (₺) *</label>
                    <input
                      type="number"
                      className="form-input"
                      min="0.01"
                      step="0.01"
                      value={createForm.amount}
                      onChange={(e) => setCreateForm((f) => ({ ...f, amount: e.target.value }))}
                      placeholder="0.00"
                    />
                  </div>
                  <div className="form-group">
                    <label className="form-label">Ödeme Türü</label>
                    <input
                      className="form-input"
                      value={createForm.payment_type ?? ''}
                      onChange={(e) => setCreateForm((f) => ({ ...f, payment_type: e.target.value || null }))}
                      placeholder="örn. Üyelik, Eğitim"
                    />
                  </div>
                </div>

                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                  <div className="form-group">
                    <label className="form-label">Son Ödeme Tarihi</label>
                    <input
                      type="date"
                      className="form-input"
                      value={createForm.due_date ?? ''}
                      onChange={(e) => setCreateForm((f) => ({ ...f, due_date: e.target.value || null }))}
                    />
                  </div>
                  <div className="form-group">
                    <label className="form-label">Ödeme Tarihi</label>
                    <input
                      type="date"
                      className="form-input"
                      value={createForm.paid_at ?? ''}
                      onChange={(e) => setCreateForm((f) => ({ ...f, paid_at: e.target.value || null }))}
                    />
                  </div>
                </div>

                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                  <div className="form-group">
                    <label className="form-label">Durum</label>
                    <select
                      className="form-select"
                      value={createForm.status ?? 'pending'}
                      onChange={(e) => setCreateForm((f) => ({ ...f, status: e.target.value as PaymentStatus }))}
                    >
                      <option value="pending">Bekliyor</option>
                      <option value="paid">Ödendi</option>
                    </select>
                  </div>
                  <div className="form-group">
                    <label className="form-label">Ödeme Yöntemi</label>
                    <input
                      className="form-input"
                      value={createForm.payment_method ?? ''}
                      onChange={(e) => setCreateForm((f) => ({ ...f, payment_method: e.target.value || null }))}
                      placeholder="örn. Nakit, Havale"
                    />
                  </div>
                </div>

                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                  <div className="form-group">
                    <label className="form-label">Makbuz No</label>
                    <input
                      className="form-input"
                      value={createForm.receipt_no ?? ''}
                      onChange={(e) => setCreateForm((f) => ({ ...f, receipt_no: e.target.value || null }))}
                    />
                  </div>
                </div>

                <div className="form-group">
                  <label className="form-label">Notlar</label>
                  <textarea
                    className="form-input"
                    rows={2}
                    value={createForm.notes ?? ''}
                    onChange={(e) => setCreateForm((f) => ({ ...f, notes: e.target.value || null }))}
                  />
                </div>
              </>
            )}
          </div>

          <div className="modal-footer">
            <button type="button" className="btn btn-ghost" onClick={onClose} disabled={saving}>
              İptal
            </button>
            <button type="submit" className="btn btn-primary" disabled={saving}>
              {saving ? 'Kaydediliyor…' : isEdit ? 'Güncelle' : 'Oluştur'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
