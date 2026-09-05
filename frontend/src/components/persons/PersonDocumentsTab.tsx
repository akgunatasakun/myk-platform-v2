/**
 * Kişisel evrak sekmesi — Veli, Antrenör/Başantrenör ve Yönetici görünümleri.
 *
 * Props:
 *   subjectPersonId — evrakları gösterilecek kişinin person.id'si
 *   role            — mevcut kullanıcının yetki kategorisi
 */
import { useEffect, useState } from 'react'
import { personDocumentsApi, streamPersonDocument } from '@/api/person_documents'
import type {
  HealthDocumentSummaryOut,
  PersonDocumentOut,
  PersonDocumentType,
  ReviewStatus,
} from '@/types/person_document'

// ────────────────────────────────────────────────────────────────────────────
// Sabitler
// ────────────────────────────────────────────────────────────────────────────

export type PersonDocumentsRole = 'veli' | 'antrenor' | 'basantrenor' | 'admin'

const COACH_ROLES: ReadonlySet<PersonDocumentsRole> = new Set(['antrenor', 'basantrenor'])

const DOC_TYPE_LABELS: Record<PersonDocumentType, string> = {
  profile_photo: 'Profil Fotoğrafı',
  identity_copy: 'Kimlik Fotokopisi',
  health_report: 'Sağlık Raporu',
  parental_permission: 'Veli İzin Belgesi',
  undertaking: 'Taahhütname',
  waiver: 'Feragatname',
  other: 'Diğer',
}

/** Veli tarafından yüklenebilen evrak tipleri (health_report hariç) */
const UPLOADABLE_TYPES: PersonDocumentType[] = [
  'profile_photo',
  'identity_copy',
  'parental_permission',
  'undertaking',
  'waiver',
  'other',
]

const STATUS_LABELS: Record<ReviewStatus, string> = {
  pending: 'İncelemede',
  approved: 'Onaylı',
  rejected: 'Red',
  expired: 'Süresi Doldu',
  superseded: 'Güncellendi',
}

const STATUS_COLORS: Record<ReviewStatus, string> = {
  pending: '#b45309',
  approved: '#065f46',
  rejected: '#991b1b',
  expired: '#c2410c',
  superseded: '#4b5563',
}

const STATUS_BG: Record<ReviewStatus, string> = {
  pending: '#fef3c7',
  approved: '#d1fae5',
  rejected: '#fee2e2',
  expired: '#ffedd5',
  superseded: '#f3f4f6',
}

const FILE_MAX_BYTES = 20 * 1024 * 1024

// ────────────────────────────────────────────────────────────────────────────
// Hata mesajları
// ────────────────────────────────────────────────────────────────────────────

function httpErrorMessage(status: number | undefined): string {
  if (status === 403) return 'Bu belgeye erişim yetkiniz yok.'
  if (status === 423) return 'Belge işlemleri şu an kilitli. Lütfen daha sonra tekrar deneyin.'
  if (status === 503) return 'Hizmet geçici olarak kullanılamıyor. Lütfen daha sonra tekrar deneyin.'
  return 'Bir hata oluştu. Lütfen sayfayı yenileyip tekrar deneyin.'
}

function uploadErrorMessage(status: number | undefined): string {
  if (status === 413) return 'Dosya 20MB sınırını aşıyor.'
  if (status === 429) return 'Günlük yükleme limitine ulaşıldı.'
  if (status === 507) return 'Kişi belge kapasitesi dolu (100MB).'
  return 'Yükleme başarısız. Lütfen tekrar deneyin.'
}

function extractStatus(err: unknown): number | undefined {
  return (err as { response?: { status?: number } })?.response?.status
}

// ────────────────────────────────────────────────────────────────────────────
// Alt bileşenler
// ────────────────────────────────────────────────────────────────────────────

