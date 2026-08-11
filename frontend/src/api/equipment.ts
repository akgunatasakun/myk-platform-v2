import apiClient from './client'
import type {
  Equipment,
  EquipmentCreate,
  EquipmentListResponse,
  EquipmentUpdate,
  MaintenanceDueListResponse,
  MaintenanceRecord,
  MaintenanceRecordCreate,
  MaintenanceRecordListResponse,
  MaintenanceRecordUpdate,
} from '@/types/equipment'

export interface EquipmentListParams {
  skip?: number
  limit?: number
  status?: string
  search?: string
  is_active?: boolean
}

export const equipmentApi = {
  list: (params?: EquipmentListParams) =>
    apiClient.get<EquipmentListResponse>('/equipment', { params }),

  maintenanceDue: () =>
    apiClient.get<MaintenanceDueListResponse>('/equipment/maintenance-due'),

  get: (id: string) =>
    apiClient.get<Equipment>(`/equipment/${id}`),

  create: (data: EquipmentCreate) =>
    apiClient.post<Equipment>('/equipment', data),

  update: (id: string, data: EquipmentUpdate) =>
    apiClient.patch<Equipment>(`/equipment/${id}`, data),

  delete: (id: string) =>
    apiClient.delete(`/equipment/${id}`),

  // ── Maintenance Records ───────────────────────────────────────────────────

  listMaintenance: (equipmentId: string) =>
    apiClient.get<MaintenanceRecordListResponse>(`/equipment/${equipmentId}/maintenance`),

  getMaintenance: (equipmentId: string, recordId: string) =>
    apiClient.get<MaintenanceRecord>(`/equipment/${equipmentId}/maintenance/${recordId}`),

  createMaintenance: (equipmentId: string, data: MaintenanceRecordCreate) =>
    apiClient.post<MaintenanceRecord>(`/equipment/${equipmentId}/maintenance`, data),

  updateMaintenance: (equipmentId: string, recordId: string, data: MaintenanceRecordUpdate) =>
    apiClient.patch<MaintenanceRecord>(`/equipment/${equipmentId}/maintenance/${recordId}`, data),
}
