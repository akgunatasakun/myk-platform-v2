import apiClient from './client'
import type {
  OverduePayment,
  Payment,
  PaymentCreate,
  PaymentListResponse,
  PaymentUpdate,
  RevenueReport,
} from '@/types/payment'

export interface PaymentListParams {
  skip?: number
  limit?: number
  status?: string
  person_id?: string
}

export const paymentsApi = {
  // ── Listeler ───────────────────────────────────────────────────────────────
  list: (params?: PaymentListParams) =>
    apiClient.get<PaymentListResponse>('/payments', { params }),

  overdue: () =>
    apiClient.get<OverduePayment[]>('/payments/overdue'),

  revenueReport: (months = 12) =>
    apiClient.get<RevenueReport>('/payments/revenue-report', { params: { months } }),

  // ── Tekil ─────────────────────────────────────────────────────────────────
  get: (id: string) =>
    apiClient.get<Payment>(`/payments/${id}`),

  // ── Yazma ─────────────────────────────────────────────────────────────────
  create: (body: PaymentCreate) =>
    apiClient.post<Payment>('/payments', body),

  update: (id: string, body: PaymentUpdate) =>
    apiClient.put<Payment>(`/payments/${id}`, body),

  delete: (id: string) =>
    apiClient.delete<void>(`/payments/${id}`),
}
