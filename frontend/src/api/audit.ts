/**
 * Denetim kaydı API istemcisi — Sprint 19.
 */
import apiClient from './client'

export interface AuditLogItem {
  id: string
  user_id: string | null
  action: string
  resource_type: string
  resource_id: string | null
  ip_address: string | null
  user_agent: string | null
  success: boolean
  error_detail: string | null
  changes: Record<string, unknown> | null
  created_at: string
}

export interface AuditLogListOut {
  items: AuditLogItem[]
  total: number
  skip: number
  limit: number
}

export interface AuditLogParams {
  skip?: number
  limit?: number
  action?: string
  actor_user_id?: string
  resource_type?: string
  success?: boolean
  from?: string   // ISO 8601
  to?: string     // ISO 8601
}

export const auditApi = {
  list: (params?: AuditLogParams) =>
    apiClient.get<AuditLogListOut>('/audit-logs', { params }),
}