function StatusBadge({ status }: { status: ReviewStatus | 'missing' }) {
  if (status === 'missing') {
    return (
      <span style={{
        padding: '2px 10px', borderRadius: 12,
        background: '#f3f4f6', color: '#4b5563',
        fontWeight: 600, fontSize: 12,
      }}>
        Eksik
      </span>
    )
  }
  return (
    <span style={{
      padding: '2px 10px', borderRadius: 12,
      background: STATUS_BG[status], color: STATUS_COLORS[status],
      fontWeight: 600, fontSize: 12,
    }}>
      {STATUS_LABELS[status]}
    </span>
  )
}

// ────────────────────────────────────────────────────────────────────────────
// Ana bileşen
// ────────────────────────────────────────────────────────────────────────────

interface Props {
  subjectPersonId: string
  role: PersonDocumentsRole
}

export default function PersonDocumentsTab({ subjectPersonId, role }: Props) {
  const [docs, setDocs] = useState<PersonDocumentOut[]>([])
  const [healthSummary, setHealthSummary] = useState<HealthDocumentSummaryOut | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)
  const [actionLoading, setActionLoading] = useState<string | null>(null) // documentId veya 'upload'

  // Yükleme formu (veli)
  const [uploadDocType, setUploadDocType] = useState<PersonDocumentType>('identity_copy')
  const [uploadFile, setUploadFile] = useState<File | null>(null)
  const [uploadValidUntil, setUploadValidUntil] = useState('')
  const [uploadState, setUploadState] = useState<'idle' | 'uploading' | 'success' | 'error'>('idle')
  const [uploadErrMsg, setUploadErrMsg] = useState('')

  // Silme isteği (veli)
  const [deleteReqState, setDeleteReqState] = useState<{ docId: string; reason: string } | null>(null)
  const [deleteReqLoading, setDeleteReqLoading] = useState(false)
  const [deleteReqMsg, setDeleteReqMsg] = useState<string | null>(null)

  const isCoach = COACH_ROLES.has(role)

  useEffect(() => {
    setLoading(true)
    setError(null)

    const fetchDocs = personDocumentsApi.list(subjectPersonId).then((r) => {
      setDocs(r.data)
    })

    const fetches: Promise<unknown>[] = [fetchDocs]

    if (isCoach) {
      fetches.push(
        personDocumentsApi.getHealthSummary(subjectPersonId).then((r) => {
          setHealthSummary(r.data)
        }),
      )
    }

    Promise.all(fetches)
      .catch((err: unknown) => {
        setError(httpErrorMessage(extractStatus(err)))
      })
      .finally(() => setLoading(false))
  }, [subjectPersonId, isCoach])

  // ── Aksiyon: Onayla ──────────────────────────────────────────────────────

  async function handleApprove(documentId: string) {
    setActionLoading(documentId)
    setActionError(null)
    try {
      const { data } = await personDocumentsApi.approve(documentId)
      setDocs((prev) => prev.map((d) => (d.id === documentId ? data : d)))
    } catch (err: unknown) {
      setActionError(httpErrorMessage(extractStatus(err)))
    } finally {
      setActionLoading(null)
    }
  }

  // ── Aksiyon: Reddet ─────────────────────────────────────────────────────

  async function handleReject(documentId: string) {
    const reason = window.prompt('Red gerekçesini girin:')
    if (reason === null) return
    if (!reason.trim()) {
      setActionError('Red gerekçesi boş bırakılamaz.')
      return
    }
    setActionLoading(documentId)
    setActionError(null)
    try {
      const { data } = await personDocumentsApi.reject(documentId, reason.trim())
      setDocs((prev) => prev.map((d) => (d.id === documentId ? data : d)))
    } catch (err: unknown) {
      setActionError(httpErrorMessage(extractStatus(err)))
    } finally {
      setActionLoading(null)
    }
  }

  // ── Aksiyon: Admin Sil ───────────────────────────────────────────────────

  async function handleAdminDelete(documentId: string) {
    if (!window.confirm('Bu evrakı kalıcı olarak silmek istediğinizden emin misiniz?')) return
    setActionLoading(documentId)
    setActionError(null)
    try {
      await personDocumentsApi.deleteDocument(documentId)
      setDocs((prev) => prev.filter((d) => d.id !== documentId))
    } catch (err: unknown) {
      setActionError(httpErrorMessage(extractStatus(err)))
    } finally {
      setActionLoading(null)
    }
  }

  // ── Aksiyon: Silme İsteği Onayla (admin) ─────────────────────────────────

  async function handleApproveDeleteRequest(documentId: string) {
    setActionLoading(documentId)
    setActionError(null)
    try {
      await personDocumentsApi.approveDeleteRequest(documentId)
      setDocs((prev) => prev.filter((d) => d.id !== documentId))
    } catch (err: unknown) {
      setActionError(httpErrorMessage(extractStatus(err)))
    } finally {
      setActionLoading(null)
    }
  }

  // ── Aksiyon: Silme İsteği Reddet (admin) ─────────────────────────────────

  async function handleRejectDeleteRequest(documentId: string) {
    const reason = window.prompt('Red gerekçesini girin:')
    if (reason === null) return
    setActionLoading(documentId)
    setActionError(null)
    try {
      const { data } = await personDocumentsApi.rejectDeleteRequest(documentId, reason.trim())
      // Silme isteği reddedildi — doc üzerindeki delete_request.status güncelle
      setDocs((prev) =>
        prev.map((d) =>
          d.id === documentId
            ? { ...d, delete_request: { ...d.delete_request!, status: data.status } }
            : d,
        ),
      )
    } catch (err: unknown) {
      setActionError(httpErrorMessage(extractStatus(err)))
    } finally {
      setActionLoading(null)
    }
  }

  // ── Aksiyon: Veli — Silme İste ───────────────────────────────────────────

  async function handleRequestDelete() {
    if (!deleteReqState) return
    setDeleteReqLoading(true)
    setDeleteReqMsg(null)
    try {
      await personDocumentsApi.requestDelete(deleteReqState.docId, deleteReqState.reason)
      setDeleteReqMsg('Silme isteği gönderildi.')
      // delete_request alanını "pending" olarak yansıt
      setDocs((prev) =>
        prev.map((d) =>
          d.id === deleteReqState.docId
            ? {
                ...d,
                delete_request: {
                  reason: deleteReqState.reason,
                  requested_by_user_id: '',
                  status: 'pending',
                  created_at: new Date().toISOString(),
                },
              }
            : d,
        ),
      )
      setDeleteReqState(null)
    } catch (err: unknown) {
      setDeleteReqMsg('İstek gönderilemedi. Lütfen tekrar deneyin.')
    } finally {
      setDeleteReqLoading(false)
    }
  }

  // ── Aksiyon: Yükle (veli) ────────────────────────────────────────────────

  async function handleUpload(e: React.FormEvent) {
    e.preventDefault()
    if (!uploadFile) {
      setUploadErrMsg('Lütfen bir dosya seçin.')
      return
    }
    if (uploadFile.size > FILE_MAX_BYTES) {
      setUploadErrMsg('Dosya 20MB sınırını aşıyor.')
      return
    }
    setUploadState('uploading')
    setUploadErrMsg('')
    try {
      const { data } = await personDocumentsApi.upload({
        subjectPersonId,
        documentType: uploadDocType,
        file: uploadFile,
        validUntil: uploadValidUntil || null,
      })
      setDocs((prev) => [data, ...prev.filter((d) => d.id !== data.id)])
      setUploadFile(null)
      setUploadValidUntil('')
      setUploadState('success')
      setTimeout(() => setUploadState('idle'), 3000)
    } catch (err: unknown) {
      setUploadErrMsg(uploadErrorMessage(extractStatus(err)))
      setUploadState('error')
    }
  }

  // ────────────────────────────────────────────────────────────────────────
  // Render guards
  // ────────────────────────────────────────────────────────────────────────

  if (loading) {
    return (
      <div className="loading-center">
        <span className="loading-spinner lg" />
      </div>
    )
  }

  if (error) {
    return (
      <div className="alert alert-error">
        <span>⚠️</span>
        <span>{error}</span>
      </div>
    )
  }

  // ────────────────────────────────────────────────────────────────────────
  // Antrenör / Başantrenör görünümü
  // ────────────────────────────────────────────────────────────────────────

  if (isCoach) {
    const pendingQueue = docs.filter(
      (d) => !d.is_sensitive && d.review_status === 'pending',
    )

    return (
      <div>
        {actionError && (
          <div className="alert alert-error" style={{ marginBottom: 12 }}>
            <span>⚠️</span><span>{actionError}</span>
          </div>
        )}

        <div className="card" style={{ marginBottom: 16 }}>
          <div className="card-header">
            Bekleyen Evraklar
            {pendingQueue.length > 0 && (
              <span className="badge badge-aktif" style={{ marginLeft: 8 }}>
                {pendingQueue.length}
              </span>
            )}
          </div>
          <div className="card-body">
            {pendingQueue.length === 0 ? (
              <div className="empty-state" style={{ padding: '16px 0' }}>
                <div className="empty-state-icon">✓</div>
                <div className="empty-state-title">Bekleyen evrak yok.</div>
              </div>
            ) : (
              <div className="table-container">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Tür</th>
                      <th>Dosya Adı</th>
                      <th>Yüklendi</th>
                      <th>İşlemler</th>
                    </tr>
                  </thead>
                  <tbody>
                    {pendingQueue.map((doc) => {
                      const busy = actionLoading === doc.id
                      return (
                        <tr key={doc.id}>
                          <td>{DOC_TYPE_LABELS[doc.document_type] ?? doc.document_type}</td>
                          <td style={{ fontSize: 13 }}>{doc.original_filename}</td>
                          <td style={{ fontSize: 13 }}>
                            {new Date(doc.uploaded_at).toLocaleDateString('tr-TR')}
                          </td>
                          <td>
                            <div style={{ display: 'flex', gap: 8 }}>
                              <button
                                className="btn btn-ghost btn-sm"
                                onClick={() => streamPersonDocument(doc.id)}
                                disabled={busy}
                              >
                                Görüntüle
                              </button>
                              <button
                                className="btn btn-primary btn-sm"
                                onClick={() => handleApprove(doc.id)}
                                disabled={busy}
                              >
                                {busy ? '…' : 'Onayla'}
                              </button>
                              <button
                                className="btn btn-danger btn-sm"
                                onClick={() => handleReject(doc.id)}
                                disabled={busy}
                              >
                                Reddet
                              </button>
                            </div>
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>

        <div className="card">
          <div className="card-header">Sağlık Raporu</div>
          <div className="card-body">
            <div style={{ fontSize: 14, color: 'var(--color-text-secondary)' }}>
              {healthSummary === null ? (
                'Yükleniyor…'
              ) : healthSummary.exists ? (
                <>
                  <span style={{ color: 'var(--color-success)', fontWeight: 600 }}>
                    Mevcut
                  </span>
                  {healthSummary.valid_until && (
                    <span style={{ marginLeft: 8 }}>
                      — Geçerlilik: {new Date(healthSummary.valid_until + 'T00:00:00').toLocaleDateString('tr-TR')}
                    </span>
                  )}
                </>
              ) : (
                <span style={{ color: 'var(--color-text-muted)' }}>Mevcut değil</span>
              )}
            </div>
          </div>
        </div>
      </div>
    )
  }

  // ────────────────────────────────────────────────────────────────────────
  // Veli görünümü
  // ────────────────────────────────────────────────────────────────────────

  if (role === 'veli') {
    return (
      <div>
        {actionError && (
          <div className="alert alert-error" style={{ marginBottom: 12 }}>
            <span>⚠️</span><span>{actionError}</span>
          </div>
        )}

        {deleteReqMsg && (
          <div className="alert alert-success" style={{ marginBottom: 12 }}>
            <span>{deleteReqMsg}</span>
          </div>
        )}

        {/* Yükleme formu */}
        <div className="card" style={{ marginBottom: 16 }}>
          <div className="card-header">Evrak Yükle</div>
          <div className="card-body">
            <form onSubmit={(e) => { void handleUpload(e) }} style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 4, minWidth: 180 }}>
                  <label style={{ fontSize: 13, fontWeight: 500 }}>Evrak Türü</label>
                  <select
                    className="form-select"
                    value={uploadDocType}
                    onChange={(e) => setUploadDocType(e.target.value as PersonDocumentType)}
                    disabled={uploadState === 'uploading'}
                  >
                    {UPLOADABLE_TYPES.map((t) => (
                      <option key={t} value={t}>{DOC_TYPE_LABELS[t]}</option>
                    ))}
                  </select>
                </div>

                <div style={{ display: 'flex', flexDirection: 'column', gap: 4, minWidth: 220 }}>
                  <label style={{ fontSize: 13, fontWeight: 500 }}>
                    Dosya <span style={{ color: 'var(--color-text-muted)', fontWeight: 400 }}>(PDF, JPG, PNG — maks. 20MB)</span>
                  </label>
                  <input
                    type="file"
                    accept=".pdf,.jpg,.jpeg,.png"
                    className="form-input"
                    disabled={uploadState === 'uploading'}
                    onChange={(e) => {
                      const f = e.target.files?.[0] ?? null
                      setUploadFile(f)
                      setUploadErrMsg('')
                      setUploadState('idle')
                    }}
                  />
                </div>

                <div style={{ display: 'flex', flexDirection: 'column', gap: 4, minWidth: 180 }}>
                  <label style={{ fontSize: 13, fontWeight: 500 }}>
                    Geçerlilik Tarihi <span style={{ color: 'var(--color-text-muted)', fontWeight: 400 }}>(opsiyonel)</span>
                  </label>
                  <input
                    type="date"
                    className="form-input"
                    value={uploadValidUntil}
                    onChange={(e) => setUploadValidUntil(e.target.value)}
                    disabled={uploadState === 'uploading'}
                  />
                </div>
              </div>

              {uploadErrMsg && (
                <div className="alert alert-error" style={{ padding: '6px 12px', fontSize: 13 }}>
                  {uploadErrMsg}
                </div>
              )}

              {uploadState === 'success' && (
                <div className="alert alert-success" style={{ padding: '6px 12px', fontSize: 13 }}>
                  Evrak başarıyla yüklendi.
                </div>
              )}

              <div>
                <button
                  type="submit"
                  className="btn btn-primary btn-sm"
                  disabled={uploadState === 'uploading' || !uploadFile}
                >
                  {uploadState === 'uploading' ? 'Yükleniyor…' : 'Yükle'}
                </button>
              </div>
            </form>
          </div>
        </div>

        {/* Mevcut evraklar tablosu */}
        <div className="card">
          <div className="card-header">
            Evraklar
            <span className="badge badge-aktif" style={{ marginLeft: 8 }}>{docs.length}</span>
          </div>
          <div className="card-body" style={{ padding: 0 }}>
            {docs.length === 0 ? (
              <div className="empty-state" style={{ padding: '24px 0' }}>
                <div className="empty-state-icon">📄</div>
                <div className="empty-state-title">Henüz evrak yok.</div>
              </div>
            ) : (
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Evrak Türü</th>
                    <th>Durum</th>
                    <th>Yüklendi</th>
                    <th>İşlemler</th>
                  </tr>
                </thead>
                <tbody>
                  {docs.map((doc) => (
                    <tr key={doc.id}>
                      <td style={{ fontWeight: 500 }}>{DOC_TYPE_LABELS[doc.document_type] ?? doc.document_type}</td>
                      <td>
                        <StatusBadge status={doc.review_status} />
                        {doc.delete_request?.status === 'pending' && (
                          <span style={{
                            marginLeft: 6, padding: '2px 8px', borderRadius: 10,
                            background: '#fef3c7', color: '#b45309',
                            fontSize: 11, fontWeight: 600,
                          }}>
                            Silme İsteği Bekliyor
                          </span>
                        )}
                      </td>
                      <td style={{ fontSize: 13 }}>
                        {new Date(doc.uploaded_at).toLocaleDateString('tr-TR')}
                      </td>
                      <td>
                        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                          <button
                            className="btn btn-ghost btn-sm"
                            onClick={() => streamPersonDocument(doc.id)}
                          >
                            Görüntüle
                          </button>
                          {doc.document_type !== 'health_report' &&
                            !doc.delete_request && (
                              <button
                                className="btn btn-ghost btn-sm"
                                style={{ color: '#991b1b' }}
                                onClick={() =>
                                  setDeleteReqState({ docId: doc.id, reason: '' })
                                }
                              >
                                Silme İste
                              </button>
                            )}
                        </div>
                        {/* Silme isteği formu — inline */}
                        {deleteReqState?.docId === doc.id && (
                          <div style={{ marginTop: 8, display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
                            <input
                              className="form-input"
                              style={{ minWidth: 180, fontSize: 13 }}
                              placeholder="Gerekçe (opsiyonel)"
                              value={deleteReqState.reason}
                              onChange={(e) =>
                                setDeleteReqState((s) => s ? { ...s, reason: e.target.value } : s)
                              }
                            />
                            <button
                              className="btn btn-danger btn-sm"
                              disabled={deleteReqLoading}
                              onClick={() => { void handleRequestDelete() }}
                            >
                              {deleteReqLoading ? '…' : 'Gönder'}
                            </button>
                            <button
                              className="btn btn-ghost btn-sm"
                              onClick={() => setDeleteReqState(null)}
                            >
                              İptal
                            </button>
                          </div>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>
      </div>
    )
  }

  // ────────────────────────────────────────────────────────────────────────
  // Admin görünümü — tüm evraklar listesi
  // ────────────────────────────────────────────────────────────────────────

  return (
    <div>
      {actionError && (
        <div className="alert alert-error" style={{ marginBottom: 12 }}>
          <span>⚠️</span><span>{actionError}</span>
        </div>
      )}

      {/* Yükleme formu — admin her zaman gösterilir */}
      <div className="card" style={{ marginBottom: 16 }}>
        <div className="card-header">Evrak Yükle</div>
        <div className="card-body">
          <form onSubmit={(e) => { void handleUpload(e) }} style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 4, minWidth: 180 }}>
                <label style={{ fontSize: 13, fontWeight: 500 }}>Evrak Türü</label>
                <select
                  className="form-select"
                  value={uploadDocType}
                  onChange={(e) => setUploadDocType(e.target.value as PersonDocumentType)}
                  disabled={uploadState === 'uploading'}
                >
                  {UPLOADABLE_TYPES.map((t) => (
                    <option key={t} value={t}>{DOC_TYPE_LABELS[t]}</option>
                  ))}
                </select>
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: 4, minWidth: 220 }}>
                <label style={{ fontSize: 13, fontWeight: 500 }}>
                  Dosya <span style={{ color: 'var(--color-text-muted)', fontWeight: 400 }}>(PDF, JPG, PNG — maks. 20MB)</span>
                </label>
                <input
                  type="file"
                  accept=".pdf,.jpg,.jpeg,.png"
                  className="form-input"
                  disabled={uploadState === 'uploading'}
                  onChange={(e) => {
                    const f = e.target.files?.[0] ?? null
                    setUploadFile(f)
                    setUploadErrMsg('')
                    setUploadState('idle')
                  }}
                />
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: 4, minWidth: 180 }}>
                <label style={{ fontSize: 13, fontWeight: 500 }}>
                  Geçerlilik Tarihi <span style={{ color: 'var(--color-text-muted)', fontWeight: 400 }}>(opsiyonel)</span>
                </label>
                <input
                  type="date"
                  className="form-input"
                  value={uploadValidUntil}
                  onChange={(e) => setUploadValidUntil(e.target.value)}
                  disabled={uploadState === 'uploading'}
                />
              </div>
            </div>

            {uploadErrMsg && (
              <div className="alert alert-error" style={{ padding: '6px 12px', fontSize: 13 }}>
                {uploadErrMsg}
              </div>
            )}

            {uploadState === 'success' && (
              <div className="alert alert-success" style={{ padding: '6px 12px', fontSize: 13 }}>
                Evrak başarıyla yüklendi.
              </div>
            )}

            <div>
              <button
                type="submit"
                className="btn btn-primary btn-sm"
                disabled={uploadState === 'uploading' || !uploadFile}
              >
                {uploadState === 'uploading' ? 'Yükleniyor…' : 'Yükle'}
              </button>
            </div>
          </form>
        </div>
      </div>

      <div className="card">
        <div className="card-header">
          Evraklar
          <span className="badge badge-aktif" style={{ marginLeft: 8 }}>
            {docs.length}
          </span>
        </div>
        <div className="card-body" style={{ padding: 0 }}>
          {docs.length === 0 ? (
            <div className="empty-state" style={{ padding: '24px 0' }}>
              <div className="empty-state-icon">📄</div>
              <div className="empty-state-title">Henüz evrak yok.</div>
            </div>
          ) : (
            <table className="data-table">
              <thead>
                <tr>
                  <th>Tür</th>
                  <th>Dosya Adı</th>
                  <th>Durum</th>
                  <th>Hassas</th>
                  <th>Yüklendi</th>
                  <th>İşlemler</th>
                </tr>
              </thead>
              <tbody>
                {docs.map((doc) => {
                  const busy = actionLoading === doc.id
                  const hasPendingDeleteReq = doc.delete_request?.status === 'pending'
                  return (
                    <tr key={doc.id}>
                      <td>{DOC_TYPE_LABELS[doc.document_type] ?? doc.document_type}</td>
                      <td style={{ fontSize: 13 }}>{doc.original_filename}</td>
                      <td>
                        <StatusBadge status={doc.review_status} />
                        {hasPendingDeleteReq && (
                          <span style={{
                            marginLeft: 6, padding: '2px 8px', borderRadius: 10,
                            background: '#fef3c7', color: '#b45309',
                            fontSize: 11, fontWeight: 600,
                          }}>
                            Silme İsteği
                          </span>
                        )}
                      </td>
                      <td>{doc.is_sensitive ? '🔒 Evet' : '—'}</td>
                      <td style={{ fontSize: 13 }}>
                        {new Date(doc.uploaded_at).toLocaleDateString('tr-TR')}
                      </td>
                      <td>
                        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                          <button
                            className="btn btn-ghost btn-sm"
                            onClick={() => streamPersonDocument(doc.id)}
                          >
                            Görüntüle
                          </button>
                          {doc.review_status === 'pending' && (
                            <>
                              <button
                                className="btn btn-primary btn-sm"
                                onClick={() => { void handleApprove(doc.id) }}
                                disabled={busy}
                              >
                                {busy ? '…' : 'Onayla'}
                              </button>
                              <button
                                className="btn btn-danger btn-sm"
                                onClick={() => { void handleReject(doc.id) }}
                                disabled={busy}
                              >
                                Reddet
                              </button>
                            </>
                          )}
                          {hasPendingDeleteReq && (
                            <>
                              <button
                                className="btn btn-danger btn-sm"
                                onClick={() => { void handleApproveDeleteRequest(doc.id) }}
                                disabled={busy}
                              >
                                {busy ? '…' : 'Silmeyi Onayla'}
                              </button>
                              <button
                                className="btn btn-ghost btn-sm"
                                onClick={() => { void handleRejectDeleteRequest(doc.id) }}
                                disabled={busy}
                              >
                                Silmeyi Reddet
                              </button>
                            </>
                          )}
                          <button
                            className="btn btn-ghost btn-sm"
                            style={{ color: '#991b1b' }}
                            onClick={() => { void handleAdminDelete(doc.id) }}
                            disabled={busy}
                          >
                            Sil
                          </button>
                        </div>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  )
}
