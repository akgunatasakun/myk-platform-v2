/**
 * Eğitim oluşturma/düzenleme modal'ı.
 *
 * P0-2: Çoklu antrenör seçimi — antrenor rolüne sahip kişiler checkbox listesi olarak sunulur.
 */
import { useEffect, useState } from 'react'
import { trainingApi } from '@/api/training'
import { personsApi } from '@/api/persons'
import { PERSON_LIST_LIMIT } from '@/api/constants'
import type { TrainingCourse, TrainingCourseCreate, TrainingCourseUpdate, CourseStatus, AttendanceMode } from '@/types/training'
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
  instructor_person_ids: [],
  status: 'planlandi',
  attendance_mode: 'coach_daily',
  is_registration_open: true,
}

const ATTENDANCE_MODE_OPTIONS: { value: AttendanceMode; label: string; description: string }[] = [
  {
    value: 'coach_daily',
    label: 'Antrenör Yoklaması',
    description: 'Antrenör tarih ve eğitimi seçerek tüm sporcular için toplu yoklama girer.',
  },
  {
    value: 'adult_self_checkin',
    label: 'Yetişkin Self Check-in (+18)',
    description: 'Sporcu kendi hesabıyla oturum saatinde katıldım kaydı oluşturur.',
  },
]

const STATUS_OPTIONS: { value: CourseStatus; label: string }[] = [
  { value: 'planlandi', label: 'Planlandı' },
  { value: 'aktif', label: 'Aktif' },
  { value: 'tamamlandi', label: 'Tamamlandı' },
  { value: 'iptal', label: 'İptal' },
]

export default function TrainingFormModal({ isOpen, onClose, course, onSaved }: Props) {
  const isEdit = !!course
  const [form, setForm] = useState<TrainingCourseCreate>(EMPTY)
  const [antrenorler, setAntrenorler] = useState<Person[]>([])
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
        // Mevcut antrenörleri yükle
        instructor_person_ids: course.instructors.map((i) => i.id),
        status: course.status,
        attendance_mode: course.attendance_mode ?? 'coach_daily',
        is_registration_open: course.is_registration_open ?? true,
      })
    } else {
      setForm(EMPTY)
    }
  }, [isOpen, course])

  // Antrenör rolüne sahip aktif kişileri yükle
  useEffect(() => {
    if (!isOpen) return
    personsApi.list({ limit: PERSON_LIST_LIMIT, is_active: true, role_code: 'antrenor' })
      .then((r) => setAntrenorler(r.data.items))
      .catch((err) => console.error('[TrainingFormModal] antrenör listesi alınamadı:', err))
  }, [isOpen])

  const set = (field: keyof TrainingCourseCreate, value: unknown) =>
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
    if (!form.name.trim()) { setError('Eğitim adı zorunludur.'); return }
    setSaving(true)
    setError(null)
    try {
      let saved: TrainingCourse
      if (isEdit && course) {
        const body: TrainingCourseUpdate = {
          name: form.name,
          description: form.description,
          class_name: form.class_name,
          level: form.level,
          start_date: form.start_date,
          end_date: form.end_date,
          schedule_text: form.schedule_text,
          capacity: form.capacity,
          fee: form.fee,
          instructor_person_ids: form.instructor_person_ids ?? [],
          status: form.status,
          attendance_mode: form.attendance_mode,
          is_registration_open: form.is_registration_open,
        }
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

  const selectedIds = form.instructor_person_ids ?? []

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" style={{ maxWidth: 640 }} onClick={(e) => e.stopPropagation()}>
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

            {/* P0-2: Çoklu antrenör seçimi */}
            <div className="form-group">
              <label className="form-label">
                Antrenörler
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
                    maxHeight: 160,
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
              <label className="form-label">Yoklama Modu</label>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginTop: 4 }}>
                {ATTENDANCE_MODE_OPTIONS.map((o) => (
                  <label
                    key={o.value}
                    style={{
                      display: 'flex',
                      alignItems: 'flex-start',
                      gap: 10,
                      padding: '10px 12px',
                      border: `1px solid ${form.attendance_mode === o.value ? 'var(--color-primary)' : 'var(--color-border)'}`,
                      borderRadius: 6,
                      cursor: 'pointer',
                      background: form.attendance_mode === o.value ? 'var(--color-primary-light, rgba(0,100,200,0.06))' : 'transparent',
                    }}
                  >
                    <input
                      type="radio"
                      name="attendance_mode"
                      value={o.value}
                      checked={form.attendance_mode === o.value}
                      onChange={() => setForm((f) => ({ ...f, attendance_mode: o.value }))}
                      style={{ marginTop: 2, accentColor: 'var(--color-primary)' }}
                    />
                    <div>
                      <div style={{ fontSize: 14, fontWeight: 500 }}>{o.label}</div>
                      <div style={{ fontSize: 12, color: 'var(--color-text-muted)', marginTop: 2 }}>{o.description}</div>
                    </div>
                  </label>
                ))}
              </div>
            </div>

            <div className="form-group">
              <label
                style={{ display: 'flex', alignItems: 'center', gap: 10, cursor: 'pointer' }}
              >
                <input
                  type="checkbox"
                  checked={form.is_registration_open ?? true}
                  onChange={(e) =>
                    setForm((f) => ({ ...f, is_registration_open: e.target.checked }))
                  }
                  style={{ width: 16, height: 16, accentColor: 'var(--color-primary)' }}
                />
                <span>
                  <strong>Başvuruya açık</strong>
                  <span style={{ display: 'block', fontSize: 12, color: 'var(--color-text-muted)', marginTop: 2 }}>
                    İşaretsiz bırakırsanız bu kurs public başvuru formunda listelenmez (UAT / dahili kurs).
                  </span>
                </span>
              </label>
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
