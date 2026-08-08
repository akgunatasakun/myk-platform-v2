import apiClient from './client';
import type { ApplicationListResponse, MembershipApplication } from '@/types/application';

export interface ApplicationListParams {
  skip?: number;
  limit?: number;
  /** Durum filtresi: 'submitted' | 'approved' | 'rejected' | 'cancelled' | 'draft' */
  status?: string;
}

export const applicationsApi = {
  list: (params?: ApplicationListParams) =>
    apiClient.get<ApplicationListResponse>('/membership-applications', { params }),

  get: (id: string) =>
    apiClient.get<MembershipApplication>(`/membership-applications/${id}`),

  /** Durum geçişi: submitted → approved / rejected / cancelled */
  transition: (id: string, to_status: string, reason?: string) =>
    apiClient.patch<MembershipApplication>(`/membership-applications/${id}/status`, {
      to_status,
      ...(reason ? { reason } : {}),
    }),
};
