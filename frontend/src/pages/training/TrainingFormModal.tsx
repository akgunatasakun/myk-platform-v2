import { useEffect, useState } from 'react'
import { trainingApi } from '@/api/training'
import { personsApi } from '@/api/persons'
import { PERSON_LIST_LIMIT } from '@/api/constants'
import type { TrainingCourse, TrainingCourseCreate, TrainingCourseUpdate, CourseStatus } from '@/types/training'
import type { Person } from '@/types/person'

interface Props {
  isOpen: boolean
  onClose: () => void
  course?: TrainingCourse
  onSaved: (course: TrainingCourse) => void
}

const EMPTY: TrainingCourseCreate = {
  name: '',
  description: null,
  class_name: null,
  level: null,
  start_date: null,
  end_date: null,
  schedule_text: null,
  capacity: 0,
  fee: '0',
  instructor_person_id: null,
  status: 'planlandi',
}

const STATUS_OPTIONS: { value: CourseStatus; label: string }[] = [
  { value: 'planlandi', label: 'Planlandı' },
  { value: 'aktif', label: 'Aktif' },
  { value: 'tamamlandi', label: 'Tamamlandı' },
  { value: 'iptal', label: 'İptal' },
]

export default function TrainingFormModal({ isOpen, onClose, course, onSaved }: Props) {
  const isEdit = !!course
  const [form, setForm] = useState<TrainingCourseCreate>(EMPTY)
  const [persons, setPersons] = useState<Person[]>([])
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!isOpen) return
    setError(null)
    if (course) {
      setForm({
        name: course.name,
        description: course.description,
        class_name: course.class_name,
        level: course.level,
        start_date: course.start_date,
        end_date: course.end_date,
        schedule_text: course.schedule_text,
        capacity: course.capacity,
        fee: course.fee,
        instructor_person_id: course.instructor_person_id,
        status: course.status,
      })
    } else {
      setForm(EMPTY)
    }
  }, [isOpen, course])

  useEffect(() => {
    if (!isOpen) return
    personsApi.list({ limit: PERSON_LIST_LIMIT, is_active: true, role_code: 'antrenor' })
      .then((r) => setPersons(r.data.items))
      .catch((err) => console.error('Eğitmen listesi yüklenemedi:', err))
  }, [isOpen])

  const set = (field: keyof TrainingCourseCreate, value: unknown) =>
    setForm((f) => ({ ...f, [field]: value || null }))

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!form.name.trim()) { setError('Eğitim adı zorunludur.'); return }
    setSaving(true)
    setError(null)
    try {
      let saved: TrainingCourse
      if (isEdit && course) {
        const body: TrainingCourseUpdate = { ...form }
        const resp = await trainingApi.updateCourse(course.id, body)
        saved = resp.data
      } else {
        const resp = await trainingApi.createCourse(form)
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
      <div className="modal" style={{ maxWidth: 620 }} onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2 className="modal-title">{isEdit ? 'Eğitimi Düzenle' : 'Yeni Eğitim'}</h2>
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
              <label className="form-label">Eğitim Adı *</label>
              <input
                className="form-input"
                value={form.name}
                onChange={(e) => set('name', e.target.value)}
                placeholder="örn. Yelken Temel Eğitimi"
              />
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
              <div className="form-group">
                <label className="form-label">Sınıf</label>
                <input
                  className="form-input"
                  value={form.class_name ?? ''}
                  onChange={(e) => set('class_name', e.target.value)}
                  placeholder="örn. Optimist A"
                />
              </div>
              <div className="form-group">
                <label className="form-label">Seviye</label>
                <input
                  className="form-input"
                  value={form.level ?? ''}
                  onChange={(e) => set('level', e.target.value)}
                  placeholder="örn. Başlangıç"
                />
              </div>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
              <div className="form-group">
                <label className="form-label">Başlangıç Tarihi</label>
                <input
                  type="date"
                  className="form-input"
                  value={form.start_date ?? ''}
                  onChange={(e) => set('start_date', e.target.value)}
                />
              </div>
              <div className="form-group">
                <label className="form-label">Bitiş Tarihi</label>
                <input
                  type="date"
                  className="form-input"
                  value={form.end_date ?? ''}
                  onChange={(e) => set('end_date', e.target.value)}
                />
              </div>
            </div>

            <div className="form-group">
              <label className="form-label">Program / Takvim</label>
              <input
                className="form-input"
                value={form.schedule_text ?? ''}
                onChange={(e) => set('schedule_text', e.target.value)}
                placeholder="örn. Pazartesi-Çarşamba 16:00-18:00"
              />
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
              <div className="form-group">
                <label className="form-label">Kapasite (0 = sınırsız)</label>
                <input
                  type="number"
                  className="form-input"
                  min={0}
                  value={form.capacity ?? 0}
                  onChange={(e) => setForm((f) => ({ ...f, capacity: parseInt(e.target.value) || 0 }))}
                />
              </div>
              <div className="form-group">
                <label className="form-label">Ücret (₺)</label>
                <input
                  type="number"
                  className="form-input"
                  min={0}
                  step="0.01"
                  value={form.fee ?? '0'}
                  onChange={(e) => setForm((f) => ({ ...f, fee: e.target.value || '0' }))}
                />
              </div>
            </div>

            <div className="form-group">
              <label className="form-label">Eğitmen</label>
              <select
                className="form-select"
                value={form.instructor_person_id ?? ''}
                onChange={(e) => set('instructor_person_id', e.target.value)}
              >
                <option value="">— Seçiniz —</option>
                {persons.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.first_name} {p.last_name}
                  </option>
                ))}
              </select>
            </div>

            <div className="form-group">
              <label className="form-label">Durum</label>
              <select
                className="form-select"
                value={form.status ?? 'planlandi'}
                onChange={(e) => setForm((f) => ({ ...f, status: e.target.value as CourseStatus }))}
              >
                {STATUS_OPTIONS.map((o) => (
                  <option key={o.value} value={o.value}>{o.label}</option>
                ))}
              </select>
            </div>

            <div className="form-group">
              <label className="form-label">Açıklama</label>
              <textarea
                className="form-input"
                rows={3}
                value={form.description ?? ''}
                onChange={(e) => set('description', e.target.value)}
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
