import apiClient from './client'
export const RENEWAL_MANAGERS = ['super_admin', 'kulup_yonetici', 'genel_sekreter']
export const RENEWAL_READERS = [...RENEWAL_MANAGERS, 'baskan', 'yk_uyesi', 'muhasebe']
export const RENEWAL_STATES = { eksik: 'Bitiş Tarihi Eksik', gecikti: 'Süresi Doldu', yaklasiyor: 'Yenileme Yaklaşıyor', guncel: 'Takipte', kapali: 'Geçmiş Dönem' }
export interface RenewalInput {
  document_id: string; kind: 'police' | 'sozlesme'; reference_no: string | null
  starts_on: string | null; expires_on: string | null; warning_days: number
  annual: boolean; responsible_user_id: string | null; notes: string | null
}
export interface Renewal extends RenewalInput {
  id: string; previous_id: string | null; is_closed: boolean; document_code: string; document_title: string
  responsible_name: string | null; days_remaining: number | null; state: keyof typeof RENEWAL_STATES
}
export interface RenewalParams { view?: 'acik' | 'gecmis' | 'uyari' | 'eksik' | 'gecikti'; kind?: 'police' | 'sozlesme'; search?: string; skip?: number; limit?: number }
export interface RenewalChoice { id: string; name: string }
export const renewalsApi = {
  list: (params?: RenewalParams) => apiClient.get<{ items: Renewal[]; total: number }>('/renewals', { params }),
  documents: (search: string, skip = 0) => apiClient.get<RenewalChoice[]>('/renewals/documents', { params: { search, skip, limit: 100 } }),
  responsibles: () => apiClient.get<RenewalChoice[]>('/renewals/responsibles'),
  create: (data: RenewalInput) => apiClient.post<Renewal>('/renewals', data),
  update: (id: string, data: RenewalInput) => apiClient.put<Renewal>(`/renewals/${id}`, data),
  renew: (id: string, data: RenewalInput) => apiClient.post<Renewal>(`/renewals/${id}/renew`, data),
  closure: (id: string, is_closed: boolean) => apiClient.patch<Renewal>(`/renewals/${id}/closure`, { is_closed }),
  listAll: async (params: RenewalParams) => {
    const items: Renewal[] = []
    let total: number
    do {
      const { data } = await renewalsApi.list({ ...params, skip: items.length, limit: 200 })
      total = data.total
      if (!data.items.length && items.length < total) throw new Error('Yenileme listesi tamamlanamadı.')
      items.push(...data.items)
    } while (items.length < total)
    return items
  },
}
