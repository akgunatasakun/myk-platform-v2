/**
 * Kişisel evrak sekmesi — Veli, Antrenör/Başantrenör ve Yönetici görünümleri.
 *
 * Props:
 *   subjectPersonId — evrakları gösterilecek kişinin person.id'si
 *   role            — mevcut kullanıcının yetki kategorisi
 */
import { useEffect, useRef, useState } from 'react'
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

/** Veli ve antrenör için gösterilecek (health_report hariç) evrak tipleri */
const VISIBLE_TYPES: PersonDocumentType[] = [
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
  pending: '#b45309',   // amber
  approved: '#065f46',  // green
  rejected: '#991b1b',  // red
  expired: '#c2410c',   // orange
  superseded: '#4b5563', // gray
}

const STATUS_BG: Record<ReviewStatus, string> = {
  pending: '#fef3c7',
  approved: '#d1fae5',
  rejected: '#fee2e2',
  expired: '#ffedd5',
  superseded: '#f3f4f6',
}

// ────────────────────────────────────────────────────────────────────────────
// Hata kodu → Türkçe mesaj
// ────────────────────────────────────────────────────────────────────────────

function httpErrorMessage(status: number | undefined): string {
  if (status === 403) return 'Bu belgeye erişim yetkiniz yok.'
  if (status === 423) return 'Belge işlemleri şu an kilitli. Lütfen daha sonra tekrar deneyin.'
  if (status === 503) return 'Hizmet geçici olarak kullanılamıyor. Lütfen daha sonra tekrar deneyin.'
  return 'Bir hata oluştu. Lütfen sayfayı yenileyip tekrar deneyin.'
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
  const [actionLoading, setActionLoading] = useState<string | null>(null) // documentId
  const fileInputRef = useRef<HTMLInputElement>(null)
  const [uploadingType, setUploadingType] = useState<PersonDocumentType | null>(null)

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
    if (reason === null) return // iptal
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

  // ── Aksiyon: Yükle ──────────────────────────────────────────────────────

  async function handleFileSelected(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (!file || !uploadingType) return
    e.target.value = ''
    setActionLoading('upload')
    setActionError(null)
    try {
      const { data } = await personDocumentsApi.upload({
        subjectPersonId,
        documentType: uploadingType,
        file,
      })
      setDocs((prev) => [...prev.filter((d) => d.document_type !== uploadingType), data])
    } catch (err: unknown) {
      setActionError(httpErrorMessage(extractStatus(err)))
    } finally {
      setActionLoading(null)
      setUploadingType(null)
    }
  }

  function triggerUpload(type: PersonDocumentType) {
    setUploadingType(type)
    setTimeout(() => fileInputRef.current?.click(), 0)
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

        {/* Bekleyen evraklar kuyruğu */}
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

        {/* Sağlık raporu — sadece metadata */}
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
    // En güncel doc per type
    const docByType: Partial<Record<PersonDocumentType, PersonDocumentOut>> = {}
    for (const doc of docs) {
      if (!docByType[doc.document_type]) docByType[doc.document_type] = doc
    }

    return (
      <div>
        {actionError && (
          <div className="alert alert-error" style={{ marginBottom: 12 }}>
            <span>⚠️</span><span>{actionError}</span>
          </div>
        )}

        {/* Gizli dosya input */}
        <input
          ref={fileInputRef}
          type="file"
          accept="application/pdf,image/jpeg,image/png"
          style={{ display: 'none' }}
          onChange={handleFileSelected}
        />

        <div className="card">
          <div className="card-header">Evraklar</div>
          <div className="card-body" style={{ padding: 0 }}>
            <table className="data-table">
              <thead>
                <tr>
                  <th>Evrak Türü</th>
                  <th>Durum</th>
                  <th>İşlem</th>
                </tr>
              </thead>
              <tbody>
                {VISIBLE_TYPES.map((type) => {
                  const doc = docByType[type]
                  const status: ReviewStatus | 'missing' = doc ? doc.review_status : 'missing'
                  const busy = actionLoading === 'upload' && uploadingType === type
                  return (
                    <tr key={type}>
                      <td style={{ fontWeight: 500 }}>{DOC_TYPE_LABELS[type]}</td>
                      <td><StatusBadge status={status} /></td>
                      <td>
                        {doc ? (
                          <button
                            className="btn btn-ghost btn-sm"
                            onClick={() => streamPersonDocument(doc.id)}
                          >
                            Görüntüle
                          </button>
                        ) : (
                          <button
                            className="btn btn-secondary btn-sm"
                            onClick={() => triggerUpload(type)}
                            disabled={busy || actionLoading === 'upload'}
                          >
                            {busy ? 'Yükleniyor…' : 'Yükle'}
                          </button>
                        )}
                      </td>
                    </tr>
                  )
                })}

                {/* Sağlık raporu — hep devre dışı satır */}
                <tr>
                  <td style={{ fontWeight: 500 }}>{DOC_TYPE_LABELS.health_report}</td>
                  <td>
                    <span style={{ fontSize: 13, color: 'var(--color-text-muted)' }}>
                      Hukuki onay ve güvenlik taraması bekleniyor.
                    </span>
                  </td>
                  <td>
                    <button className="btn btn-ghost btn-sm" disabled>
                      Hukuki onay ve güvenlik taraması bekleniyor.
                    </button>
                  </td>
                </tr>
              </tbody>
            </table>
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
                  return (
                    <tr key={doc.id}>
                      <td>{DOC_TYPE_LABELS[doc.document_type] ?? doc.document_type}</td>
                      <td style={{ fontSize: 13 }}>{doc.original_filename}</td>
                      <td><StatusBadge status={doc.review_status} /></td>
                      <td>{doc.is_sensitive ? '🔒 Evet' : '—'}</td>
                      <td style={{ fontSize: 13 }}>
                        {new Date(doc.uploaded_at).toLocaleDateString('tr-TR')}
                      </td>
                      <td>
                        <div style={{ display: 'flex', gap: 8 }}>
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
                            </>
                          )}
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
