import { useEffect, useState } from 'react'
import AppShell from '@/components/layout/AppShell'
import { documentsApi } from '@/api/documents'
import type { Document } from '@/types/document'

// ── Kategori haritası — TYF kod prefix'ine göre ───────────────────────────────

const CATEGORIES = [
  { key: 'all',   label: 'Tümü' },
  { key: 'dingi', label: 'Dingi Yelken' },
  { key: 'kite',  label: 'Uçurtma Sörfü' },
  { key: 'wing',  label: 'Kanat Sörfü' },
  { key: 'staff', label: 'Eğitmen / Antrenör' },
]

function categoryKeyFromCode(code: string): string {
  if (code.startsWith('TYF-D'))  return 'dingi'
  if (code.startsWith('TYF-US')) return 'kite'
  if (code.startsWith('TYF-WS')) return 'wing'
  return 'staff'
}

// ── Sayfa ─────────────────────────────────────────────────────────────────────

export default function KutuphanePage() {
  const [docs, setDocs]               = useState<Document[]>([])
  const [loading, setLoading]         = useState(true)
  const [error, setError]             = useState<string | null>(null)
  const [activeCategory, setActive]   = useState('all')
  const [actionLoading, setActionLoading] = useState<string | null>(null) // `${docId}-preview|download`

  useEffect(() => {
    documentsApi
      .list({ owner_type: 'tyf_library' })
      .then((res) => setDocs(res.data))
      .catch(() => setError('Kütüphane yüklenemedi.'))
      .finally(() => setLoading(false))
  }, [])

  const filtered =
    activeCategory === 'all'
      ? docs
      : docs.filter((d) => categoryKeyFromCode(d.code) === activeCategory)

  const handleAction = async (doc: Document, action: 'preview' | 'download') => {
    const key = `${doc.id}-${action}`
    setActionLoading(key)
    try {
      const detail = (await documentsApi.get(doc.id)).data
      const rev = detail.revisions?.find((r) => r.is_current) ?? detail.revisions?.[0]
      if (!rev) { alert('Revizyon bulunamadı.'); return }
      const file = rev.files.find((f) => f.is_primary) ?? rev.files[0]
      if (!file) { alert('Dosya bulunamadı.'); return }
      if (action === 'preview') {
        await documentsApi.previewPdf(String(detail.id), String(rev.id), String(file.id))
      } else {
        await documentsApi.downloadFile(String(detail.id), String(rev.id), String(file.id))
      }
    } catch {
      alert('İşlem başarısız. Lütfen tekrar deneyin.')
    } finally {
      setActionLoading(null)
    }
  }

  return (
    <AppShell title="TYF Eğitim Kütüphanesi">
      <div className="page-header">
        <h1 className="page-title">TYF Eğitim Kütüphanesi</h1>
        <p className="page-subtitle">Türkiye Yelken Federasyonu eğitim dokümanları</p>
      </div>

      {error && (
        <div className="alert alert-error" style={{ marginBottom: '1rem' }}>
          {error}
        </div>
      )}

      {/* Kategori filtresi */}
      <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap', marginBottom: '1.5rem' }}>
        {CATEGORIES.map((cat) => (
          <button
            key={cat.key}
            className={`btn ${activeCategory === cat.key ? 'btn-primary' : 'btn-secondary'}`}
            style={{ fontSize: '0.85rem' }}
            onClick={() => setActive(cat.key)}
          >
            {cat.label}
          </button>
        ))}
      </div>

      {loading ? (
        <div style={{ display: 'flex', justifyContent: 'center', padding: '3rem' }}>
          <span className="loading-spinner lg" />
        </div>
      ) : filtered.length === 0 ? (
        <div className="empty-state">
          <div className="empty-state-icon">📚</div>
          <h3>Doküman bulunamadı</h3>
          <p>Bu kategoride henüz doküman yok.</p>
        </div>
      ) : (
        <div className="card-grid">
          {filtered.map((doc) => {
            const catLabel =
              CATEGORIES.find((c) => c.key === categoryKeyFromCode(doc.code))?.label ?? ''
            const previewLoading  = actionLoading === `${doc.id}-preview`
            const downloadLoading = actionLoading === `${doc.id}-download`
            const busy = previewLoading || downloadLoading
            return (
              <div key={doc.id} className="card">
                <div className="card-body">
                  <div
                    style={{
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'flex-start',
                      marginBottom: '0.5rem',
                    }}
                  >
                    <h3 className="card-title" style={{ margin: 0 }}>
                      {doc.title}
                    </h3>
                    <span
                      className="badge badge-info"
                      style={{ flexShrink: 0, marginLeft: '0.5rem', fontSize: '0.75rem' }}
                    >
                      {catLabel}
                    </span>
                  </div>
                  <p
                    style={{
                      fontSize: '0.8rem',
                      color: 'var(--color-text-secondary)',
                      margin: '0 0 1rem',
                    }}
                  >
                    {doc.code}
                  </p>
                  <div style={{ display: 'flex', gap: '0.5rem', marginTop: 'auto' }}>
                    <button
                      className="btn btn-primary"
                      disabled={busy}
                      onClick={() => handleAction(doc, 'preview')}
                    >
                      {previewLoading ? 'Açılıyor…' : 'Görüntüle'}
                    </button>
                    <button
                      className="btn btn-secondary"
                      disabled={busy}
                      onClick={() => handleAction(doc, 'download')}
                    >
                      {downloadLoading ? 'İndiriliyor…' : 'İndir'}
                    </button>
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      )}
    </AppShell>
  )
}
