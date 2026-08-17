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
  instructor_person_id: null,
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
  const [persons, setPersons] = useState<Person[]>([])
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
        instructor_person_id: session.instructor_person_id,
        notes: session.notes,
        status: session.status,
      })
    } else {
      setForm(EMPTY)
    }
  }, [isOpen, session])

  useEffect(() => {
    if (!isOpen) return
    personsApi.list({ limit: PERSON_LIST_LIMIT, is_active: true })
      .then((r) => setPersons(r.data.items))
      .catch((err) => console.error('Eğitmen listesi yüklenemedi:', err))
  }, [isOpen])

  const set = (field: keyof TrainingSessionCreate, value: unknown) =>
    setForm((f) => ({ ...f, [field]: value || null }))

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!form.session_date) { setError('Oturum tarihi zorunludur.'); return }
    setSaving(true)
    setError(null)
    try {
      let saved: TrainingSession
      if (isEdit && session) {
        const body: TrainingSessionUpdate = { ...form }
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

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" style={{ maxWidth: 480 }} onClick={(e) => e.stopPropagation()}>
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

            <div className="form-group">
              <label className="form-label">Eğitmen (opsiyonel — kurstan farklıysa)</label>
              <select
                className="form-select"
                value={form.instructor_person_id ?? ''}
                onChange={(e) => set('instructor_person_id', e.target.value)}
              >
                <option value="">— Kurs eğitmeni —</option>
                {persons.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.first_name} {p.last_name}
                  </option>
                ))}
              </select>
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
