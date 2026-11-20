import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { useAuth } from '@/hooks/useAuth'
import { renewalsApi, RENEWAL_READERS, RENEWAL_STATES } from '@/api/renewals'
import type { Renewal } from '@/api/renewals'
export default function RenewalSummary() {
  const { user } = useAuth()
  const allowed = RENEWAL_READERS.includes(user?.role ?? '')
  const [data, setData] = useState<{ items: Renewal[]; total: number } | null>(null)
  const [error, setError] = useState(false)
  const [attempt, setAttempt] = useState(0)
  useEffect(() => {
    if (!allowed) return
    let cancelled = false
    setData(null); setError(false)
    renewalsApi.list({ view: 'uyari', limit: 5 }).then(({ data: result }) => { if (!cancelled) setData(result) }).catch(() => { if (!cancelled) setError(true) })
    return () => { cancelled = true }
  }, [allowed, attempt])
  if (!allowed) return null
  return <section className="card" style={{ marginBottom: 20 }} aria-label="Poliçe ve sözleşme uyarıları"><div className="card-header">Poliçe ve Sözleşme Yenilemeleri{data && ` (${data.total})`}</div><div className="card-body">
    {error ? <div role="alert">Yenilemeler yüklenemedi. <button className="btn btn-ghost" onClick={() => setAttempt((n) => n + 1)}>Tekrar Dene</button></div> : !data ? <p role="status">Yenilemeler yükleniyor…</p> : !data.total ? <p>Yaklaşan, süresi dolmuş veya tarihi eksik takip kaydı yok.</p> : data.items.map((r) => <div key={r.id} style={{ marginBottom: 12, overflowWrap: 'anywhere' }}><strong>{r.document_title}</strong><div>{RENEWAL_STATES[r.state]} · {r.expires_on ? new Date(r.expires_on + 'T00:00:00').toLocaleDateString('tr-TR') : 'Bitiş tarihi bilinmiyor'} · {r.responsible_name ?? 'Sorumlu atanmamış'}</div></div>)}
    <Link to="/yenilemeler?view=uyari">Yenileme takibini aç</Link>
  </div></section>
}
