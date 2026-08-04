import { useEffect, useRef, useState } from 'react'
import { personsApi } from '@/api/persons'
import type { Person, PersonCreate, PersonRoleCode, Gender, BloodType } from '@/types/person'

const ROLE_OPTIONS: { code: PersonRoleCode; label: string }[] = [
  { code: 'sporcu', label: 'Sporcu' },
  { code: 'uye', label: 'Üye' },
  { code: 'veli', label: 'Veli' },
  { code: 'antrenor', label: 'Antrenör' },
  { code: 'personel', label: 'Personel' },
  { code: 'misafir', label: 'Misafir' },
]

const GENDER_OPTIONS: { value: Gender; label: string }[] = [
  { value: 'erkek', label: 'Erkek' },
  { value: 'kadin', label: 'Kadın' },
  { value: 'belirtilmedi', label: 'Belirtilmedi' },
]

const BLOOD_TYPE_OPTIONS: BloodType[] = ['A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', '0+', '0-']

interface Props {
  isOpen: boolean
  onClose: () => void
  person?: Person
  onSaved: (p: Person) => void
}

interface FormData {
  first_name: string
  last_name: string
  national_id: string
  birth_date: string
  gender: string
  phone: string
  email: string
  address: string
  emergency_contact_name: string
  emergency_contact_phone: string
  blood_type: string
  notes: string
  role_codes: PersonRoleCode[]
}

const EMPTY_FORM: FormData = {
  first_name: '',
  last_name: '',
  national_id: '',
  birth_date: '',
  gender: '',
  phone: '',
  email: '',
  address: '',
  emergency_contact_name: '',
  emergency_contact_phone: '',
  blood_type: '',
  notes: '',
  role_codes: [],
}

function personToForm(p: Person): FormData {
  return {
    first_name: p.first_name,
    last_name: p.last_name,
    national_id: p.national_id && p.national_id !== '***' ? p.national_id : '',
    birth_date: p.birth_date ?? '',
    gender: p.gender ?? '',
    phone: p.phone ?? '',
    email: p.email ?? '',
    address: p.address ?? '',
    emergency_contact_name: p.emergency_contact_name ?? '',
    emergency_contact_phone: p.emergency_contact_phone ?? '',
    blood_type: (p.blood_type && (p.blood_type as string) !== '***') ? p.blood_type : '',
    notes: p.notes ?? '',
    role_codes: p.role_codes ?? [],
  }
}

