import { useEffect, useState } from 'react'
import { isAxiosError } from 'axios'
import { Link, useSearchParams } from 'react-router-dom'
import AppShell from '@/components/layout/AppShell'
import { useAuth } from '@/hooks/useAuth'
import { renewalsApi, RENEWAL_MANAGERS, RENEWAL_STATES } from '@/api/renewals'
import type { Renewal, RenewalParams } from '@/api/renewals'
import RenewalForm from './RenewalForm'

function dateLabel(value: string | null) { return value ? new Date(value + 'T00:00:00').toLocaleDateString('tr-TR') : 'Bilinmiyor' }
export default function RenewalsPage() {
  const { user } = useAuth()
  const manage = RENEWAL_MANAGERS.includes(user?.role ?? '')
  const [url, setUrl] = useSearchParams()
  const view = (['acik', 'gecmis', 'uyari', 'eksik', 'gecikti'].includes(url.get('view') ?? '') ? url.get('view') : 'acik') as RenewalParams['view']
  const [search, setSearch] = useState('')
  const [kind, setKind] = useState('')
  const [skip, setSkip] = useState(0)
  const [data, setData] = useState<{ items: Renewal[]; total: number } | null>(null)
  const [error, setError] = useState(false)
  const [attempt, setAttempt] = useState(0)
  const [form, setForm] = useState<{ item: Renewal | null; renew: boolean } | null>(null)
  const [exporting, setExporting] = useState(false)
  const [savingClosure, setSavingClosure] = useState(false)
  const [notice, setNotice] = useState('')
  useEffect(() => {
    let cancelled = false
    setData(null); setError(false)
    renewalsApi.list({ view, kind: kind as RenewalParams['kind'] || undefined, search: search || undefined, skip, limit: 20 }).then(({ data: result }) => {
      if (cancelled) return
      if (skip && skip >= result.total) { setSkip(Math.max(0, Math.floor((result.total - 1) / 20) * 20)); return }
      setData(result)
    }).catch(() => { if (!cancelled) setError(true) })
    return () => { cancelled = true }
  }, [view, kind, search, skip, attempt])
  async function changeClosure(item: Renewal) {
    if (!window.confirm(item.is_closed ? 'Bu dönem yeniden takibe alınsın mı?' : 'Bu dönem kapatılıp geçmişe taşınsın mı? Belge silinmez.')) return
    setSavingClosure(true); setNotice('')
    try { await renewalsApi.closure(item.id, !item.is_closed); setAttempt((n) => n + 1); setNotice('Takip durumu güncellendi.') }
    catch (err) { const detail = isAxiosError(err) ? err.response?.data?.detail : null; setNotice(typeof detail === 'string' ? detail : 'Takip durumu güncellenemedi.') }
    finally { setSavingClosure(false) }
  }
  async function exportCsv() {
    setExporting(true); setNotice('')
    try {
      const rows = await renewalsApi.listAll({ view, kind: kind as RenewalParams['kind'] || undefined, search: search || undefined })
      const cell = (v: string) => `"${(/^[\s]*[=+\-@]|^[\t\r\n]/.test(v) ? `'${v}` : v).replace(/"/g, '""')}"`
      const csv = [['Belge Kodu', 'Belge', 'Tür', 'Numara', 'Başlangıç', 'Bitiş', 'Uyarı Günü', 'Sorumlu', 'Durum', 'Yıllık', 'Notlar'], ...rows.map((r) => [r.document_code, r.document_title, r.kind === 'police' ? 'Poliçe' : 'Sözleşme', r.reference_no ?? '', r.starts_on ?? '', r.expires_on ?? '', String(r.warning_days), r.responsible_name ?? '', RENEWAL_STATES[r.state], r.annual ? 'Evet' : 'Hayır', r.notes ?? ''])].map((row) => row.map(cell).join(';')).join('\r\n')
      const link = document.createElement('a'); const target = URL.createObjectURL(new Blob(['\uFEFF' + csv], { type: 'text/csv;charset=utf-8' })); link.href = target; link.download = 'myk-yenilemeler.csv'; link.click(); URL.revokeObjectURL(target); setNotice(`${rows.length} kayıt dışa aktarıldı.`)
    } catch { setNotice('Dışa aktarma tamamlanamadı. Tekrar deneyin.') }
    finally { setExporting(false) }
  }
  return <AppShell title="Yenileme Takibi">
    <div className="page-header"><div><h1 className="page-title">Poliçe ve Sözleşme Yenilemeleri</h1><p>Belgelere bağlı dönemler, sorumlular ve yenileme uyarıları</p></div><div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}><button className="btn btn-ghost" disabled={!data || exporting} onClick={exportCsv}>CSV İndir</button>{manage && <button className="btn btn-primary" onClick={() => setForm({ item: null, renew: false })}>Takip Ekle</button>}</div></div>
    <div className="filter-bar">
      <input className="form-input" style={{ maxWidth: 300 }} aria-label="Yenileme ara" placeholder="Belge adı, kodu veya numara…" value={search} onChange={(e) => { setSearch(e.target.value); setSkip(0) }} />
      <select className="form-select" aria-label="Takip görünümü" value={view} onChange={(e) => { setUrl({ view: e.target.value }); setSkip(0) }}><option value="acik">Açık Takipler</option><option value="uyari">Tüm Uyarılar</option><option value="gecikti">Süresi Dolanlar</option><option value="eksik">Bitiş Tarihi Eksik</option><option value="gecmis">Geçmiş Dönemler</option></select>
      <select className="form-select" aria-label="Belge türü" value={kind} onChange={(e) => { setKind(e.target.value); setSkip(0) }}><option value="">Tüm Türler</option><option value="police">Poliçe</option><option value="sozlesme">Sözleşme</option></select>
    </div>
    {notice && <p role="status">{notice}</p>}
    {error ? <div role="alert">Yenilemeler yüklenemedi. <button className="btn btn-ghost" onClick={() => setAttempt((n) => n + 1)}>Tekrar Dene</button></div> : !data ? <p role="status">Yenilemeler yükleniyor…</p> : <>
      <p>{data.total} kayıt</p>{!data.items.length && <div className="card"><div className="card-body">Bu filtrelere uygun takip kaydı yok.</div></div>}
      <div className="task-grid">{data.items.map((r) => <article className="card" key={r.id}><div className="card-body">
        <h2 style={{ fontSize: 18, overflowWrap: 'anywhere' }}>{r.document_title}</h2>
        <p>{r.document_code} · {r.kind === 'police' ? 'Poliçe' : 'Sözleşme'}{r.reference_no && ` · ${r.reference_no}`}</p>
        <p><strong>{RENEWAL_STATES[r.state]}</strong>{r.days_remaining !== null && !r.is_closed && ` · ${r.days_remaining < 0 ? `${-r.days_remaining} gün geçti` : `${r.days_remaining} gün kaldı`}`}</p>
        <p>{dateLabel(r.starts_on)} – {dateLabel(r.expires_on)}</p>
        <p><strong>Sorumlu:</strong> {r.responsible_name ?? 'Atanmamış'} · {r.warning_days} gün önce uyarı{r.annual && ' · Yıllık yenileme'}</p>
        {r.notes && <p style={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}>{r.notes}</p>}
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>{user?.role !== 'muhasebe' && <Link className="btn btn-ghost" to={`/belgeler/${r.document_id}`}>Belgeyi Aç</Link>}{manage && <button className="btn btn-ghost" disabled={savingClosure} onClick={() => changeClosure(r)}>{r.is_closed ? 'Yeniden Takibe Al' : 'Takibi Kapat'}</button>}{manage && !r.is_closed && <><button className="btn btn-ghost" onClick={() => setForm({ item: r, renew: false })}>Düzenle</button><button className="btn btn-primary" onClick={() => setForm({ item: r, renew: true })}>Yeni Dönem / Yenile</button></>}</div>
      </div></article>)}</div>
      {data.total > 20 && <div style={{ display: 'flex', gap: 12, marginTop: 20 }}><button className="btn btn-ghost" disabled={!skip} onClick={() => setSkip((n) => Math.max(0, n - 20))}>← Önceki</button><span>{Math.floor(skip / 20) + 1} / {Math.ceil(data.total / 20)}</span><button className="btn btn-ghost" disabled={skip + 20 >= data.total} onClick={() => setSkip((n) => n + 20)}>Sonraki →</button></div>}
    </>}
    {form && <RenewalForm item={form.item} renew={form.renew} onClose={() => setForm(null)} onSaved={() => { setForm(null); setUrl({ view: 'acik' }); setSkip(0); setSearch(''); setKind(''); setAttempt((n) => n + 1); setNotice('Yenileme dönemi kaydedildi.') }} />}
  </AppShell>
}
