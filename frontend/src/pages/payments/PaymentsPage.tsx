import { useCallback, useEffect, useState } from 'react'
import AppShell from '@/components/layout/AppShell'
import PaymentFormModal from './PaymentFormModal'
import { paymentsApi } from '@/api/payments'
import type { OverduePayment, Payment, PaymentListResponse, PaymentStatus } from '@/types/payment'
import { useAuth } from '@/hooks/useAuth'

const READ_ONLY_ROLES = new Set(['sporcu', 'veli', 'uye', 'misafir'])

// ── Sabitler ──────────────────────────────────────────────────────────────────

const STATUS_LABEL: Record<string, string> = {
  pending: 'Bekliyor',
  paid: 'Ödendi',
}

const STATUS_CLASS: Record<string, string> = {
  pending: 'badge-planlandi',
  paid: 'badge-aktif',
}

const STATUS_OPTIONS: { value: PaymentStatus | ''; label: string }[] = [
  { value: '', label: 'Tüm Durumlar' },
  { value: 'pending', label: 'Bekliyor' },
  { value: 'paid', label: 'Ödendi' },
]

function fmt(date: string | null) {
  if (!date) return '—'
  return new Date(date + 'T00:00:00').toLocaleDateString('tr-TR')
}

function fmtAmount(amount: string) {
  return `${parseFloat(amount).toLocaleString('tr-TR', { minimumFractionDigits: 2 })} ₺`
}

type Tab = 'all' | 'overdue'
const PAGE_SIZE = 50

// ── Component ─────────────────────────────────────────────────────────────────

