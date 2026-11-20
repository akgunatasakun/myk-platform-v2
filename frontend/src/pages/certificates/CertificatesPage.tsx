import { useEffect, useState } from 'react'
import { isAxiosError } from 'axios'
import { Link, useSearchParams } from 'react-router-dom'
import AppShell from '@/components/layout/AppShell'
import { useAuth } from '@/hooks/useAuth'
import { certificatesApi, certificateParams, CERTIFICATE_MANAGERS, CERTIFICATE_STATES } from '@/api/certificates'
import type { Certificate, CertificateOption } from '@/api/certificates'

type Form = { kind: 'create' | 'edit' | 'issue' | 'revoke'; item?: Certificate }
const dateLabel = (date: string | null) => date ? new Date(date + 'T00:00:00').toLocaleDateString('tr-TR') : '—'
function message(error: unknown) {
  const detail = isAxiosError(error) ? error.response?.data?.detail : undefined
  return typeof detail === 'string' ? detail : 'İşlem tamamlanamadı. Bilgileri kontrol edip tekrar deneyin.'
}

export default function CertificatesPage() {
  const { user } = useAuth()
  const manage = CERTIFICATE_MANAGERS.includes(user?.role ?? '')
  const canOpenTraining = ['super_admin', 'kulup_yonetici', 'baskan', 'sportif_direktor', 'basantrenor', 'antrenor', 'sporcu', 'veli'].includes(user?.role ?? '')
  const [url, setUrl] = useSearchParams()
  const params = certificateParams(url)
  const queryKey = JSON.stringify(params)
  const [data, setData] = useState<{ items: Certificate[]; total: number } | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [refresh, setRefresh] = useState(0)
  const [form, setForm] = useState<Form | null>(null)
  const [exporting, setExporting] = useState(false)
  const [deleting, setDeleting] = useState(false)

  const change = (key: string, value: string) => setUrl((old) => {
    const next = new URLSearchParams(old)
    if (value) next.set(key, value); else next.delete(key)
    if (key !== 'page') next.delete('page')
    return next
  }, { replace: key === 'q' })

  useEffect(() => {
    let cancelled = false
    setLoading(true); setError('')
    const parsed = JSON.parse(queryKey)
    const timer = setTimeout(() => {
      certificatesApi.list(parsed).then((r) => {
        if (cancelled) return
        if (parsed.skip > 0 && parsed.skip >= r.data.total) {
          setUrl((old) => { const next = new URLSearchParams(old); next.delete('page'); return next }, { replace: true })
          return
        }
        setData(r.data)
      }).catch((e) => { if (!cancelled) setError(message(e)) }).finally(() => { if (!cancelled) setLoading(false) })
    }, 300)
    return () => { cancelled = true; clearTimeout(timer) }
  }, [queryKey, refresh, setUrl])

  const remove = async (item: Certificate) => {
    if (!window.confirm(`${item.person_name} için sertifika taslağı silinsin mi?`)) return
    setDeleting(true)
    try { await certificatesApi.deleteDraft(item.id); setRefresh((v) => v + 1); setNotice('Taslak silindi.') }
    catch (e) { setNotice(message(e)) }
    finally { setDeleting(false) }
  }
  const exportCsv = async () => {
    setExporting(true)
    try {
      const filters = { search: params.search, state: params.state, course_id: params.course_id, enrollment_id: params.enrollment_id }
      const response = await certificatesApi.exportCsv(filters)
      const blobUrl = URL.createObjectURL(response.data)
      const link = document.createElement('a'); link.href = blobUrl; link.download = 'myk-sertifikalar.csv'; link.click()
      URL.revokeObjectURL(blobUrl); setNotice('Filtrelenen sertifika kayıtları dışa aktarıldı.')
    } catch { setNotice('Dışa aktarma tamamlanamadı. Filtreyi daraltıp tekrar deneyin.') }
    finally { setExporting(false) }
  }
  return <AppShell title="Sertifika Kayıtları">
    <div className="page-header"><div><h1 className="page-title">Sertifika Kayıtları</h1><p>Kulübün düzenlediği eğitim sertifikalarını katılımcı bazında takip edin.</p></div><div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
      <button className="btn btn-secondary" disabled={exporting || loading || !data?.total} onClick={exportCsv}>{exporting ? 'Hazırlanıyor…' : 'CSV İndir'}</button>
      {manage && <button className="btn btn-primary" onClick={() => setForm({ kind: 'create' })}>+ Sertifika Taslağı</button>}
    </div></div>
    <div className="filter-bar">
      <input className="form-input" aria-label="Sertifika ara" placeholder="Katılımcı, kurs veya sertifika numarası…" value={url.get('q') ?? ''} onChange={(e) => change('q', e.target.value)} />
      <select className="form-select" aria-label="Sertifika durumu" value={params.state ?? ''} onChange={(e) => change('state', e.target.value)}><option value="">Tüm Durumlar</option>{Object.entries(CERTIFICATE_STATES).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select>
      {(params.course_id || params.enrollment_id) && <button className="btn btn-ghost" onClick={() => setUrl((old) => { const next = new URLSearchParams(old); next.delete('course_id'); next.delete('enrollment_id'); next.delete('page'); return next })}>Eğitim / katılımcı filtresini kaldır</button>}
    </div>
    {params.course_id && canOpenTraining && <p><Link to={`/egitimler/${params.course_id}`}>Eğitim ayrıntısına dön</Link></p>}
    {notice && <p role="status">{notice}</p>}
    {error && <div role="alert" className="alert alert-error">{error}<button className="btn btn-ghost" onClick={() => setRefresh((v) => v + 1)}>Tekrar Dene</button></div>}
    {loading ? <div className="loading-center"><span className="loading-spinner lg" /></div> : !error && <>
      <p role="status">{data?.total ?? 0} sertifika kaydı</p>
      <div className="table-container">{!data?.items.length ? <div className="empty-state">Bu filtrelere uygun sertifika kaydı bulunamadı.</div> : <table className="data-table"><thead><tr><th>Katılımcı / Kurs</th><th>Sertifika / Numara</th><th>Durum</th><th>Düzenleme</th><th>Geçerlilik</th>{manage && <th>İşlemler</th>}</tr></thead><tbody>{data.items.map((item) => <tr key={item.id}>
        <td><strong>{item.person_name}</strong><div>{item.course_name}</div></td>
        <td>{item.title}<div>{item.number ?? 'Numara düzenleme sırasında verilir'}</div></td>
        <td><span className={`badge ${item.state === 'issued' ? 'badge-aktif' : item.state === 'draft' ? 'badge-planlandi' : 'badge-iptal'}`}>{CERTIFICATE_STATES[item.state]}</span>{item.revocation_reason && <div style={{ fontSize: 12 }}>{item.revocation_reason}</div>}</td>
        <td>{dateLabel(item.issued_on)}</td><td>{dateLabel(item.expires_on)}</td>
        {manage && <td><div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>{item.status === 'draft' && <><button className="btn btn-sm btn-secondary" onClick={() => setForm({ kind: 'edit', item })}>Taslağı Düzenle</button><button className="btn btn-sm btn-primary" onClick={() => setForm({ kind: 'issue', item })}>Düzenlendi İşaretle</button><button className="btn btn-sm btn-danger" disabled={deleting} onClick={() => remove(item)}>Taslağı Sil</button></>}{item.status === 'issued' && <button className="btn btn-sm btn-danger" onClick={() => setForm({ kind: 'revoke', item })}>İptal Et</button>}</div></td>}
      </tr>)}</tbody></table>}</div>
      {!!data?.total && <div className="pagination"><span>{(params.skip ?? 0) + 1}–{Math.min((params.skip ?? 0) + 20, data.total)} / {data.total}</span><button className="btn btn-sm btn-secondary" disabled={!params.skip} onClick={() => change('page', String((params.skip ?? 0) / 20))}>Önceki</button><button className="btn btn-sm btn-secondary" disabled={(params.skip ?? 0) + 20 >= data.total} onClick={() => change('page', String((params.skip ?? 0) / 20 + 2))}>Sonraki</button></div>}
    </>}
    {form && <CertificateForm key={`${form.kind}-${form.item?.id ?? 'new'}`} form={form} courseId={params.course_id} enrollmentId={params.enrollment_id} onClose={() => setForm(null)} onSaved={() => { setForm(null); setRefresh((v) => v + 1); setNotice('Sertifika kaydı güncellendi.') }} />}
  </AppShell>
}

function CertificateForm({ form, courseId, enrollmentId, onClose, onSaved }: { form: Form; courseId?: string; enrollmentId?: string; onClose: () => void; onSaved: () => void }) {
  const [search, setSearch] = useState('')
  const [options, setOptions] = useState<CertificateOption[]>([])
  const [selected, setSelected] = useState(enrollmentId ?? '')
  const [title, setTitle] = useState(form.item?.title ?? '')
  const [notes, setNotes] = useState(form.item?.notes ?? '')
  const [issuedOn, setIssuedOn] = useState(new Date().toLocaleDateString('sv-SE', { timeZone: 'Europe/Istanbul' }))
  const [expiresOn, setExpiresOn] = useState('')
  const [reason, setReason] = useState('')
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)
  const [loading, setLoading] = useState(form.kind === 'create')
  const [optionsError, setOptionsError] = useState('')
  const [retry, setRetry] = useState(0)
  useEffect(() => {
    if (form.kind !== 'create') return
    let cancelled = false
    setLoading(true); setOptionsError('')
    const timer = setTimeout(() => { certificatesApi.options({ search: search.trim() || undefined, course_id: courseId, enrollment_id: enrollmentId }).then((r) => {
      if (cancelled) return
      setOptions(r.data)
      if (enrollmentId && r.data.length === 1) { setSelected(r.data[0].id); setTitle((old) => old || `${r.data[0].course_name} Eğitim Sertifikası`) }
    }).catch((e) => { if (!cancelled) setOptionsError(message(e)) }).finally(() => { if (!cancelled) setLoading(false) }) }, 300)
    return () => { cancelled = true; clearTimeout(timer) }
  }, [form.kind, courseId, enrollmentId, search, retry])
  const submit = async (e: React.FormEvent) => {
    e.preventDefault(); setSaving(true); setError('')
    try {
      if (form.kind === 'create') await certificatesApi.create({ enrollment_id: selected, title: title.trim(), notes: notes.trim() || null })
      else if (form.kind === 'edit' && form.item) await certificatesApi.update(form.item.id, { title: title.trim(), notes: notes.trim() || null })
      else if (form.kind === 'issue' && form.item) await certificatesApi.issue(form.item.id, { issued_on: issuedOn, expires_on: expiresOn || null })
      else if (form.kind === 'revoke' && form.item) await certificatesApi.revoke(form.item.id, reason.trim())
      onSaved()
    } catch (e) { setError(message(e)) } finally { setSaving(false) }
  }
  const labels = { create: 'Sertifika Taslağı', edit: 'Taslağı Düzenle', issue: 'Sertifika Düzenleme Kaydı', revoke: 'Sertifikayı İptal Et' }
  return <div className="modal-overlay"><section className="modal" role="dialog" aria-modal="true" aria-labelledby="certificate-form-title" style={{ maxWidth: 600 }}><div className="modal-header"><h2 id="certificate-form-title" className="modal-title">{labels[form.kind]}</h2><button className="modal-close" aria-label="Kapat" disabled={saving} onClick={onClose}>×</button></div><form onSubmit={submit}><div className="modal-body">
    {error && <p role="alert" className="alert alert-error">{error}</p>}
    {form.item && <p><strong>{form.item.person_name}</strong> · {form.item.course_name}<br />{form.item.title}</p>}
    {form.kind === 'create' && <>
      <label className="form-label" htmlFor="certificate-choice-search">Katılımcı / kurs ara</label><input id="certificate-choice-search" className="form-input" value={search} onChange={(e) => { setSearch(e.target.value); if (!enrollmentId) setSelected('') }} placeholder="Ad soyad veya kurs adı" />
      <label className="form-label" htmlFor="certificate-enrollment">Eğitim Katılımcısı</label><select id="certificate-enrollment" className="form-select" required disabled={loading || !!optionsError} value={selected} onChange={(e) => { setSelected(e.target.value); const option = options.find((o) => o.id === e.target.value); setTitle(option ? `${option.course_name} Eğitim Sertifikası` : '') }}><option value="">Seçiniz</option>{options.map((o) => <option key={o.id} value={o.id}>{o.person_name} · {o.course_name}</option>)}</select>
      <p style={{ fontSize: 12 }}>Açık sertifika kaydı bulunmayan ilk 50 katılımcı gösterilir. Listeyi aramayla daraltabilirsiniz.</p>
      {loading && <p role="status">Katılımcılar yükleniyor…</p>}{optionsError && <p role="alert">{optionsError}<button type="button" className="btn btn-ghost" onClick={() => setRetry((v) => v + 1)}>Tekrar Dene</button></p>}
    </>}
    {(form.kind === 'create' || form.kind === 'edit') && <>
      <label className="form-label" htmlFor="certificate-title">Sertifika Adı</label><input id="certificate-title" className="form-input" required maxLength={240} value={title} onChange={(e) => setTitle(e.target.value)} />
      <label className="form-label" htmlFor="certificate-notes">Yönetim Notu</label><textarea id="certificate-notes" className="form-input" maxLength={4000} value={notes} onChange={(e) => setNotes(e.target.value)} />
    </>}
    {form.kind === 'issue' && <>
      <p>Bu işlem kulüp eğitim sertifikasını düzenlenmiş olarak kaydeder ve numara verir. Katılımcının eğitim sonucunu kontrol edin; sonrasında içerik değiştirilemez.</p>
      <label className="form-label" htmlFor="certificate-issued">Düzenleme Tarihi</label><input id="certificate-issued" type="date" className="form-input" required value={issuedOn} onChange={(e) => setIssuedOn(e.target.value)} />
      <label className="form-label" htmlFor="certificate-expiry">Geçerlilik Sonu (varsa)</label><input id="certificate-expiry" type="date" className="form-input" min={issuedOn} value={expiresOn} onChange={(e) => setExpiresOn(e.target.value)} />
    </>}
    {form.kind === 'revoke' && <><p>İptal kaydı geçmişte kalır. Gerekiyorsa aynı eğitim için yeni taslak açılabilir.</p><label className="form-label" htmlFor="certificate-reason">İptal Gerekçesi</label><textarea id="certificate-reason" className="form-input" required maxLength={2000} value={reason} onChange={(e) => setReason(e.target.value)} /></>}
  </div><div className="modal-footer"><button type="button" className="btn btn-ghost" disabled={saving} onClick={onClose}>Vazgeç</button><button className={`btn ${form.kind === 'revoke' ? 'btn-danger' : 'btn-primary'}`} type="submit" disabled={saving || (form.kind === 'create' && (loading || !!optionsError || !options.some((o) => o.id === selected)))}>{saving ? 'Kaydediliyor…' : form.kind === 'issue' ? 'Düzenlendi Olarak Kaydet' : form.kind === 'revoke' ? 'İptali Kaydet' : 'Taslağı Kaydet'}</button></div></form></section></div>
}
