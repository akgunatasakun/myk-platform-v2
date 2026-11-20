import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { announcementsApi } from '@/api/announcements'
import type { Announcement } from '@/api/announcements'

export default function AnnouncementSummary() {
  const [items, setItems] = useState<Announcement[] | null>(null)
  const [error, setError] = useState(false)
  const [attempt, setAttempt] = useState(0)
  useEffect(() => {
    let cancelled = false
    setItems(null); setError(false)
    announcementsApi.list({ limit: 3 }).then(({ data }) => { if (!cancelled) setItems(data.items) })
      .catch(() => { if (!cancelled) setError(true) })
    return () => { cancelled = true }
  }, [attempt])
  return <section className="card" style={{ marginBottom: 20 }} aria-label="Kulüp duyuruları"><div className="card-header">Kulüp Duyuruları</div><div className="card-body">
    {error ? <div role="alert">Duyurular yüklenemedi. <button className="btn btn-ghost" onClick={() => setAttempt((n) => n + 1)}>Tekrar Dene</button></div> : !items ? <p role="status">Duyurular yükleniyor…</p> : !items.length ? <p>Güncel duyuru bulunmuyor.</p> : items.map((a) => <div key={a.id} style={{ marginBottom: 16, overflowWrap: 'anywhere' }}><strong>{a.important && '📌 '}{a.title}</strong><p style={{ whiteSpace: 'pre-wrap' }}>{a.body.length > 300 ? a.body.slice(0, 300) + '…' : a.body}</p></div>)}
    <Link to="/duyurular">Tüm duyuruları aç</Link>
  </div></section>
}
