import apiClient from './client'
import type {
  Equipment,
  EquipmentCreate,
  EquipmentListResponse,
  EquipmentUpdate,
  MaintenanceDueEquipment,
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

  maintenanceDue: async () => {
    const response = await apiClient.get<MaintenanceDueEquipment[] | MaintenanceDueListResponse>(
      '/equipment/maintenance-due',
    )
    const data = Array.isArray(response.data)
      ? { items: response.data, total: response.data.length }
      : response.data
    return { ...response, data }
  },

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
