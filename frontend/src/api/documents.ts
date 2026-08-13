import apiClient from './client'
import type {
  Document,
  DocumentCreate,
  DocumentRevision,
  DocumentRevisionFile,
  RevisionCreate,
} from '@/types/document'

export interface DocumentListParams {
  q?: string
  document_type?: string
  content_status?: string
}

/** Authorization başlığını taşıyarak dosyayı indir ve Blob URL döndür. */
async function _fetchFileBlob(
  docId: string,
  revId: string,
  fileId: string,
  inline: boolean,
): Promise<{ blobUrl: string; filename: string }> {
  const params = inline ? '?inline=true' : ''
  const resp = await apiClient.get<ArrayBuffer>(
    `/documents/${docId}/revisions/${revId}/files/${fileId}/download${params}`,
    { responseType: 'arraybuffer' },
  )
  const contentDisposition = (resp.headers['content-disposition'] as string) ?? ''
  const match = contentDisposition.match(/filename="([^"]+)"/)
  const filename = match ? match[1] : 'dosya'
  const blob = new Blob([resp.data], {
    type: (resp.headers['content-type'] as string) ?? 'application/octet-stream',
  })
  return { blobUrl: URL.createObjectURL(blob), filename }
}

export const documentsApi = {
  list: (params?: DocumentListParams) =>
    apiClient.get<Document[]>('/documents', { params }),

  get: (id: string) =>
    apiClient.get<Document>(`/documents/${id}`),

  create: (data: DocumentCreate) =>
    apiClient.post<Document>('/documents', data),

  update: (id: string, data: Partial<DocumentCreate>) =>
    apiClient.patch<Document>(`/documents/${id}`, data),

  delete: (id: string) =>
    apiClient.delete(`/documents/${id}`),

  // ── Revisions ─────────────────────────────────────────────────────────────

  listRevisions: (docId: string) =>
    apiClient.get<DocumentRevision[]>(`/documents/${docId}/revisions`),

  createRevision: (docId: string, data: RevisionCreate) =>
    apiClient.post<DocumentRevision>(`/documents/${docId}/revisions`, data),

  // ── Files ─────────────────────────────────────────────────────────────────

  uploadFile: (
    docId: string,
    revId: string,
    file: File,
    fileRole: string = 'source',
  ) => {
    const formData = new FormData()
    formData.append('file', file)
    formData.append('file_role', fileRole)
    return apiClient.post<DocumentRevisionFile>(
      `/documents/${docId}/revisions/${revId}/files`,
      formData,
      { headers: { 'Content-Type': 'multipart/form-data' } },
    )
  },

  /**
   * PDF'i tarayıcıda inline olarak aç (yeni sekme).
   * Authorization başlığı axios üzerinden taşınır — MinIO URL'i asla istemciye sızmaz.
   */
  previewPdf: async (docId: string, revId: string, fileId: string): Promise<void> => {
    // Önce boş sekme aç — pop-up blocker ve Safari/Edge uyumluluğu için kritik.
    // window.open() async callback içinde değil, doğrudan kullanıcı etkileşimi
    // sırasında çağrıldığı için tarayıcı engel koymaz.
    const win = window.open('', '_blank')
    try {
      const { blobUrl } = await _fetchFileBlob(docId, revId, fileId, true)
      if (win) {
        win.location.href = blobUrl
      } else {
        // Pop-up engellenmiş — aynı sekmede aç
        window.location.href = blobUrl
      }
      setTimeout(() => URL.revokeObjectURL(blobUrl), 60_000)
    } catch (err) {
      win?.close()
      throw err
    }
  },

  /**
   * Dosyayı attachment olarak indir (attachment disposition).
   * Her dosya türü için çalışır.
   */
  downloadFile: async (docId: string, revId: string, fileId: string): Promise<void> => {
    const { blobUrl, filename } = await _fetchFileBlob(docId, revId, fileId, false)
    const a = document.createElement('a')
    a.href = blobUrl
    a.download = filename
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    setTimeout(() => URL.revokeObjectURL(blobUrl), 5_000)
  },
}
