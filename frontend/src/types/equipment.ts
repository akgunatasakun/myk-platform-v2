export type EquipmentStatus = 'aktif' | 'bakimda' | 'hasarli' | 'hizmetdisi'

export interface Equipment {
  id: string
  club_id: string
  name: string
  equipment_type: string | null
  serial_no: string | null
  brand: string | null
  model: string | null
  purchase_date: string | null        // ISO date "YYYY-MM-DD"
  purchase_cost: string | null        // Decimal as string from API
  status: EquipmentStatus
  assigned_person_id: string | null
  assigned_person_name: string | null
  last_maintenance_date: string | null
  next_maintenance_date: string | null
  insurance_expiry_date: string | null
  notes: string | null
  is_active: boolean
  is_deleted: boolean
  created_at: string
  updated_at: string
}

export interface EquipmentListResponse {
  items: Equipment[]
  total: number
  skip: number
  limit: number
}

export interface EquipmentCreate {
  name: string
  equipment_type?: string | null
  serial_no?: string | null
  brand?: string | null
  model?: string | null
  purchase_date?: string | null
  purchase_cost?: number | null
  status?: EquipmentStatus
  assigned_person_id?: string | null
  last_maintenance_date?: string | null
  next_maintenance_date?: string | null
  insurance_expiry_date?: string | null
  notes?: string | null
  is_active?: boolean
}

export interface EquipmentUpdate {
  name?: string
  equipment_type?: string | null
  serial_no?: string | null
  brand?: string | null
  model?: string | null
  purchase_date?: string | null
  purchase_cost?: number | null
  status?: EquipmentStatus | null
  assigned_person_id?: string | null
  last_maintenance_date?: string | null
  next_maintenance_date?: string | null
  insurance_expiry_date?: string | null
  notes?: string | null
  is_active?: boolean
}

// maintenance-due endpoint ek alanları
export interface MaintenanceDueEquipment extends Equipment {
  maintenance_due: boolean
  maintenance_days_remaining: number | null
  insurance_due: boolean
  insurance_days_remaining: number | null
}

export interface MaintenanceDueListResponse {
  items: MaintenanceDueEquipment[]
  total: number
}

export interface MaintenanceRecord {
  id: string
  club_id: string
  equipment_id: string
  maintenance_date: string
  maintenance_type: string | null
  description: string | null
  cost: string | null
  performed_by: string | null
  next_maintenance_date: string | null
  notes: string | null
  recorded_by_user_id: string | null
  is_deleted: boolean
  created_at: string
  updated_at: string
}

export interface MaintenanceRecordListResponse {
  items: MaintenanceRecord[]
  total: number
}

export interface MaintenanceRecordCreate {
  maintenance_date: string
  maintenance_type?: string | null
  description?: string | null
  cost?: number | null
  performed_by?: string | null
  next_maintenance_date?: string | null
  notes?: string | null
}

export interface MaintenanceRecordUpdate {
  maintenance_date?: string
  maintenance_type?: string | null
  description?: string | null
  cost?: number | null
  performed_by?: string | null
  next_maintenance_date?: string | null
  notes?: string | null
}
