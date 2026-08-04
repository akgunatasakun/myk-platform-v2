import apiClient from './client';

export interface DashboardStats {
  toplam_kisi: number;
  aktif_sporcu: number;
  aktif_uye: number;
  antrenor_sayisi: number;
  vadesi_gecen_odeme: number;
  yaklasan_egitim: number;
  bakim_bekleyen_ekipman: number;
  son_aktiviteler: unknown[];
}

export const dashboardApi = {
  stats: () => apiClient.get<DashboardStats>('/dashboard/stats'),
};
