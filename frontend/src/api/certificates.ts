import apiClient from './client'

export const CERTIFICATE_MANAGERS = ['super_admin', 'kulup_yonetici', 'genel_sekreter']
export const CERTIFICATE_READERS = [...CERTIFICATE_MANAGERS, 'baskan', 'yk_uyesi', 'sportif_direktor', 'basantrenor', 'antrenor', 'sporcu', 'veli']
export const CERTIFICATE_STATES = { draft: 'Taslak', issued: 'Düzenlendi', expired: 'Süresi Doldu', revoked: 'İptal Edildi' } as const
export type CertificateState = keyof typeof CERTIFICATE_STATES
export interface Certificate {
  id: string; enrollment_id: string; course_id: string; person_id: string
  title: string; person_name: string; course_name: string
  status: 'draft' | 'issued' | 'revoked'; state: CertificateState
  number: string | null; issued_on: string | null; expires_on: string | null
  notes: string | null; revocation_reason: string | null; created_at: string; updated_at: string
}
export interface CertificateParams { search?: string; state?: CertificateState; course_id?: string; enrollment_id?: string; skip?: number; limit?: number }
export interface CertificateOption { id: string; course_id: string; course_name: string; person_name: string }
export interface CertificateDraft { enrollment_id: string; title: string; notes: string | null }
export const certificatesApi = {
  list: (params: CertificateParams) => apiClient.get<{ items: Certificate[]; total: number; skip: number; limit: number }>('/certificates', { params }),
  options: (params: { search?: string; course_id?: string; enrollment_id?: string }) => apiClient.get<CertificateOption[]>('/certificates/enrollment-options', { params }),
  create: (body: CertificateDraft) => apiClient.post<Certificate>('/certificates', body),
  update: (id: string, body: { title: string; notes: string | null }) => apiClient.patch<Certificate>(`/certificates/${id}`, body),
  issue: (id: string, body: { issued_on: string; expires_on: string | null }) => apiClient.post<Certificate>(`/certificates/${id}/issue`, body),
  revoke: (id: string, reason: string) => apiClient.post<Certificate>(`/certificates/${id}/revoke`, { reason }),
  deleteDraft: (id: string) => apiClient.delete(`/certificates/${id}`),
  exportCsv: (params: CertificateParams) => apiClient.get<Blob>('/certificates/export', { params, responseType: 'blob' }),
}
export function certificateParams(url: URLSearchParams): CertificateParams {
  const state = url.get('state') ?? ''
  const page = Number(url.get('page') ?? 1)
  return {
    search: url.get('q')?.trim() || undefined,
    state: Object.prototype.hasOwnProperty.call(CERTIFICATE_STATES, state) ? state as CertificateState : undefined,
    course_id: url.get('course_id') || undefined, enrollment_id: url.get('enrollment_id') || undefined,
    skip: (Number.isSafeInteger(page) && page >= 1 && page <= 1000000 ? page - 1 : 0) * 20, limit: 20,
  }
}
