import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import AppShell from '@/components/layout/AppShell'
import { documentsApi } from '@/api/documents'
import type { Document, DocumentType, ContentStatus } from '@/types/document'

const TYPE_LABEL: Record<string, string> = {
  prosedur: 'Prosedür',
  talimati: 'Talimat',
  form: 'Form',
  el_kitabi: 'El Kitabı',
  egitim_materyali: 'Eğitim Mat.',
  operasyonel: 'Operasyonel',
  sporcu_belgesi: 'Sporcu Belgesi',
  ekipman_belgesi: 'Ekipman Belgesi',
  diger: 'Diğer',
}

const TYPE_OPTIONS: { value: DocumentType | ''; label: string }[] = [
  { value: '', label: 'Tüm Türler' },
  { value: 'prosedur', label: 'Prosedür' },
  { value: 'talimati', label: 'Talimat' },
  { value: 'form', label: 'Form' },
  { value: 'el_kitabi', label: 'El Kitabı' },
  { value: 'egitim_materyali', label: 'Eğitim Materyali' },
  { value: 'operasyonel', label: 'Operasyonel' },
  { value: 'sporcu_belgesi', label: 'Sporcu Belgesi' },
  { value: 'ekipman_belgesi', label: 'Ekipman Belgesi' },
  { value: 'diger', label: 'Diğer' },
]

const STATUS_LABEL: Record<string, string> = {
  tamamlandi: 'Tamamlandı',
  taslak: 'Taslak',
  eksik: 'Eksik',
  placeholder: 'Placeholder',
  bilinmiyor: 'Bilinmiyor',
}

const STATUS_CLASS: Record<string, string> = {
  tamamlandi: 'badge-aktif',
  taslak: 'badge-bakimda',
  eksik: 'badge-hasarli',
  placeholder: 'badge-hizmetdisi',
  bilinmiyor: 'badge-hizmetdisi',
}

const STATUS_OPTIONS: { value: ContentStatus | ''; label: string }[] = [
  { value: '', label: 'Tüm Durumlar' },
  { value: 'tamamlandi', label: 'Tamamlandı' },
  { value: 'taslak', label: 'Taslak' },
  { value: 'eksik', label: 'Eksik' },
  { value: 'placeholder', label: 'Placeholder' },
  { value: 'bilinmiyor', label: 'Bilinmiyor' },
]

interface CreateModalProps {
  isOpen: boolean
  onClose: () => void
  onSaved: (doc: Document) => void
}

