/**
 * Payment (Ödeme/Tahsilat) TypeScript tipleri.
 * Kaynak: backend/app/schemas/payment.py
 */

export type PaymentStatus = 'pending' | 'paid'

// ── PaymentCreate ─────────────────────────────────────────────────────────────

export interface PaymentCreate {
  person_id?: string | null
  amount: string               // Decimal → string
  payment_type?: string | null
  payment_method?: string | null
  due_date?: string | null
  paid_at?: string | null
  status?: PaymentStatus
  receipt_no?: string | null
  notes?: string | null
}

// ── PaymentUpdate (kısıtlı alanlar) ──────────────────────────────────────────
// Backend: yalnızca status, paid_at, payment_method, receipt_no, notes güncellenebilir

export interface PaymentUpdate {
  status?: PaymentStatus
  paid_at?: string | null
  payment_method?: string | null
  receipt_no?: string | null
  notes?: string | null
}

// ── PaymentOut ────────────────────────────────────────────────────────────────

export interface Payment {
  id: string
  club_id: string
  recorded_by_user_id: string | null
  person_id: string | null
  person_name: string | null
  amount: string
  payment_type: string | null
  payment_method: string | null
  due_date: string | null
  paid_at: string | null
  status: PaymentStatus
  receipt_no: string | null
  notes: string | null
  is_deleted: boolean
  created_at: string
  updated_at: string
}

export interface PaymentListResponse {
  items: Payment[]
  total: number
  skip: number
  limit: number
}

// ── OverduePaymentOut ─────────────────────────────────────────────────────────

export interface OverduePayment extends Payment {
  gecikme_gun: number
}

// ── Revenue Report ─────────────────────────────────────────────────────────────

export interface RevenueByMonth {
  ay: string               // YYYY-MM
  payment_type: string | null
  toplam: string           // Decimal → string
  adet: number
}

export interface RevenueReport {
  items: RevenueByMonth[]
  toplam_gelir: string     // Decimal → string
}