export default function PaymentsPage() {
  const { user } = useAuth()
  const canWrite = !READ_ONLY_ROLES.has(user?.role ?? '')

  const [tab, setTab] = useState<Tab>('all')

  const [data, setData] = useState<PaymentListResponse | null>(null)
  const [overdueItems, setOverdueItems] = useState<OverduePayment[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const [statusFilter, setStatusFilter] = useState<PaymentStatus | ''>('')
  const [skip, setSkip] = useState(0)

  const [modalOpen, setModalOpen] = useState(false)
  const [editPayment, setEditPayment] = useState<Payment | undefined>(undefined)

  const fetchAll = useCallback(async (status: string, skipVal: number) => {
    setLoading(true)
    setError(null)
    try {
      const params: Record<string, unknown> = { skip: skipVal, limit: PAGE_SIZE }
      if (status) params.status = status
      const resp = await paymentsApi.list(params)
      setData(resp.data)
    } catch {
      setError('Ödemeler yüklenemedi.')
    } finally {
      setLoading(false)
    }
  }, [])

  const fetchOverdue = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const resp = await paymentsApi.overdue()
      setOverdueItems(resp.data)
    } catch {
      setError('Gecikmiş ödemeler yüklenemedi.')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    if (tab === 'all') fetchAll(statusFilter, skip)
    else fetchOverdue()
  }, [tab, statusFilter, skip, fetchAll, fetchOverdue])

  const handleSaved = (saved: Payment) => {
    setData((prev) => {
      if (!prev) return prev
      const exists = prev.items.some((p) => p.id === saved.id)
      if (exists) return { ...prev, items: prev.items.map((p) => (p.id === saved.id ? saved : p)) }
      return { ...prev, items: [saved, ...prev.items], total: prev.total + 1 }
    })
  }

  const handleDelete = async (payment: Payment, e: React.MouseEvent) => {
    e.stopPropagation()
    if (!window.confirm('Bu ödeme kaydını silmek istiyor musunuz?')) return
    try {
      await paymentsApi.delete(payment.id)
      if (tab === 'all') {
        setData((prev) =>
          prev
            ? { ...prev, items: prev.items.filter((p) => p.id !== payment.id), total: prev.total - 1 }
            : prev
        )
      } else {
        setOverdueItems((prev) => prev.filter((p) => p.id !== payment.id))
      }
    } catch {
      alert('Silme işlemi sırasında hata oluştu.')
    }
  }

  const openCreate = () => { setEditPayment(undefined); setModalOpen(true) }
  const openEdit = (payment: Payment, e: React.MouseEvent) => {
    e.stopPropagation()
    setEditPayment(payment)
    setModalOpen(true)
  }

  const totalPages = data ? Math.ceil(data.total / PAGE_SIZE) : 0
  const currentPage = Math.floor(skip / PAGE_SIZE) + 1
  const items: (Payment | OverduePayment)[] = tab === 'all' ? (data?.items ?? []) : overdueItems
  const isEmpty = !loading && items.length === 0

  // Toplam istatistik (all tab)
  const totalPending = data?.items.filter((p) => p.status === 'pending').reduce((s, p) => s + parseFloat(p.amount), 0) ?? 0
  const totalPaid = data?.items.filter((p) => p.status === 'paid').reduce((s, p) => s + parseFloat(p.amount), 0) ?? 0

  return (
    <AppShell title="Ödemeler">
      <div className="page-header">
        <h1 className="page-title">Ödemeler</h1>
        {canWrite && (
          <button className="btn btn-primary" onClick={openCreate}>+ Yeni Ödeme</button>
        )}
      </div>

      {/* Tabs */}
      <div style={{ display: 'flex', gap: 8, marginBottom: 16 }}>
        <button
          className={`btn btn-sm ${tab === 'all' ? 'btn-primary' : 'btn-ghost'}`}
          onClick={() => { setTab('all'); setSkip(0) }}
        >
          Tüm Ödemeler {data && `(${data.total})`}
        </button>
        <button
          className={`btn btn-sm ${tab === 'overdue' ? 'btn-primary' : 'btn-ghost'}`}
          onClick={() => setTab('overdue')}
          style={tab === 'overdue' ? {} : { color: 'var(--color-danger)', borderColor: 'var(--color-danger)' }}
        >
          ⚠️ Gecikmiş {tab === 'overdue' && `(${overdueItems.length})`}
        </button>
      </div>

      {/* Filtre — sadece "all" tab */}
      {tab === 'all' && (
        <div className="filter-bar">
          <select
            className="form-select"
            style={{ width: 'auto', minWidth: 160 }}
            value={statusFilter}
            onChange={(e) => { setStatusFilter(e.target.value as PaymentStatus | ''); setSkip(0) }}
          >
            {STATUS_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>{o.label}</option>
            ))}
          </select>

          {/* Mini özet */}
          {data && data.items.length > 0 && (
            <div style={{ display: 'flex', gap: 16, marginLeft: 'auto', fontSize: 13 }}>
              <span style={{ color: 'var(--color-text-muted)' }}>
                Bekliyor: <strong style={{ color: 'var(--color-warning)' }}>
                  {totalPending.toLocaleString('tr-TR', { minimumFractionDigits: 2 })} ₺
                </strong>
              </span>
              <span style={{ color: 'var(--color-text-muted)' }}>
                Ödendi: <strong style={{ color: 'var(--color-success)' }}>
                  {totalPaid.toLocaleString('tr-TR', { minimumFractionDigits: 2 })} ₺
                </strong>
              </span>
            </div>
          )}
        </div>
      )}

      {error && (
        <div className="alert alert-error"><span>⚠️</span><span>{error}</span></div>
      )}

      <div className="table-container">
        {loading ? (
          <div className="loading-center"><span className="loading-spinner lg" /></div>
        ) : isEmpty ? (
          <div className="empty-state">
            <div className="empty-state-icon">💳</div>
            <div className="empty-state-title">
              {tab === 'overdue' ? 'Gecikmiş Ödeme Yok' : 'Ödeme Bulunamadı'}
            </div>
            <div className="empty-state-desc">
              {tab === 'overdue'
                ? 'Tüm ödemeler zamanında — gecikmiş kayıt yok.'
                : 'Henüz ödeme kaydı yok. Yeni ödeme ekleyin.'}
            </div>
          </div>
        ) : (
          <>
            <table className="data-table">
              <thead>
                <tr>
                  <th>Kişi</th>
                  <th>Tutar</th>
                  <th>Tür</th>
                  <th>Yöntem</th>
                  <th>Son Tarih</th>
                  <th>Ödeme Tarihi</th>
                  {tab === 'overdue' && <th>Gecikme</th>}
                  <th>Durum</th>
                  {canWrite && <th>İşlemler</th>}
                </tr>
              </thead>
              <tbody>
                {items.map((p) => {
                  const isOverdue = tab === 'overdue'
                  const op = isOverdue ? (p as OverduePayment) : null
                  return (
                    <tr key={p.id}>
                      <td>
                        <strong>{p.person_name ?? '—'}</strong>
                        {p.receipt_no && (
                          <div style={{ fontSize: 11, color: 'var(--color-text-muted)' }}>
                            #{p.receipt_no}
                          </div>
                        )}
                      </td>
                      <td>
                        <strong style={{ color: p.status === 'paid' ? 'var(--color-success)' : undefined }}>
                          {fmtAmount(p.amount)}
                        </strong>
                      </td>
                      <td>{p.payment_type ?? '—'}</td>
                      <td>{p.payment_method ?? '—'}</td>
                      <td>
                        <span style={p.status === 'pending' && p.due_date && new Date(p.due_date) < new Date() ? { color: 'var(--color-danger)', fontWeight: 600 } : {}}>
                          {fmt(p.due_date)}
                        </span>
                      </td>
                      <td>{fmt(p.paid_at)}</td>
                      {isOverdue && (
                        <td>
                          <span style={{ color: 'var(--color-danger)', fontWeight: 600, fontSize: 13 }}>
                            {op!.gecikme_gun} gün
                          </span>
                        </td>
                      )}
                      <td>
                        <span className={`badge ${STATUS_CLASS[p.status] ?? ''}`}>
                          {STATUS_LABEL[p.status] ?? p.status}
                        </span>
                      </td>
                      {canWrite && (
                        <td>
                          <div style={{ display: 'flex', gap: 6 }}>
                            <button
                              className="btn btn-sm btn-secondary"
                              onClick={(e) => openEdit(p as Payment, e)}
                            >
                              Düzenle
                            </button>
                            <button
                              className="btn btn-sm btn-danger"
                              onClick={(e) => handleDelete(p as Payment, e)}
                            >
                              🗑
                            </button>
                          </div>
                        </td>
                      )}
                    </tr>
                  )
                })}
              </tbody>
            </table>

            {tab === 'all' && data && data.total > PAGE_SIZE && (
              <div className="pagination">
                <span>
                  {data.total} kayıttan {skip + 1}–{Math.min(skip + PAGE_SIZE, data.total)} arası gösteriliyor
                </span>
                <div className="pagination-controls">
                  <button
                    className="btn btn-sm btn-secondary"
                    disabled={skip === 0}
                    onClick={() => setSkip((s) => Math.max(0, s - PAGE_SIZE))}
                  >
                    ← Önceki
                  </button>
                  <span style={{ padding: '5px 10px', fontSize: 13 }}>
                    {currentPage} / {totalPages}
                  </span>
                  <button
                    className="btn btn-sm btn-secondary"
                    disabled={skip + PAGE_SIZE >= data.total}
                    onClick={() => setSkip((s) => s + PAGE_SIZE)}
                  >
                    Sonraki →
                  </button>
                </div>
              </div>
            )}
          </>
        )}
      </div>

      <PaymentFormModal
        isOpen={modalOpen}
        onClose={() => setModalOpen(false)}
        payment={editPayment}
        onSaved={handleSaved}
      />
    </AppShell>
  )
}
