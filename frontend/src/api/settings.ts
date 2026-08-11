import apiClient from './client'
import type {
  Branch,
  BranchCreate,
  BranchUpdate,
  ClubSettings,
  ClubSettingsUpdate,
} from '@/types/settings'

export const settingsApi = {
  // ── Kulüp ──────────────────────────────────────────────────────────────────
  getClub: () =>
    apiClient.get<ClubSettings>('/settings/club'),

  updateClub: (data: ClubSettingsUpdate) =>
    apiClient.patch<ClubSettings>('/settings/club', data),

  // ── Branşlar ───────────────────────────────────────────────────────────────
  getBranches: () =>
    apiClient.get<Branch[]>('/settings/branches'),

  createBranch: (data: BranchCreate) =>
    apiClient.post<Branch>('/settings/branches', data),

  updateBranch: (id: string, data: BranchUpdate) =>
    apiClient.patch<Branch>(`/settings/branches/${id}`, data),
}
