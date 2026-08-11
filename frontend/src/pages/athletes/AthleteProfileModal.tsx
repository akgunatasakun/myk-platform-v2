/**
 * Sporcu profili oluşturma / güncelleme modalı.
 * Backend: PATCH /api/v1/athletes/{person_id}
 */
import { useEffect, useState } from 'react'
import { athletesApi } from '@/api/athletes'
import type { AthleteDetailOut, AthleteLevel, AthleteProfileUpdate } from '@/types/athlete'

interface Props {
  isOpen: boolean
  onClose: () => void
  personId: string
  profile: AthleteDetailOut
  onSaved: (updated: AthleteDetailOut) => void
}

const LEVELS: { value: AthleteLevel; label: string }[] = [
  { value: 'baslangic', label: 'Başlangıç' },
  { value: 'orta', label: 'Orta' },
  { value: 'ileri', label: 'İleri' },
  { value: 'elit', label: 'Elit' },
]

export default function AthleteProfileModal({ isOpen, onClose, personId, profile, onSaved }: Props) {
  const ap = profile.athlete_profile

  const [form, setForm] = useState<AthleteProfileUpdate>({})
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!isOpen) return
    setError(null)
    setForm({
      class_name: ap?.class_name ?? null,
      level: ap?.level ?? 'baslangic',
      license_no: ap?.license_no ?? null,
      license_expiry_date: ap?.license_expiry_date ?? null,
      visa_expiry_date: ap?.visa_expiry_date ?? null,
      health_report_expiry_date: ap?.health_report_expiry_date ?? null,
      swimming_qualified: ap?.swimming_qualified ?? false,
      allergies: ap?.allergies ?? null,
      special_conditions: ap?.special_conditions ?? null,
      kvkk_consent: ap?.kvkk_consent ?? false,
      kvkk_text_version: ap?.kvkk_text_version ?? null,
      photo_video_consent: ap?.photo_video_consent ?? false,
    })
  }, [isOpen, ap])

  const set = <K extends keyof AthleteProfileUpdate>(key: K, value: AthleteProfileUpdate[K]) => {
    setForm((f) => ({ ...f, [key]: value }))
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setSaving(true)
    setError(null)
    try {
      const r = await athletesApi.updateProfile(personId, form)
      onSaved(r.data)
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
      <div className="modal" style={{ maxWidth: 600 }} onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2 className="modal-title">Sporcu Profili</h2>
          <button className="modal-close" onClick={onClose}>×</button>
        </div>

        <form onSubmit={handleSubmit}>
          <div className="modal-body" style={{ maxHeight: '70vh', overflowY: 'auto' }}>
            {error && (
              <div className="alert alert-error" style={{ marginBottom: 12 }}>
                <span>⚠️</span><span>{error}</span>
              </div>
            )}

            {/* Sportif sınıf & seviye */}
            <div style={{ fontWeight: 600, fontSize: 13, color: 'var(--color-text-muted)', marginBottom: 8, marginTop: 4, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
              Sportif Bilgiler
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 16 }}>
              <div className="form-group">
                <label className="form-label">Yelken Sınıfı</label>
                <input
                  className="form-input"
                  value={form.class_name ?? ''}
                  onChange={(e) => set('class_name', e.target.value || null)}
                  placeholder="örn. Optimist, ILCA, 420"
                />
              </div>
              <div className="form-group">
                <label className="form-label">Seviye</label>
                <select
                  className="form-select"
                  value={form.level ?? 'baslangic'}
                  onChange={(e) => set('level', e.target.value as AthleteLevel)}
                >
                  {LEVELS.map((l) => (
                    <option key={l.value} value={l.value}>{l.label}</option>
                  ))}
                </select>
              </div>
            </div>

            {/* Lisans & vize */}
            <div style={{ fontWeight: 600, fontSize: 13, color: 'var(--color-text-muted)', marginBottom: 8, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
              Lisans & Vize
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 12, marginBottom: 16 }}>
              <div className="form-group" style={{ gridColumn: '1 / -1' }}>
                <label className="form-label">Lisans No</label>
                <input
                  className="form-input"
                  value={form.license_no ?? ''}
                  onChange={(e) => set('license_no', e.target.value || null)}
                  placeholder="TYF-XXXX"
                />
              </div>
              <div className="form-group">
                <label className="form-label">Lisans Bitiş</label>
                <input
                  type="date"
                  className="form-input"
                  value={form.license_expiry_date ?? ''}
                  onChange={(e) => set('license_expiry_date', e.target.value || null)}
                />
              </div>
              <div className="form-group">
                <label className="form-label">Vize Bitiş</label>
                <input
                  type="date"
                  className="form-input"
                  value={form.visa_expiry_date ?? ''}
                  onChange={(e) => set('visa_expiry_date', e.target.value || null)}
                />
              </div>
            </div>

            {/* Sağlık */}
            <div style={{ fontWeight: 600, fontSize: 13, color: 'var(--color-text-muted)', marginBottom: 8, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
              Sağlık
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 16 }}>
              <div className="form-group">
                <label className="form-label">Sağlık Raporu Bitiş</label>
                <input
                  type="date"
                  className="form-input"
                  value={form.health_report_expiry_date ?? ''}
                  onChange={(e) => set('health_report_expiry_date', e.target.value || null)}
                />
              </div>
              <div className="form-group" style={{ display: 'flex', alignItems: 'center', paddingTop: 24 }}>
                <label style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer', fontSize: 14 }}>
                  <input
                    type="checkbox"
                    checked={form.swimming_qualified ?? false}
                    onChange={(e) => set('swimming_qualified', e.target.checked)}
                  />
                  Yüzme Yeterliliği Var
                </label>
              </div>
            </div>

            <div className="form-group" style={{ marginBottom: 8 }}>
              <label className="form-label">Alerji</label>
              <textarea
                className="form-input"
                rows={2}
                value={form.allergies ?? ''}
                onChange={(e) => set('allergies', e.target.value || null)}
                placeholder="Bilinen alerjiler"
              />
            </div>
            <div className="form-group" style={{ marginBottom: 16 }}>
              <label className="form-label">Özel Durum</label>
              <textarea
                className="form-input"
                rows={2}
                value={form.special_conditions ?? ''}
                onChange={(e) => set('special_conditions', e.target.value || null)}
                placeholder="Dikkat edilmesi gereken durumlar"
              />
            </div>

            {/* KVKK & izinler */}
            <div style={{ fontWeight: 600, fontSize: 13, color: 'var(--color-text-muted)', marginBottom: 8, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
              KVKK & İzinler
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              <label style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer', fontSize: 14 }}>
                <input
                  type="checkbox"
                  checked={form.kvkk_consent ?? false}
                  onChange={(e) => set('kvkk_consent', e.target.checked)}
                />
                KVKK Onayı Verildi
              </label>
              <label style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer', fontSize: 14 }}>
                <input
                  type="checkbox"
                  checked={form.photo_video_consent ?? false}
                  onChange={(e) => set('photo_video_consent', e.target.checked)}
                />
                Fotoğraf / Video Yayın İzni
              </label>
            </div>
          </div>

          <div className="modal-footer">
            <button type="button" className="btn btn-ghost" onClick={onClose} disabled={saving}>
              İptal
            </button>
            <button type="submit" className="btn btn-primary" disabled={saving}>
              {saving ? 'Kaydediliyor…' : 'Kaydet'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
