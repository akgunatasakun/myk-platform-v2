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

  getDownloadUrl: (docId: string, revId: string, fileId: string): string =>
    `/api/v1/documents/${docId}/revisions/${revId}/files/${fileId}/download`,
}
