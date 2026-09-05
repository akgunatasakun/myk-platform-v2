/**
 * Kişisel evrak API — backend /person-documents endpoint'lerini sarmalar.
 * api/documents.ts veya types/document.ts'den hiçbir şey import edilmez.
 */
import apiClient from './client'
import type {
  DeleteRequestOut,
  HealthDocumentSummaryOut,
  PersonDocumentOut,
} from '@/types/person_document'

export interface UploadPersonDocumentPayload {
  subjectPersonId: string
  documentType: string
  file: File
  validUntil?: string | null
  processingBasis?: string | null
}

export const personDocumentsApi = {
  list: (subjectPersonId: string) =>
    apiClient.get<PersonDocumentOut[]>('/person-documents', {
      params: { subject_person_id: subjectPersonId },
    }),

  get: (documentId: string) =>
    apiClient.get<PersonDocumentOut>(`/person-documents/${documentId}`),

  getHealthSummary: (subjectPersonId: string) =>
    apiClient.get<HealthDocumentSummaryOut>(
      `/person-documents/health-summary/${subjectPersonId}`,
    ),

  approve: (documentId: string) =>
    apiClient.patch<PersonDocumentOut>(
      `/person-documents/${documentId}/approve`,
      {},
    ),

  reject: (documentId: string, rejectionReason: string) =>
    apiClient.patch<PersonDocumentOut>(
      `/person-documents/${documentId}/reject`,
      { rejection_reason: rejectionReason },
    ),

  upload: (payload: UploadPersonDocumentPayload) => {
    const form = new FormData()
    form.append('subject_person_id', payload.subjectPersonId)
    form.append('document_type', payload.documentType)
    form.append('file', payload.file)
    if (payload.validUntil) form.append('valid_until', payload.validUntil)
    if (payload.processingBasis)
      form.append('processing_basis', payload.processingBasis)
    return apiClient.post<PersonDocumentOut>('/person-documents', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },

  requestDelete: (documentId: string, reason?: string) =>
    apiClient.post<DeleteRequestOut>(
      `/person-documents/${documentId}/delete-request`,
      { reason: reason ?? '' },
    ),

  approveDeleteRequest: (documentId: string) =>
    apiClient.post<PersonDocumentOut>(
      `/person-documents/${documentId}/delete-request/approve`,
      {},
    ),

  rejectDeleteRequest: (documentId: string, reason: string) =>
    apiClient.post<DeleteRequestOut>(
      `/person-documents/${documentId}/delete-request/reject`,
      { rejection_reason: reason },
    ),

  deleteDocument: (documentId: string) =>
    apiClient.delete<{ deleted: boolean }>(`/person-documents/${documentId}`),
}

/**
 * Görüntüleme URL'ini döndürür — Bearer token axios interceptor'ı
 * üzerinden taşındığından doğrudan <a href> yerine streamPersonDocument
 * kullanın.
 */
export function getViewUrl(documentId: string): string {
  return `/api/v1/person-documents/${documentId}/view`
}

/**
 * Belgeyi tarayıcıda inline olarak açar (yeni sekme).
 * Authorization başlığı axios üzerinden taşınır.
 */
export async function streamPersonDocument(documentId: string): Promise<void> {
  const win = window.open('', '_blank')
  try {
    const resp = await apiClient.get<ArrayBuffer>(
      `/person-documents/${documentId}/view`,
      { responseType: 'arraybuffer' },
    )
    const blob = new Blob([resp.data], {
      type: (resp.headers['content-type'] as string) ?? 'application/octet-stream',
    })
    const blobUrl = URL.createObjectURL(blob)
    if (win) {
      win.location.href = blobUrl
    } else {
      window.location.href = blobUrl
    }
    setTimeout(() => URL.revokeObjectURL(blobUrl), 60_000)
  } catch (err) {
    win?.close()
    throw err
  }
}