function CreateDocumentModal({ isOpen, onClose, onSaved }: CreateModalProps) {
  const [code, setCode] = useState('')
  const [title, setTitle] = useState('')
  const [docType, setDocType] = useState<DocumentType>('diger')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!code.trim() || !title.trim()) return
    setSaving(true)
    setError(null)
    try {
      const resp = await documentsApi.create({ code: code.trim(), title: title.trim(), document_type: docType })
      onSaved(resp.data)
      setCode('')
      setTitle('')
      setDocType('diger')
      onClose()
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      setError(msg ?? 'Belge oluşturulamadı.')
    } finally {
      setSaving(false)
    }
  }

  if (!isOpen) return null

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()} style={{ maxWidth: 480 }}>
        <div className="modal-header">
          <h2 className="modal-title">Yeni Belge</h2>
          <button className="modal-close" onClick={onClose}>×</button>
        </div>
        <form onSubmit={handleSubmit}>
          <div className="modal-body">
            {error && (
              <div className="alert alert-error" style={{ marginBottom: 12 }}>
                <span>{error}</span>
              </div>
            )}
            <div className="form-group">
              <label className="form-label">Belge Kodu *</label>
              <input
                className="form-input"
                value={code}
                onChange={(e) => setCode(e.target.value)}
                placeholder="ör. PRO-001"
                required
              />
            </div>
            <div className="form-group">
              <label className="form-label">Başlık *</label>
              <input
                className="form-input"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="Belge başlığı"
                required
              />
            </div>
            <div className="form-group">
              <label className="form-label">Belge Türü</label>
              <select
                className="form-select"
                value={docType}
                onChange={(e) => setDocType(e.target.value as DocumentType)}
              >
                {TYPE_OPTIONS.filter((o) => o.value !== '').map((o) => (
                  <option key={o.value} value={o.value}>{o.label}</option>
                ))}
              </select>
            </div>
          </div>
          <div className="modal-footer">
            <button type="button" className="btn btn-secondary" onClick={onClose}>
              İptal
            </button>
            <button type="submit" className="btn btn-primary" disabled={saving}>
              {saving ? 'Kaydediliyor...' : 'Oluştur'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

export default function DocumentsPage() {
  const navigate = useNavigate()

  const [docs, setDocs] = useState<Document[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const [search, setSearch] = useState('')
  const [typeFilter, setTypeFilter] = useState<DocumentType | ''>('')
  const [statusFilter, setStatusFilter] = useState<ContentStatus | ''>('')

  const [modalOpen, setModalOpen] = useState(false)

  const fetchDocs = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const params: Record<string, string> = {}
      if (search) params.q = search
      if (typeFilter) params.document_type = typeFilter
      if (statusFilter) params.content_status = statusFilter
      const resp = await documentsApi.list(params)
      setDocs(resp.data)
    } catch {
      setError('Belgeler yüklenemedi.')
    } finally {
      setLoading(false)
    }
  }, [search, typeFilter, statusFilter])

  useEffect(() => {
    fetchDocs()
  }, [fetchDocs])

  const handleSaved = (doc: Document) => {
    setDocs((prev) => {
      const exists = prev.some((d) => d.id === doc.id)
      if (exists) return prev.map((d) => (d.id === doc.id ? doc : d))
      return [doc, ...prev]
    })
  }

  const handleDelete = async (doc: Document, e: React.MouseEvent) => {
    e.stopPropagation()
    if (!window.confirm(`"${doc.title}" belgesini silmek istiyor musunuz?`)) return
    try {
      await documentsApi.delete(doc.id)
      setDocs((prev) => prev.filter((d) => d.id !== doc.id))
    } catch {
      alert('Silme işlemi başarısız.')
    }
  }

  return (
    <AppShell title="Belgeler">
      <div className="page-header">
        <h1 className="page-title">Belgeler</h1>
        <button className="btn btn-primary" onClick={() => setModalOpen(true)}>
          + Yeni Belge
        </button>
      </div>

      {/* Filtreler */}
      <div className="filter-bar">
        <input
          className="form-input"
          style={{ maxWidth: 260 }}
          placeholder="Kod veya başlık ara..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <select
          className="form-select"
          style={{ width: 'auto', minWidth: 160 }}
          value={typeFilter}
          onChange={(e) => setTypeFilter(e.target.value as DocumentType | '')}
        >
          {TYPE_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>{o.label}</option>
          ))}
        </select>
        <select
          className="form-select"
          style={{ width: 'auto', minWidth: 160 }}
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value as ContentStatus | '')}
        >
          {STATUS_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>{o.label}</option>
          ))}
        </select>
      </div>

      {error && (
        <div className="alert alert-error">
          <span>{error}</span>
        </div>
      )}

      <div className="table-container">
        {loading ? (
          <div className="loading-center"><span className="loading-spinner lg" /></div>
        ) : docs.length === 0 ? (
          <div className="empty-state">
            <div className="empty-state-icon">📄</div>
            <div className="empty-state-title">Belge Bulunamadı</div>
            <div className="empty-state-desc">
              Henüz kayıtlı belge yok. Yeni belge ekleyin.
            </div>
          </div>
        ) : (
          <table className="data-table">
            <thead>
              <tr>
                <th>Kod</th>
                <th>Başlık</th>
                <th>Tür</th>
                <th>İçerik Durumu</th>
                <th>İşlemler</th>
              </tr>
            </thead>
            <tbody>
              {docs.map((doc) => (
                <tr
                  key={doc.id}
                  onClick={() => navigate(`/belgeler/${doc.id}`)}
                  style={{ cursor: 'pointer' }}
                >
                  <td>
                    <strong>{doc.code}</strong>
                  </td>
                  <td>{doc.title}</td>
                  <td>
                    <span className="badge badge-secondary">
                      {TYPE_LABEL[doc.document_type] ?? doc.document_type}
                    </span>
                  </td>
                  <td>
                    <span className={`badge ${STATUS_CLASS[doc.content_status] ?? ''}`}>
                      {STATUS_LABEL[doc.content_status] ?? doc.content_status}
                    </span>
                  </td>
                  <td>
                    <div style={{ display: 'flex', gap: 6 }} onClick={(e) => e.stopPropagation()}>
                      <button
                        className="btn btn-sm btn-danger"
                        onClick={(e) => handleDelete(doc, e)}
                      >
                        Sil
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <CreateDocumentModal
        isOpen={modalOpen}
        onClose={() => setModalOpen(false)}
        onSaved={handleSaved}
      />
    </AppShell>
  )
}
