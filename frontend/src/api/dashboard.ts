import apiClient from './client';

export interface OturumOut {
  session_id: string
  course_id: string
  course_name: string
  session_date: string
  start_time?: string | null
  end_time?: string | null
  instructor_name?: string | null
  status: string
}

export interface AktiviteOut {
  id: string
  action: string
  resource_type: string
  resource_id?: string | null
  created_at: string
}

export interface DashboardStats {
  // kişi sayaçları
  toplam_kisi: number
  aktif_sporcu: number
  aktif_uye: number
  antrenor_sayisi: number
  // uyarı sayaçları
  bekleyen_basvuru: number
  vadesi_gecen_odeme: number
  vadesi_gecen_odeme_toplami: number
  bakim_bekleyen_ekipman: number
  // eğitim
  aktif_kurs_sayisi: number
  yaklasan_egitim: number
  bugunun_oturumlari: OturumOut[]
  yaklasan_oturumlar: OturumOut[]
  // feed
  son_aktiviteler: AktiviteOut[]
}

export const dashboardApi = {
  stats: () => apiClient.get<DashboardStats>('/dashboard/stats'),
}
