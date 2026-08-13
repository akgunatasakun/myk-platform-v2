import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import AppShell from '@/components/layout/AppShell'
import { documentsApi } from '@/api/documents'
import type {
  Document,
  DocumentRevision,
  DocumentRevisionFile,
  RevisionStatus,
  RevisionCreate,
} from '@/types/document'

const REV_STATUS_LABEL: Record<string, string> = {
  taslak: 'Taslak',
  incelemede: 'İncelemede',
  onaylandi: 'Onaylandı',
  yayinda: 'Yayında',
  arsivlendi: 'Arşivlendi',
  bloke: 'Bloke',
}

const REV_STATUS_CLASS: Record<string, string> = {
  taslak: 'badge-bakimda',
  incelemede: 'badge-bakimda',
  onaylandi: 'badge-aktif',
  yayinda: 'badge-aktif',
  arsivlendi: 'badge-hizmetdisi',
  bloke: 'badge-hasarli',
}

function fmtBytes(n: number): string {
  if (n < 1024) return `${n} B`
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`
  return `${(n / (1024 * 1024)).toFixed(1)} MB`
}

interface NewRevisionModalProps {
  docId: string
  isOpen: boolean
  onClose: () => void
  onSaved: (rev: DocumentRevision) => void
}

function NewRevisionModal({ docId, isOpen, onClose, onSaved }: NewRevisionModalProps) {
  const [revCode, setRevCode] = useState('')
  const [revStatus, setRevStatus] = useState<RevisionStatus>('taslak')
  const [description, setDescription] = useState('')
  const [isCurrent, setIsCurrent] = useState(false)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!revCode.trim()) return
    setSaving(true)
    setError(null)
    try {
      const data: RevisionCreate = {
        revision_code: revCode.trim(),
        status: revStatus,
        description: description.trim() || undefined,
        is_current: isCurrent,
      }
      const resp = await documentsApi.createRevision(docId, data)
      onSaved({ ...resp.data, files: [] })
      setRevCode('')
      setDescription('')
      setIsCurrent(false)
      onClose()
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      setError(msg ?? 'Revizyon oluşturulamadı.')
    } finally {
      setSaving(false)
    }
  }

  if (!isOpen) return null

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()} style={{ maxWidth: 480 }}>
        <div className="modal-header">
          <h2 className="modal-title">Yeni Revizyon</h2>
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
              <label className="form-label">Revizyon Kodu *</label>
              <input
                className="form-input"
                value={revCode}
                onChange={(e) => setRevCode(e.target.value)}
                placeholder="ör. R00"
                required
              />
            </div>
            <div className="form-group">
              <label className="form-label">Durum</label>
              <select
                className="form-select"
                value={revStatus}
                onChange={(e) => setRevStatus(e.target.value as RevisionStatus)}
              >
                {Object.entries(REV_STATUS_LABEL).map(([k, v]) => (
                  <option key={k} value={k}>{v}</option>
                ))}
              </select>
            </div>
            <div className="form-group">
              <label className="form-label">Açıklama</label>
              <textarea
                className="form-input"
                rows={3}
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="İsteğe bağlı"
              />
            </div>
            <div className="form-group">
              <label style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer' }}>
                <input
                  type="checkbox"
                  checked={isCurrent}
                  onChange={(e) => setIsCurrent(e.target.checked)}
                />
                Güncel revizyon olarak işaretle
              </label>
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

function FileActions({ file, docId, revId }: {
  file: DocumentRevisionFile
  docId: string
  revId: string
}) {
  const [loadingAction, setLoadingAction] = useState<'preview' | 'pdf' | 'word' | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)

  const isPdf = file.mime_type === 'application/pdf'
  const isDocx = file.mime_type === 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    || file.original_filename.toLowerCase().endsWith('.docx')

  const run = async (action: 'preview' | 'pdf' | 'word') => {
    setLoadingAction(action)
    setActionError(null)
    try {
      if (action === 'preview') {
        await documentsApi.previewPdf(docId, revId, file.id)
      } else {
        await documentsApi.downloadFile(docId, revId, file.id)
      }
    } catch {
      setActionError('İşlem başarısız oldu.')
    } finally {
      setLoadingAction(null)
    }
  }

  return (
    <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap', alignItems: 'center' }}>
      {isPdf && (
        <button
          className="btn btn-sm btn-primary"
          disabled={loadingAction !== null}
          onClick={() => run('preview')}
          title="Tarayıcıda görüntüle"
        >
          {loadingAction === 'preview' ? '…' : '👁 Görüntüle'}
        </button>
      )}
      {isPdf && (
        <button
          className="btn btn-sm btn-secondary"
          disabled={loadingAction !== null}
          onClick={() => run('pdf')}
          title="PDF olarak indir"
        >
          {loadingAction === 'pdf' ? '…' : '⬇ PDF İndir'}
        </button>
      )}
      {isDocx && (
        <button
          className="btn btn-sm btn-secondary"
          disabled={loadingAction !== null}
          onClick={() => run('word')}
          title="Word belgesi olarak indir"
        >
          {loadingAction === 'word' ? '…' : '⬇ Word İndir'}
        </button>
      )}
      {!isPdf && !isDocx && (
        <button
          className="btn btn-sm btn-secondary"
          disabled={loadingAction !== null}
          onClick={() => run('pdf')}
        >
          {loadingAction !== null ? '…' : '⬇ İndir'}
        </button>
      )}
      {actionError && (
        <span style={{ color: 'var(--color-danger)', fontSize: 12 }}>{actionError}</span>
      )}
    </div>
  )
}

function FileList({ files, docId, revId }: {
  files: DocumentRevisionFile[]
  docId: string
  revId: string
}) {
  if (files.length === 0) {
    return <div style={{ color: 'var(--color-text-muted)', fontSize: 13 }}>Bu revizyona henüz dosya yüklenmemiş.</div>
  }

  return (
    <table className="data-table" style={{ marginTop: 8 }}>
      <thead>
        <tr>
          <th>Dosya Adı</th>
          <th>Rol</th>
          <th>Boyut</th>
          <th>İşlemler</th>
        </tr>
      </thead>
      <tbody>
        {files.map((f) => (
          <tr key={f.id}>
            <td>
              {f.mime_type === 'application/pdf' ? (
                <button
                  className="btn-link"
                  style={{ background: 'none', border: 'none', padding: 0, cursor: 'pointer', color: 'var(--color-primary)', textDecoration: 'underline', fontSize: 'inherit' }}
                  onClick={() => documentsApi.previewPdf(docId, revId, f.id)}
                  title="Tarayıcıda aç"
                >
                  {f.original_filename}
                </button>
              ) : (
                f.original_filename
              )}
            </td>
            <td>{f.file_role}</td>
            <td style={{ fontSize: 12 }}>{fmtBytes(f.file_size)}</td>
            <td>
              <FileActions file={f} docId={docId} revId={revId} />
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

function UploadFileSection({ docId, revId, onUploaded }: {
  docId: string
  revId: string
  onUploaded: (file: DocumentRevisionFile) => void
}) {
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    setUploading(true)
    setError(null)
    try {
      const resp = await documentsApi.uploadFile(docId, revId, file)
      onUploaded(resp.data)
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      setError(msg ?? 'Dosya yüklenemedi.')
    } finally {
      setUploading(false)
      e.target.value = ''
    }
  }

  return (
    <div style={{ marginTop: 12 }}>
      {error && (
        <div className="alert alert-error" style={{ marginBottom: 8 }}>
          <span>{error}</span>
        </div>
      )}
      <label className="btn btn-sm btn-secondary" style={{ cursor: 'pointer' }}>
        {uploading ? 'Yükleniyor...' : '+ Dosya Yükle'}
        <input
          type="file"
          style={{ display: 'none' }}
          onChange={handleFileChange}
          disabled={uploading}
        />
      </label>
    </div>
  )
}

export default function DocumentDetailPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()

  const [doc, setDoc] = useState<Document | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [selectedRevision, setSelectedRevision] = useState<DocumentRevision | null>(null)
  const [newRevModalOpen, setNewRevModalOpen] = useState(false)

  useEffect(() => {
    if (!id) return
    setLoading(true)
    documentsApi.get(id)
      .then((resp) => {
        setDoc(resp.data)
        const revs = resp.data.revisions ?? []
        if (revs.length > 0) {
          const current = revs.find((r) => r.is_current) ?? revs[revs.length - 1]
          setSelectedRevision(current)
        }
      })
      .catch(() => setError('Belge yüklenemedi.'))
      .finally(() => setLoading(false))
  }, [id])

  const handleRevisionSaved = (rev: DocumentRevision) => {
    setDoc((prev) => {
      if (!prev) return prev
      const existingRevs = prev.revisions ?? []
      const newRevs = rev.is_current
        ? [...existingRevs.map((r) => ({ ...r, is_current: false })), rev]
        : [...existingRevs, rev]
      return { ...prev, revisions: newRevs, current_revision_id: rev.is_current ? rev.id : prev.current_revision_id }
    })
    setSelectedRevision(rev)
  }

  const handleFileUploaded = (file: DocumentRevisionFile) => {
    if (!selectedRevision) return
    setSelectedRevision((prev) => {
      if (!prev) return prev
      return { ...prev, files: [...prev.files, file] }
    })
    setDoc((prev) => {
      if (!prev) return prev
      return {
        ...prev,
        revisions: (prev.revisions ?? []).map((r) =>
          r.id === selectedRevision.id
            ? { ...r, files: [...r.files, file] }
            : r
        ),
      }
    })
  }

  if (loading) {
    return (
      <AppShell title="Belge">
        <div className="loading-center"><span className="loading-spinner lg" /></div>
      </AppShell>
    )
  }

  if (error || !doc) {
    return (
      <AppShell title="Belge">
        <div className="alert alert-error"><span>{error ?? 'Belge bulunamadı.'}</span></div>
        <button className="btn btn-secondary" onClick={() => navigate('/belgeler')}>
          ← Geri
        </button>
      </AppShell>
    )
  }

  const revisions = doc.revisions ?? []

  return (
    <AppShell title={doc.title}>
      <div style={{ marginBottom: 16 }}>
        <button className="btn btn-secondary btn-sm" onClick={() => navigate('/belgeler')}>
          ← Belgeler
        </button>
      </div>

      {/* Belge başlığı */}
      <div className="card" style={{ marginBottom: 20 }}>
        <div className="card-body">
          <h1 style={{ margin: '0 0 4px', fontSize: 22 }}>{doc.title}</h1>
          <div style={{ color: 'var(--color-text-muted)', fontSize: 14 }}>
            <strong>{doc.code}</strong> &nbsp;·&nbsp; {doc.document_type} &nbsp;·&nbsp; {doc.content_status}
          </div>
        </div>
      </div>

      {/* Revizyonlar */}
      <div style={{ display: 'flex', gap: 20, alignItems: 'flex-start' }}>
        {/* Sol: revizyon listesi */}
        <div style={{ width: 240, flexShrink: 0 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
            <strong style={{ fontSize: 14 }}>Revizyonlar ({revisions.length})</strong>
            <button
              className="btn btn-sm btn-primary"
              onClick={() => setNewRevModalOpen(true)}
            >
              + Yeni
            </button>
          </div>

          {revisions.length === 0 ? (
            <div style={{ color: 'var(--color-text-muted)', fontSize: 13 }}>
              Henüz revizyon yok.
            </div>
          ) : (
            <ul style={{ listStyle: 'none', margin: 0, padding: 0, display: 'flex', flexDirection: 'column', gap: 4 }}>
              {[...revisions].reverse().map((rev) => (
                <li key={rev.id}>
                  <button
                    style={{
                      width: '100%',
                      textAlign: 'left',
                      padding: '8px 12px',
                      border: '1px solid',
                      borderColor: selectedRevision?.id === rev.id
                        ? 'var(--color-primary)'
                        : 'var(--color-border)',
                      borderRadius: 6,
                      background: selectedRevision?.id === rev.id
                        ? 'var(--color-primary-light, rgba(0,112,240,0.08))'
                        : 'transparent',
                      cursor: 'pointer',
                      fontSize: 13,
                    }}
                    onClick={() => setSelectedRevision(rev)}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <strong>{rev.revision_code}</strong>
                      {rev.is_current && (
                        <span style={{ fontSize: 10, background: 'var(--color-primary)', color: '#fff', padding: '1px 6px', borderRadius: 4 }}>
                          güncel
                        </span>
                      )}
                    </div>
                    <span className={`badge ${REV_STATUS_CLASS[rev.status] ?? ''}`} style={{ fontSize: 11, marginTop: 4 }}>
                      {REV_STATUS_LABEL[rev.status] ?? rev.status}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>

        {/* Sağ: seçili revizyon dosyaları */}
        <div style={{ flex: 1 }}>
          {selectedRevision ? (
            <div>
              <h3 style={{ margin: '0 0 12px', fontSize: 16 }}>
                Revizyon {selectedRevision.revision_code} — Dosyalar
              </h3>
              <FileList
                files={selectedRevision.files}
                docId={doc.id}
                revId={selectedRevision.id}
              />
              <UploadFileSection
                docId={doc.id}
                revId={selectedRevision.id}
                onUploaded={handleFileUploaded}
              />
            </div>
          ) : (
            <div style={{ color: 'var(--color-text-muted)' }}>
              Sol taraftan bir revizyon seçin veya yeni revizyon ekleyin.
            </div>
          )}
        </div>
      </div>

      <NewRevisionModal
        docId={doc.id}
        isOpen={newRevModalOpen}
        onClose={() => setNewRevModalOpen(false)}
        onSaved={handleRevisionSaved}
      />
    </AppShell>
  )
}
