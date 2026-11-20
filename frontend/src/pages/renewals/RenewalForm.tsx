import { useEffect, useState } from 'react'
import { isAxiosError } from 'axios'
import { renewalsApi } from '@/api/renewals'
import type { Renewal, RenewalChoice, RenewalInput } from '@/api/renewals'

export default function RenewalForm({ item, renew, onClose, onSaved }: { item: Renewal | null; renew: boolean; onClose: () => void; onSaved: () => void }) {
  const [form, setForm] = useState<RenewalInput>(item ? { ...item, starts_on: renew ? null : item.starts_on, expires_on: renew ? null : item.expires_on, reference_no: renew ? null : item.reference_no } : { document_id: '', kind: 'police', reference_no: null, starts_on: null, expires_on: null, warning_days: 30, annual: true, responsible_user_id: null, notes: null })
  const [search, setSearch] = useState('')
  const [docs, setDocs] = useState<RenewalChoice[]>([])
  const [people, setPeople] = useState<RenewalChoice[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [loadError, setLoadError] = useState(false)
  const [attempt, setAttempt] = useState(0)
  const [saving, setSaving] = useState(false)
  const [more, setMore] = useState(false)
  const [loadingMore, setLoadingMore] = useState(false)
  useEffect(() => {
    let cancelled = false
    setLoading(true); setLoadError(false)
    Promise.all([renewalsApi.documents(search), renewalsApi.responsibles()]).then(([d, p]) => { if (!cancelled) { setDocs(d.data); setMore(d.data.length === 100); setPeople(p.data) } })
      .catch(() => { if (!cancelled) setLoadError(true) }).finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [search, attempt])
  async function loadMore() {
    setLoadingMore(true)
    try { const { data } = await renewalsApi.documents(search, docs.length); setDocs((old) => [...old, ...data]); setMore(data.length === 100) }
    catch { setError('Diğer belgeler yüklenemedi. Tekrar deneyin.') }
    finally { setLoadingMore(false) }
  }
  async function submit(e: React.FormEvent) {
    e.preventDefault(); setSaving(true); setError('')
    const data: RenewalInput = { document_id: form.document_id, kind: form.kind, reference_no: form.reference_no?.trim() || null, starts_on: form.starts_on, expires_on: form.expires_on, warning_days: form.warning_days, annual: form.annual, responsible_user_id: form.responsible_user_id, notes: form.notes?.trim() || null }
    try {
      if (item && renew) await renewalsApi.renew(item.id, data)
      else if (item) await renewalsApi.update(item.id, data)
      else await renewalsApi.create(data)
      onSaved()
    } catch (err) { const detail = isAxiosError(err) ? err.response?.data?.detail : null; setError(typeof detail === 'string' ? detail : 'Kayıt tamamlanamadı. Bilgileri kontrol edip tekrar deneyin.') }
    finally { setSaving(false) }
  }
  const invalidDates = !!form.starts_on && !!form.expires_on && form.expires_on < form.starts_on
  return <div className="modal-overlay"><div className="modal" role="dialog" aria-modal="true" aria-labelledby="renewal-form-title" style={{ maxWidth: 700 }}>
    <div className="modal-header"><h2 id="renewal-form-title">{renew ? 'Yeni Yenileme Dönemi' : item ? 'Takibi Düzenle' : 'Yenileme Takibi Ekle'}</h2><button className="btn btn-ghost" onClick={onClose} disabled={saving} aria-label="Kapat">×</button></div>
    <form onSubmit={submit}><div className="modal-body">
      {error && <p role="alert">{error}</p>}
      {loadError && <p role="alert">Belge veya sorumlu listesi yüklenemedi. <button type="button" className="btn btn-ghost" onClick={() => setAttempt((n) => n + 1)}>Tekrar Dene</button></p>}
      {loading && <p role="status">Seçenekler yükleniyor…</p>}
      {item ? <p><strong>Belge:</strong> {item.document_code} — {item.document_title}</p> : <>
        <div className="form-group"><label className="form-label" htmlFor="renewal-doc-search">Belge Ara</label><input id="renewal-doc-search" disabled={loadingMore} className="form-input" value={search} onChange={(e) => setSearch(e.target.value)} /></div>
        <div className="form-group"><label className="form-label" htmlFor="renewal-document">Bağlı Belge *</label><select id="renewal-document" className="form-select" required disabled={loading || loadError} value={form.document_id} onChange={(e) => setForm({ ...form, document_id: e.target.value })}><option value="">Belge seçin</option>{form.document_id && !docs.some((d) => d.id === form.document_id) && <option value={form.document_id}>Seçilen belge (arama dışında)</option>}{docs.map((d) => <option value={d.id} key={d.id}>{d.name}</option>)}</select></div>
        {more && <button type="button" className="btn btn-ghost" disabled={loading || loadingMore} onClick={loadMore}>Daha Fazla Belge</button>}
      </>}
      <div className="form-group"><label className="form-label" htmlFor="renewal-kind">Tür</label><select id="renewal-kind" className="form-select" value={form.kind} onChange={(e) => setForm({ ...form, kind: e.target.value as RenewalInput['kind'] })}><option value="police">Poliçe</option><option value="sozlesme">Sözleşme</option></select></div>
      <div className="form-group"><label className="form-label" htmlFor="renewal-ref">Poliçe / Sözleşme Numarası</label><input id="renewal-ref" className="form-input" maxLength={128} value={form.reference_no ?? ''} onChange={(e) => setForm({ ...form, reference_no: e.target.value || null })} /></div>
      <div className="form-row">
        <div className="form-group"><label className="form-label" htmlFor="renewal-start">Başlangıç Tarihi</label><input id="renewal-start" type="date" className="form-input" required={renew} value={form.starts_on ?? ''} onChange={(e) => setForm({ ...form, starts_on: e.target.value || null })} /></div>
        <div className="form-group"><label className="form-label" htmlFor="renewal-end">Bitiş Tarihi</label><input id="renewal-end" type="date" className="form-input" required={renew} min={form.starts_on ?? undefined} value={form.expires_on ?? ''} onChange={(e) => setForm({ ...form, expires_on: e.target.value || null })} /></div>
      </div>
      {!renew && <p>Bitiş tarihi bilinmiyorsa boş bırakın; kayıt eksik bilgi uyarısında gösterilir.</p>}
      {renew && <p>Önceki dönem geçmişte korunur. Yeni belge dosyasını bağlı belgenin revizyonlarına yükleyin. Bu işlem belgeyi hukuken yürürlüğe almaz.</p>}
      {invalidDates && <p role="alert">Bitiş tarihi başlangıçtan önce olamaz.</p>}
      <div className="form-group"><label className="form-label" htmlFor="renewal-warning">Kaç Gün Önce Uyarılsın?</label><input id="renewal-warning" type="number" min={1} max={365} className="form-input" value={form.warning_days} onChange={(e) => setForm({ ...form, warning_days: Number(e.target.value) })} /></div>
      <div className="form-group"><label><input type="checkbox" checked={form.annual} onChange={(e) => setForm({ ...form, annual: e.target.checked })} /> Yıllık yenilenir (tarihler otomatik değiştirilmez)</label></div>
      <div className="form-group"><label className="form-label" htmlFor="renewal-person">Sorumlu</label><select id="renewal-person" className="form-select" disabled={loading || loadError} value={form.responsible_user_id ?? ''} onChange={(e) => setForm({ ...form, responsible_user_id: e.target.value || null })}><option value="">Atanmamış</option>{form.responsible_user_id && !people.some((p) => p.id === form.responsible_user_id) && <option value={form.responsible_user_id}>Önceki sorumlu (aktif değil)</option>}{people.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}</select></div>
      <div className="form-group"><label className="form-label" htmlFor="renewal-notes">Notlar</label><textarea id="renewal-notes" className="form-input" rows={3} maxLength={10000} value={form.notes ?? ''} onChange={(e) => setForm({ ...form, notes: e.target.value || null })} /></div>
    </div><div className="modal-footer"><button type="button" className="btn btn-ghost" disabled={saving} onClick={onClose}>Vazgeç</button><button className="btn btn-primary" disabled={saving || loading || loadingMore || loadError || invalidDates || !form.document_id}>{saving ? 'Kaydediliyor…' : renew ? 'Yeni Dönemi Kaydet' : 'Kaydet'}</button></div></form>
  </div></div>
}
