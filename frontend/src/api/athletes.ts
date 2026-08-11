import apiClient from './client'
import type {
  AthleteAlertItem,
  AthleteDetailOut,
  AthleteListOut,
  AthleteProfileUpdate,
} from '@/types/athlete'

export interface AthleteListParams {
  skip?: number
  limit?: number
  search?: string
  class_name?: string
  is_active?: boolean
}

export const athletesApi = {
  list: (params?: AthleteListParams) =>
    apiClient.get<AthleteListOut>('/athletes', { params }),

  alerts: () =>
    apiClient.get<AthleteAlertItem[]>('/athletes/alerts'),

  get: (personId: string) =>
    apiClient.get<AthleteDetailOut>(`/athletes/${personId}`),

  updateProfile: (personId: string, data: AthleteProfileUpdate) =>
    apiClient.patch<AthleteDetailOut>(`/athletes/${personId}`, data),
}
