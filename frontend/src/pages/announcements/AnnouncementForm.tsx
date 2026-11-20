import { useState } from 'react'
import { announcementsApi, AUDIENCE_LABELS, ANNOUNCEMENT_STATUSES } from '@/api/announcements'
import type { Announcement, AnnouncementInput } from '@/api/announcements'
import type { Role } from '@/types/auth'

export default function AnnouncementForm({ item, onClose, onSaved }: { item: Announcement | null; onClose: () => void; onSaved: () => void }) {
  const [form, setForm] = useState<AnnouncementInput>(item ?? { title: '', body: '', status: 'taslak', important: false, starts_on: null, ends_on: null, target_roles: [] })
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const invalidDates = !!form.starts_on && !!form.ends_on && form.ends_on < form.starts_on
  async function submit(e: React.FormEvent) {
    e.preventDefault(); setError(''); setSaving(true)
    const data: AnnouncementInput = { title: form.title.trim(), body: form.body.trim(), status: form.status, important: form.important, starts_on: form.starts_on, ends_on: form.ends_on, target_roles: form.target_roles }
    try {
      if (item) await announcementsApi.update(item.id, data)
      else await announcementsApi.create(data)
      onSaved()
    } catch { setError('Duyuru kaydedilemedi. Bilgileri kontrol edip tekrar deneyin.') }
    finally { setSaving(false) }
  }
  function toggleRole(role: Role) {
    setForm({ ...form, target_roles: form.target_roles.includes(role) ? form.target_roles.filter((r) => r !== role) : [...form.target_roles, role] })
  }
  return <div className="modal-overlay"><div className="modal" role="dialog" aria-modal="true" aria-labelledby="announcement-title" style={{ maxWidth: 700 }}>
    <div className="modal-header"><h2 id="announcement-title">{item ? 'Duyuruyu Düzenle' : 'Yeni Duyuru'}</h2><button className="btn btn-ghost" disabled={saving} onClick={onClose} aria-label="Kapat">×</button></div>
    <form onSubmit={submit}><div className="modal-body">
      {error && <p role="alert">{error}</p>}
      <div className="form-group"><label className="form-label" htmlFor="ann-title">Başlık *</label><input autoFocus className="form-input" id="ann-title" value={form.title} maxLength={200} required onChange={(e) => setForm({ ...form, title: e.target.value })} /></div>
      <div className="form-group"><label className="form-label" htmlFor="ann-body">Duyuru Metni *</label><textarea className="form-input" id="ann-body" rows={6} value={form.body} maxLength={20000} required onChange={(e) => setForm({ ...form, body: e.target.value })} /></div>
      <div className="form-group"><label className="form-label" htmlFor="ann-status">Durum</label><select className="form-select" id="ann-status" value={form.status} onChange={(e) => setForm({ ...form, status: e.target.value as AnnouncementInput['status'] })}>{Object.entries(ANNOUNCEMENT_STATUSES).map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select></div>
      <div className="form-group"><label><input type="checkbox" checked={form.important} onChange={(e) => setForm({ ...form, important: e.target.checked })} /> Önemli duyuru (listenin başında göster)</label></div>
      <div className="form-row">
        <div className="form-group"><label className="form-label" htmlFor="ann-start">Yayın Başlangıcı</label><input className="form-input" id="ann-start" type="date" value={form.starts_on ?? ''} onChange={(e) => setForm({ ...form, starts_on: e.target.value || null })} /></div>
        <div className="form-group"><label className="form-label" htmlFor="ann-end">Yayın Bitişi</label><input className="form-input" id="ann-end" type="date" min={form.starts_on ?? undefined} value={form.ends_on ?? ''} onChange={(e) => setForm({ ...form, ends_on: e.target.value || null })} /></div>
      </div>
      <p>Türkiye saati esas alınır. Bitiş günü dahildir. Boş tarih alanları yayın süresini sınırlamaz.</p>
      {invalidDates && <p role="alert">Bitiş tarihi başlangıç tarihinden önce olamaz.</p>}
      <fieldset style={{ border: '1px solid var(--color-border)', padding: 12 }}><legend>Hedef Kitle</legend>
        <p>{form.target_roles.length ? `${form.target_roles.length} rol seçili` : 'Rol seçilmediğinde tüm kulüp kullanıcıları görür.'}</p>
        <div className="announcement-audiences">{Object.entries(AUDIENCE_LABELS).map(([role, label]) => <label key={role}><input type="checkbox" checked={form.target_roles.includes(role as Role)} onChange={() => toggleRole(role as Role)} /> {label}</label>)}</div>
      </fieldset>
    </div><div className="modal-footer"><button type="button" className="btn btn-ghost" disabled={saving} onClick={onClose}>Vazgeç</button><button className="btn btn-primary" disabled={saving || invalidDates || !form.title.trim() || !form.body.trim()}>{saving ? 'Kaydediliyor…' : 'Kaydet'}</button></div></form>
  </div></div>
}
