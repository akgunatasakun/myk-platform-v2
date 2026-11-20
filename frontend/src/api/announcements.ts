import apiClient from './client'
import type { Role } from '@/types/auth'
export const ANNOUNCEMENT_MANAGERS = ['super_admin', 'kulup_yonetici', 'baskan', 'genel_sekreter']
export const AUDIENCE_LABELS: Record<Role, string> = {
  super_admin: 'Sistem Yöneticisi', kulup_yonetici: 'Kulüp Yöneticisi', baskan: 'Başkan', yk_uyesi: 'Yönetim Kurulu Üyesi', genel_sekreter: 'Genel Sekreter', muhasebe: 'Muhasebe', sportif_direktor: 'Sportif Direktör', basantrenor: 'Başantrenör', antrenor: 'Antrenör', personel: 'Personel', saglik_sorumlusu: 'Sağlık Sorumlusu', guvenlik_operasyon: 'Güvenlik ve Operasyon', veli: 'Veli', sporcu: 'Sporcu', uye: 'Üye', misafir: 'Misafir',
}
export const ANNOUNCEMENT_STATUSES = { taslak: 'Taslak', yayinda: 'Yayında', arsiv: 'Arşiv' }
export interface AnnouncementInput {
  title: string; body: string; status: keyof typeof ANNOUNCEMENT_STATUSES; important: boolean
  starts_on: string | null; ends_on: string | null; target_roles: Role[]
}
export interface Announcement extends AnnouncementInput { id: string; created_at: string; updated_at: string }
export interface AnnouncementParams { manage?: boolean; status?: AnnouncementInput['status']; search?: string; skip?: number; limit?: number }
export const announcementsApi = {
  list: (params?: AnnouncementParams) => apiClient.get<{ items: Announcement[]; total: number }>('/announcements', { params }),
  create: (data: AnnouncementInput) => apiClient.post<Announcement>('/announcements', data),
  update: (id: string, data: AnnouncementInput) => apiClient.put<Announcement>(`/announcements/${id}`, data),
  listAll: async (params: AnnouncementParams) => {
    const items: Announcement[] = []
    let total: number
    do {
      const { data } = await announcementsApi.list({ ...params, skip: items.length, limit: 200 })
      total = data.total
      if (!data.items.length && items.length < total) throw new Error('Duyuru listesi tamamlanamadı.')
      items.push(...data.items)
    } while (items.length < total)
    return items
  },
}
export function publicationLabel(item: AnnouncementInput): string {
  if (item.status !== 'yayinda') return ANNOUNCEMENT_STATUSES[item.status]
  const today = new Intl.DateTimeFormat('en-CA', { timeZone: 'Europe/Istanbul', year: 'numeric', month: '2-digit', day: '2-digit' }).format(new Date())
  if (item.starts_on && item.starts_on > today) return 'Planlandı'
  if (item.ends_on && item.ends_on < today) return 'Süresi Doldu'
  return 'Yayında'
}
