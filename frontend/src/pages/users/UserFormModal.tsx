import { useEffect, useRef, useState } from 'react'
import { usersApi } from '@/api/users'
import { personsApi } from '@/api/persons'
import type { UserOut, UserCreate, UserUpdate } from '@/types/user'
import type { Role } from '@/types/auth'

interface PersonOption {
  id: string
  label: string // "Ad Soyad (e-posta) · Rol"
}

// G8: Frontend rol listesi (super_admin kendi kendine atanamaz — backend da reddeder)
const ROLE_OPTIONS: { value: Role; label: string }[] = [
  { value: 'kulup_yonetici', label: 'Kulüp Yöneticisi' },
  { value: 'genel_sekreter', label: 'Genel Sekreter' },
  { value: 'baskan', label: 'Başkan' },
  { value: 'yk_uyesi', label: 'YK Üyesi' },
  { value: 'muhasebe', label: 'Muhasebe' },
  { value: 'sportif_direktor', label: 'Sportif Direktör' },
  { value: 'basantrenor', label: 'Baş Antrenör' },
  { value: 'antrenor', label: 'Antrenör' },
  { value: 'personel', label: 'Personel' },
  { value: 'saglik_sorumlusu', label: 'Sağlık Sorumlusu' },
  { value: 'guvenlik_operasyon', label: 'Güvenlik / Operasyon' },
  { value: 'veli', label: 'Veli' },
  { value: 'sporcu', label: 'Sporcu' },
  { value: 'uye', label: 'Üye' },
  { value: 'misafir', label: 'Misafir' },
]

const ROLES_REQUIRING_PERSON: Role[] = ['sporcu', 'antrenor']

interface Props {
  isOpen: boolean
  onClose: () => void
  user?: UserOut
  onSaved: (u: UserOut) => void
  /** Oluşturma sonrası geçici parola göstermek için */
  onCreated?: (tempPassword: string) => void
}

interface FormData {
  email: string
  full_name: string
  role: Role
  person_id: string
  is_active: boolean
}

const EMPTY_FORM: FormData = {
  email: '',
  full_name: '',
  role: 'uye',
  person_id: '',
  is_active: true,
}

export default function UserFormModal({ isOpen, onClose, user, onSaved, onCreated }: Props) {
  const [form, setForm] = useState<FormData>(EMPTY_FORM)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [personOptions, setPersonOptions] = useState<PersonOption[]>([])
  const firstRef = useRef<HTMLInputElement>(null)

  const isEdit = Boolean(user)

  useEffect(() => {
    if (isOpen) {
      setError(null)
      if (user) {
        setForm({
          email: user.email,
          full_name: user.full_name,
          role: user.role,
          person_id: user.person_id ?? '',
          is_active: user.is_active,
        })
      } else {
        setForm(EMPTY_FORM)
      }
      // Kişi kartı listesini yükle
      personsApi.list({ limit: 200, is_active: true }).then((r) => {
        const items = (r.data as { items: Array<{ id: string; first_name: string; last_name: string; email?: string; roles?: Array<{ role_code: string }> }> }).items
        setPersonOptions(
          items.map((p) => ({
            id: p.id,
            label: `${p.first_name} ${p.last_name}${p.email ? ` · ${p.email}` : ''}`,
          }))
        )
      }).catch(() => {/* sessiz başarısızlık */})
      setTimeout(() => firstRef.current?.focus(), 50)
    }
  }, [isOpen, user])

  if (!isOpen) return null

  const set = (field: keyof FormData, value: string | boolean | Role) =>
    setForm((prev) => ({ ...prev, [field]: value }))

  const roleRequiresPerson = ROLES_REQUIRING_PERSON.includes(form.role)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)

    if (!form.full_name.trim()) return setError('Ad Soyad zorunludur.')
    if (!isEdit && !form.email.trim()) return setError('E-posta zorunludur.')
    if (roleRequiresPerson && !form.person_id.trim())
      return setError(`'${form.role}' rolü için Person ID zorunludur.`)

    setSaving(true)
    try {
      if (isEdit && user) {
        const update: UserUpdate = {}
        if (form.role !== user.role) update.role = form.role
        if (form.is_active !== user.is_active) update.is_active = form.is_active
        if (form.full_name !== user.full_name) update.full_name = form.full_name
        const currentPersonId = user.person_id ?? ''
        if (form.person_id.trim() !== currentPersonId) {
          update.person_id = form.person_id.trim() || null
        }
        const resp = await usersApi.update(user.id, update)
        onSaved(resp.data)
        onClose()
      } else {
        const create: UserCreate = {
          email: form.email.trim(),
          full_name: form.full_name.trim(),
          role: form.role,
          person_id: form.person_id.trim() || null,
        }
        const resp = await usersApi.create(create)
        onSaved(resp.data)
        onCreated?.(resp.data.temp_password)
        onClose()
      }
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
        ?? 'Kayıt sırasında hata oluştu.'
      setError(msg)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2>{isEdit ? 'Kullanıcı Düzenle' : 'Yeni Kullanıcı'}</h2>
          <button className="modal-close" onClick={onClose} aria-label="Kapat">×</button>
        </div>

        <form onSubmit={handleSubmit} className="modal-body">
          {error && <div className="alert alert-error">{error}</div>}

          {!isEdit && (
            <div className="form-group">
              <label>E-posta *</label>
              <input
                ref={firstRef}
                type="email"
                className="form-control"
                value={form.email}
                onChange={(e) => set('email', e.target.value)}
                required
                autoComplete="off"
              />
            </div>
          )}

          <div className="form-group">
            <label>Ad Soyad *</label>
            <input
              ref={isEdit ? firstRef : undefined}
              type="text"
              className="form-control"
              value={form.full_name}
              onChange={(e) => set('full_name', e.target.value)}
              required
            />
          </div>

          <div className="form-group">
            <label>Rol *</label>
            <select
              className="form-control"
              value={form.role}
              onChange={(e) => set('role', e.target.value as Role)}
            >
              {ROLE_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>{o.label}</option>
              ))}
            </select>
          </div>

          <div className="form-group">
            <label>Bağlı Kişi Kartı {roleRequiresPerson ? '*' : '(isteğe bağlı)'}</label>
            <select
              className="form-control"
              value={form.person_id}
              onChange={(e) => set('person_id', e.target.value)}
            >
              <option value="">— Bağlantı yok —</option>
              {personOptions.map((p) => (
                <option key={p.id} value={p.id}>{p.label}</option>
              ))}
            </select>
            <small className="form-text text-muted">
              {roleRequiresPerson
                ? `'${form.role}' rolü için kişi kaydı bağlantısı zorunludur.`
                : 'Seçilmezse mevcut bağlantı kaldırılır.'}
            </small>
          </div>

          {isEdit && (
            <div className="form-group">
              <label className="checkbox-label">
                <input
                  type="checkbox"
                  checked={form.is_active}
                  onChange={(e) => set('is_active', e.target.checked)}
                />
                {' '}Hesap aktif
              </label>
            </div>
          )}

          <div className="modal-footer">
            <button type="button" className="btn btn-secondary" onClick={onClose} disabled={saving}>
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
