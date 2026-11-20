import { useEffect, useState } from 'react'
import AppShell from '@/components/layout/AppShell'
import { useAuth } from '@/hooks/useAuth'
import { announcementsApi, ANNOUNCEMENT_MANAGERS, ANNOUNCEMENT_STATUSES, AUDIENCE_LABELS, publicationLabel } from '@/api/announcements'
import type { Announcement, AnnouncementInput } from '@/api/announcements'
import AnnouncementForm from './AnnouncementForm'

export default function AnnouncementsPage() {
  const { user } = useAuth()
  const canManage = ANNOUNCEMENT_MANAGERS.includes(user?.role ?? '')
  const [manage, setManage] = useState(false)
  const [search, setSearch] = useState('')
  const [status, setStatus] = useState('')
  const [skip, setSkip] = useState(0)
  const [data, setData] = useState<{ items: Announcement[]; total: number } | null>(null)
  const [error, setError] = useState(false)
  const [attempt, setAttempt] = useState(0)
  const [editing, setEditing] = useState<Announcement | null | undefined>(undefined)
  const [notice, setNotice] = useState('')
  const [exporting, setExporting] = useState(false)
  useEffect(() => {
    let cancelled = false
    setData(null); setError(false)
    announcementsApi.list({ manage: canManage && manage, search: search || undefined, status: (manage ? status : undefined) as AnnouncementInput['status'] | undefined || undefined, skip, limit: 20 })
      .then(({ data: result }) => { if (!cancelled) setData(result) })
      .catch(() => { if (!cancelled) setError(true) })
    return () => { cancelled = true }
  }, [canManage, manage, search, status, skip, attempt])
  async function exportCsv() {
    setExporting(true); setNotice('')
    try {
      const rows = await announcementsApi.listAll({ manage: canManage && manage, search: search || undefined, status: (manage ? status : undefined) as AnnouncementInput['status'] | undefined || undefined })
      const cell = (v: string) => `"${(/^[\s]*[=+\-@]|^[\t\r\n]/.test(v) ? `'${v}` : v).replace(/"/g, '""')}"`
      const content = [['Başlık', 'Metin', 'Durum', 'Önemli', 'Başlangıç', 'Bitiş', 'Hedef Kitle'], ...rows.map((a) => [a.title, a.body, publicationLabel(a), a.important ? 'Evet' : 'Hayır', a.starts_on ?? '', a.ends_on ?? '', a.target_roles.map((r) => AUDIENCE_LABELS[r]).join(', ') || 'Tüm Kulüp'])].map((row) => row.map(cell).join(';')).join('\r\n')
      const url = URL.createObjectURL(new Blob(['\uFEFF' + content], { type: 'text/csv;charset=utf-8' }))
      const link = document.createElement('a'); link.href = url; link.download = 'myk-duyurular.csv'; link.click(); URL.revokeObjectURL(url)
      setNotice(`${rows.length} duyuru dışa aktarıldı.`)
    } catch { setNotice('Dışa aktarma tamamlanamadı. Tekrar deneyin.') }
    finally { setExporting(false) }
  }
  return <AppShell title="Duyurular">
    <div className="page-header"><h1 className="page-title">Duyurular</h1><div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}><button className="btn btn-ghost" disabled={exporting || !data} onClick={exportCsv}>{exporting ? 'Hazırlanıyor…' : 'CSV İndir'}</button>{canManage && <button className="btn btn-primary" onClick={() => setEditing(null)}>Yeni Duyuru</button>}</div></div>
    <div className="filter-bar">
      <input className="form-input" style={{ maxWidth: 300 }} aria-label="Duyuru ara" placeholder="Başlık veya metin ara…" value={search} onChange={(e) => { setSearch(e.target.value); setSkip(0) }} />
      {canManage && <select className="form-select" aria-label="Duyuru görünümü" value={manage ? 'manage' : 'published'} onChange={(e) => { setManage(e.target.value === 'manage'); setSkip(0); setStatus('') }}><option value="published">Bana Gösterilen Duyurular</option><option value="manage">Duyuru Yönetimi (Tümü)</option></select>}
      {canManage && manage && <select className="form-select" aria-label="Durum filtresi" value={status} onChange={(e) => { setStatus(e.target.value); setSkip(0) }}><option value="">Tüm Durumlar</option>{Object.entries(ANNOUNCEMENT_STATUSES).map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select>}
    </div>
    {notice && <p role="status">{notice}</p>}
    {error ? <div role="alert">Duyurular yüklenemedi. <button className="btn btn-ghost" onClick={() => setAttempt((n) => n + 1)}>Tekrar Dene</button></div> : !data ? <p role="status">Duyurular yükleniyor…</p> : <>
      <p>{data.total} duyuru{manage && ' · Taslaklar ve yayın aralığı dışındaki duyurular dahil'}</p>
      {!data.items.length && <div className="card"><div className="card-body">Bu filtrelere uygun duyuru bulunmuyor.</div></div>}
      <div className="task-grid">{data.items.map((a) => <article className="card" key={a.id}><div className="card-body">
        <h2 style={{ fontSize: 18, overflowWrap: 'anywhere' }}>{a.important && '📌 '}{a.title}</h2>
        <p style={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}>{a.body}</p>
        <p>{publicationLabel(a)}{a.important && ' · Önemli'}</p>
        {manage && <><p><strong>Hedef:</strong> {a.target_roles.map((r) => AUDIENCE_LABELS[r]).join(', ') || 'Tüm Kulüp'}</p><p><strong>Yayın:</strong> {a.starts_on ?? 'Sınırsız'} – {a.ends_on ?? 'Sınırsız'}</p><button className="btn btn-ghost" onClick={() => setEditing(a)}>Düzenle / Arşivle</button></>}
      </div></article>)}</div>
      {data.total > 20 && <div style={{ display: 'flex', gap: 12, marginTop: 20 }}><button className="btn btn-ghost" disabled={!skip} onClick={() => setSkip((n) => Math.max(0, n - 20))}>← Önceki</button><span>{Math.floor(skip / 20) + 1} / {Math.ceil(data.total / 20)}</span><button className="btn btn-ghost" disabled={skip + 20 >= data.total} onClick={() => setSkip((n) => n + 20)}>Sonraki →</button></div>}
    </>}
    {editing !== undefined && <AnnouncementForm item={editing} onClose={() => setEditing(undefined)} onSaved={() => { setEditing(undefined); setManage(true); setSkip(0); setStatus(''); setSearch(''); setAttempt((n) => n + 1); setNotice('Duyuru kaydedildi.') }} />}
  </AppShell>
}
