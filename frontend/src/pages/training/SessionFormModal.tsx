/**
 * Oturum oluşturma/düzenleme modal'ı.
 *
 * P0-2: Çoklu antrenör seçimi — antrenor rolüne sahip kişiler checkbox listesi olarak sunulur.
 */
import { useEffect, useState } from 'react'
import { trainingApi } from '@/api/training'
import { personsApi } from '@/api/persons'
import { PERSON_LIST_LIMIT } from '@/api/constants'
import type { TrainingSession, TrainingSessionCreate, TrainingSessionUpdate, SessionStatus } from '@/types/training'
import type { Person } from '@/types/person'

interface Props {
  isOpen: boolean
  onClose: () => void
  courseId: string
  session?: TrainingSession
  onSaved: (session: TrainingSession) => void
}

const EMPTY: TrainingSessionCreate = {
  session_date: '',
  start_time: null,
  end_time: null,
  instructor_person_ids: [],
  notes: null,
  status: 'planli',
}

const STATUS_OPTIONS: { value: SessionStatus; label: string }[] = [
  { value: 'planli', label: 'Planlı' },
  { value: 'tamamlandi', label: 'Tamamlandı' },
  { value: 'iptal', label: 'İptal' },
]

export default function SessionFormModal({ isOpen, onClose, courseId, session, onSaved }: Props) {
  const isEdit = !!session
  const [form, setForm] = useState<TrainingSessionCreate>(EMPTY)
  const [antrenorler, setAntrenorler] = useState<Person[]>([])
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!isOpen) return
    setError(null)
    if (session) {
      setForm({
        session_date: session.session_date,
        start_time: session.start_time,
        end_time: session.end_time,
        // Mevcut oturum antrenörlerini yükle
        instructor_person_ids: session.instructors.map((i) => i.id),
        notes: session.notes,
        status: session.status,
      })
    } else {
      setForm(EMPTY)
    }
  }, [isOpen, session])

  // Antrenör rolüne sahip aktif kişileri yükle
  useEffect(() => {
    if (!isOpen) return
    personsApi.list({ limit: PERSON_LIST_LIMIT, is_active: true, role_code: 'antrenor' })
      .then((r) => setAntrenorler(r.data.items))
      .catch((err) => console.error('[SessionFormModal] antrenör listesi alınamadı:', err))
  }, [isOpen])

  const set = (field: keyof TrainingSessionCreate, value: unknown) =>
    setForm((f) => ({ ...f, [field]: value ?? null }))

  const toggleInstructor = (personId: string) => {
    setForm((f) => {
      const ids = f.instructor_person_ids ?? []
      const next = ids.includes(personId)
        ? ids.filter((id) => id !== personId)
        : [...ids, personId]
      return { ...f, instructor_person_ids: next }
    })
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!form.session_date) { setError('Oturum tarihi zorunludur.'); return }
    setSaving(true)
    setError(null)
    try {
      let saved: TrainingSession
      if (isEdit && session) {
        const body: TrainingSessionUpdate = {
          session_date: form.session_date,
          start_time: form.start_time,
          end_time: form.end_time,
          instructor_person_ids: form.instructor_person_ids ?? [],
          notes: form.notes,
          status: form.status,
        }
        const resp = await trainingApi.updateSession(courseId, session.id, body)
        saved = resp.data
      } else {
        const resp = await trainingApi.createSession(courseId, form)
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

  const selectedIds = form.instructor_person_ids ?? []

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" style={{ maxWidth: 500 }} onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2 className="modal-title">{isEdit ? 'Oturumu Düzenle' : 'Yeni Oturum'}</h2>
          <button className="modal-close" onClick={onClose}>×</button>
        </div>
        <form onSubmit={handleSubmit}>
          <div className="modal-body">
            {error && (
              <div className="alert alert-error" style={{ marginBottom: 12 }}>
                <span>⚠️</span><span>{error}</span>
              </div>
            )}

            <div className="form-group">
              <label className="form-label">Tarih *</label>
              <input
                type="date"
                className="form-input"
                value={form.session_date}
                onChange={(e) => setForm((f) => ({ ...f, session_date: e.target.value }))}
              />
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
              <div className="form-group">
                <label className="form-label">Başlangıç Saati</label>
                <input
                  type="time"
                  className="form-input"
                  value={form.start_time ?? ''}
                  onChange={(e) => set('start_time', e.target.value)}
                />
              </div>
              <div className="form-group">
                <label className="form-label">Bitiş Saati</label>
                <input
                  type="time"
                  className="form-input"
                  value={form.end_time ?? ''}
                  onChange={(e) => set('end_time', e.target.value)}
                />
              </div>
            </div>

            <div className="form-group">
              <label className="form-label">Durum</label>
              <select
                className="form-select"
                value={form.status ?? 'planli'}
                onChange={(e) => setForm((f) => ({ ...f, status: e.target.value as SessionStatus }))}
              >
                {STATUS_OPTIONS.map((o) => (
                  <option key={o.value} value={o.value}>{o.label}</option>
                ))}
              </select>
            </div>

            {/* P0-2: Çoklu antrenör seçimi (opsiyonel — kurstan farklıysa) */}
            <div className="form-group">
              <label className="form-label">
                Antrenörler (opsiyonel — kurstan farklıysa)
                {selectedIds.length > 0 && (
                  <span style={{ marginLeft: 8, fontWeight: 400, color: 'var(--color-text-muted)', fontSize: 12 }}>
                    ({selectedIds.length} seçildi)
                  </span>
                )}
              </label>
              {antrenorler.length === 0 ? (
                <div style={{ color: 'var(--color-text-muted)', fontSize: 13, padding: '6px 0' }}>
                  Antrenor rolüne sahip aktif kişi bulunamadı.
                </div>
              ) : (
                <div
                  style={{
                    border: '1px solid var(--color-border)',
                    borderRadius: 6,
                    maxHeight: 140,
                    overflowY: 'auto',
                    padding: '4px 0',
                  }}
                >
                  {antrenorler.map((p) => (
                    <label
                      key={p.id}
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: 8,
                        padding: '6px 12px',
                        cursor: 'pointer',
                        background: selectedIds.includes(p.id) ? 'var(--color-primary-light, rgba(0,100,200,0.08))' : 'transparent',
                      }}
                    >
                      <input
                        type="checkbox"
                        checked={selectedIds.includes(p.id)}
                        onChange={() => toggleInstructor(p.id)}
                        style={{ accentColor: 'var(--color-primary)' }}
                      />
                      <span style={{ fontSize: 14 }}>{p.first_name} {p.last_name}</span>
                    </label>
                  ))}
                </div>
              )}
            </div>

            <div className="form-group">
              <label className="form-label">Notlar</label>
              <textarea
                className="form-input"
                rows={2}
                value={form.notes ?? ''}
                onChange={(e) => set('notes', e.target.value)}
              />
            </div>
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