export default function PersonFormModal({ isOpen, onClose, person, onSaved }: Props) {
  const [form, setForm] = useState<FormData>(EMPTY_FORM)
  const [errors, setErrors] = useState<Partial<Record<keyof FormData, string>>>({})
  const [apiError, setApiError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const isDirty = useRef(false)

  useEffect(() => {
    if (isOpen) {
      const initial = person ? personToForm(person) : EMPTY_FORM
      setForm(initial)
      setErrors({})
      setApiError(null)
      isDirty.current = false
    }
  }, [isOpen, person])

  const handleChange = (
    e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>
  ) => {
    isDirty.current = true
    const { name, value } = e.target
    setForm((prev) => ({ ...prev, [name]: value }))
    setErrors((prev) => ({ ...prev, [name]: undefined }))
  }

  const handleRoleToggle = (code: PersonRoleCode) => {
    isDirty.current = true
    setForm((prev) => ({
      ...prev,
      role_codes: prev.role_codes.includes(code)
        ? prev.role_codes.filter((r) => r !== code)
        : [...prev.role_codes, code],
    }))
  }

  const validate = (): boolean => {
    const newErrors: Partial<Record<keyof FormData, string>> = {}
    if (!form.first_name.trim()) newErrors.first_name = 'Ad zorunludur.'
    if (!form.last_name.trim()) newErrors.last_name = 'Soyad zorunludur.'
    if (form.email && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.email)) {
      newErrors.email = 'Geçerli bir e-posta adresi girin.'
    }
    setErrors(newErrors)
    return Object.keys(newErrors).length === 0
  }

  const handleClose = () => {
    if (isDirty.current) {
      if (!window.confirm('Kaydedilmemiş değişiklikler var. Çıkmak istiyor musunuz?')) return
    }
    onClose()
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!validate()) return

    setSaving(true)
    setApiError(null)

    const payload: PersonCreate = {
      first_name: form.first_name.trim(),
      last_name: form.last_name.trim(),
      ...(form.national_id ? { national_id: form.national_id } : {}),
      ...(form.birth_date ? { birth_date: form.birth_date } : {}),
      ...(form.gender ? { gender: form.gender as Gender } : {}),
      ...(form.phone ? { phone: form.phone } : {}),
      ...(form.email ? { email: form.email } : {}),
      ...(form.address ? { address: form.address } : {}),
      ...(form.emergency_contact_name
        ? { emergency_contact_name: form.emergency_contact_name }
        : {}),
      ...(form.emergency_contact_phone
        ? { emergency_contact_phone: form.emergency_contact_phone }
        : {}),
      ...(form.blood_type ? { blood_type: form.blood_type as BloodType } : {}),
      ...(form.notes ? { notes: form.notes } : {}),
      role_codes: form.role_codes,
    }

    try {
      let saved: Person
      if (person) {
        const resp = await personsApi.update(person.id, payload)
        saved = resp.data
      } else {
        const resp = await personsApi.create(payload)
        saved = resp.data
      }
      isDirty.current = false
      onSaved(saved)
      onClose()
    } catch (err: unknown) {
      const axiosErr = err as { response?: { data?: { detail?: string } } }
      setApiError(
        axiosErr.response?.data?.detail ?? 'Kayıt sırasında bir hata oluştu.'
      )
    } finally {
      setSaving(false)
    }
  }

  if (!isOpen) return null

  return (
    <div className="modal-overlay" onClick={(e) => e.target === e.currentTarget && handleClose()}>
      <div className="modal-box">
        <div className="modal-header">
          <h2 className="modal-title">
            {person ? 'Kişiyi Düzenle' : 'Yeni Kişi Ekle'}
          </h2>
          <button className="modal-close" onClick={handleClose} type="button">
            ✕
          </button>
        </div>

        <form onSubmit={handleSubmit}>
          <div className="modal-body">
            {apiError && (
              <div className="alert alert-error" style={{ marginBottom: '16px' }}>
                <span>⚠️</span>
                <span>{apiError}</span>
              </div>
            )}

            <div className="form-row">
              <div className="form-group">
                <label className="form-label required" htmlFor="first_name">Ad</label>
                <input
                  id="first_name"
                  name="first_name"
                  className={`form-input${errors.first_name ? ' error' : ''}`}
                  value={form.first_name}
                  onChange={handleChange}
                  placeholder="Ad"
                  maxLength={100}
                />
                {errors.first_name && (
                  <span className="form-error">{errors.first_name}</span>
                )}
              </div>
              <div className="form-group">
                <label className="form-label required" htmlFor="last_name">Soyad</label>
                <input
                  id="last_name"
                  name="last_name"
                  className={`form-input${errors.last_name ? ' error' : ''}`}
                  value={form.last_name}
                  onChange={handleChange}
                  placeholder="Soyad"
                  maxLength={100}
                />
                {errors.last_name && (
                  <span className="form-error">{errors.last_name}</span>
                )}
              </div>
            </div>

            <div className="form-row">
              <div className="form-group">
                <label className="form-label" htmlFor="national_id">TC / Pasaport No</label>
                <input
                  id="national_id"
                  name="national_id"
                  className="form-input"
                  value={form.national_id}
                  onChange={handleChange}
                  placeholder="TC Kimlik veya Pasaport No"
                  maxLength={20}
                />
              </div>
              <div className="form-group">
                <label className="form-label" htmlFor="birth_date">Doğum Tarihi</label>
                <input
                  id="birth_date"
                  name="birth_date"
                  type="date"
                  className="form-input"
                  value={form.birth_date}
                  onChange={handleChange}
                />
              </div>
            </div>

            <div className="form-row">
              <div className="form-group">
                <label className="form-label" htmlFor="gender">Cinsiyet</label>
                <select
                  id="gender"
                  name="gender"
                  className="form-select"
                  value={form.gender}
                  onChange={handleChange}
                >
                  <option value="">Seçiniz</option>
                  {GENDER_OPTIONS.map((g) => (
                    <option key={g.value} value={g.value}>{g.label}</option>
                  ))}
                </select>
              </div>
              <div className="form-group">
                <label className="form-label" htmlFor="blood_type">Kan Grubu</label>
                <select
                  id="blood_type"
                  name="blood_type"
                  className="form-select"
                  value={form.blood_type}
                  onChange={handleChange}
                >
                  <option value="">Seçiniz</option>
                  {BLOOD_TYPE_OPTIONS.map((bt) => (
                    <option key={bt} value={bt}>{bt}</option>
                  ))}
                </select>
              </div>
            </div>

            <div className="form-row">
              <div className="form-group">
                <label className="form-label" htmlFor="phone">Telefon</label>
                <input
                  id="phone"
                  name="phone"
                  className="form-input"
                  value={form.phone}
                  onChange={handleChange}
                  placeholder="05XX XXX XX XX"
                  maxLength={20}
                />
              </div>
              <div className="form-group">
                <label className="form-label" htmlFor="email">E-posta</label>
                <input
                  id="email"
                  name="email"
                  type="email"
                  className={`form-input${errors.email ? ' error' : ''}`}
                  value={form.email}
                  onChange={handleChange}
                  placeholder="ornek@email.com"
                />
                {errors.email && (
                  <span className="form-error">{errors.email}</span>
                )}
              </div>
            </div>

            <div className="form-group">
              <label className="form-label" htmlFor="address">Adres</label>
              <textarea
                id="address"
                name="address"
                className="form-textarea"
                value={form.address}
                onChange={handleChange}
                placeholder="Adres"
                rows={2}
              />
            </div>

            <div className="form-row">
              <div className="form-group">
                <label className="form-label" htmlFor="emergency_contact_name">Acil Kişi</label>
                <input
                  id="emergency_contact_name"
                  name="emergency_contact_name"
                  className="form-input"
                  value={form.emergency_contact_name}
                  onChange={handleChange}
                  placeholder="Ad Soyad"
                  maxLength={200}
                />
              </div>
              <div className="form-group">
                <label className="form-label" htmlFor="emergency_contact_phone">Acil Telefon</label>
                <input
                  id="emergency_contact_phone"
                  name="emergency_contact_phone"
                  className="form-input"
                  value={form.emergency_contact_phone}
                  onChange={handleChange}
                  placeholder="05XX XXX XX XX"
                  maxLength={20}
                />
              </div>
            </div>

            <div className="form-group">
              <label className="form-label" htmlFor="notes">Notlar</label>
              <textarea
                id="notes"
                name="notes"
                className="form-textarea"
                value={form.notes}
                onChange={handleChange}
                placeholder="Kişi hakkında ek notlar"
                rows={2}
              />
            </div>

            <div className="form-group">
              <label className="form-label">Roller</label>
              <div className="form-checkboxes">
                {ROLE_OPTIONS.map((r) => (
                  <label key={r.code} className="form-checkbox-item">
                    <input
                      type="checkbox"
                      checked={form.role_codes.includes(r.code)}
                      onChange={() => handleRoleToggle(r.code)}
                    />
                    {r.label}
                  </label>
                ))}
              </div>
            </div>
          </div>

          <div className="modal-footer">
            <button
              type="button"
              className="btn btn-secondary"
              onClick={handleClose}
              disabled={saving}
            >
              İptal
            </button>
            <button type="submit" className="btn btn-primary" disabled={saving}>
              {saving ? (
                <>
                  <span className="loading-spinner" style={{ width: 14, height: 14 }} />
                  Kaydediliyor...
                </>
              ) : (
                person ? 'Güncelle' : 'Kaydet'
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
