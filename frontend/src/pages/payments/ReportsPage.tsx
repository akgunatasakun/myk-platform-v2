/**
 * /raporlar — Gelir raporu
 *
 * Backend: GET /api/v1/payments/revenue-report?months=N
 * Dönen veri: { items: RevenueByMonth[], toplam_gelir: Decimal }
 * items.ay: "YYYY-MM" formatı — en yeni önce (backend sort: descending)
 */
import { useCallback, useEffect, useState } from 'react'
import AppShell from '@/components/layout/AppShell'
import { paymentsApi } from '@/api/payments'
import type { RevenueByMonth, RevenueReport } from '@/types/payment'

const MONTH_OPTIONS = [
  { value: 6, label: 'Son 6 ay' },
  { value: 12, label: 'Son 12 ay' },
  { value: 24, label: 'Son 24 ay' },
  { value: 36, label: 'Son 3 yıl' },
]

function fmtAmount(amount: string) {
  return `${parseFloat(amount).toLocaleString('tr-TR', { minimumFractionDigits: 2 })} ₺`
}

function fmtMonth(ay: string) {
  // YYYY-MM → Türkçe ay adı
  const [y, m] = ay.split('-')
  const months = [
    '', 'Ocak', 'Şubat', 'Mart', 'Nisan', 'Mayıs', 'Haziran',
    'Temmuz', 'Ağustos', 'Eylül', 'Ekim', 'Kasım', 'Aralık',
  ]
  return `${months[parseInt(m)]} ${y}`
}

export default function ReportsPage() {
  const [months, setMonths] = useState(12)
  const [report, setReport] = useState<RevenueReport | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async (m: number) => {
    setLoading(true)
    setError(null)
    try {
      const resp = await paymentsApi.revenueReport(m)
      setReport(resp.data)
    } catch {
      setError('Gelir raporu yüklenemedi.')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load(months) }, [months, load])

  // Aylara göre grupla: { ay → { payment_type → RevenueByMonth } }
  // Backend ay bazında birden fazla payment_type döndürebilir
  const byMonth = new Map<string, RevenueByMonth[]>()
  if (report) {
    for (const item of report.items) {
      if (!byMonth.has(item.ay)) byMonth.set(item.ay, [])
      byMonth.get(item.ay)!.push(item)
    }
  }

  // Ay sırası (backend zaten desc sıralı geliyor)
  const sortedMonths = Array.from(byMonth.keys())

  // payment_type dağılımı için özet
  const byType = new Map<string, { toplam: number; adet: number }>()
  if (report) {
    for (const item of report.items) {
      const key = item.payment_type ?? '(Türsüz)'
      const prev = byType.get(key) ?? { toplam: 0, adet: 0 }
      byType.set(key, {
        toplam: prev.toplam + parseFloat(item.toplam),
        adet: prev.adet + item.adet,
      })
    }
  }

  return (
    <AppShell title="Raporlar">
      <div className="page-header">
        <h1 className="page-title">Gelir Raporu</h1>
        <select
          className="form-select"
          style={{ width: 'auto' }}
          value={months}
          onChange={(e) => setMonths(parseInt(e.target.value))}
        >
          {MONTH_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>{o.label}</option>
          ))}
        </select>
      </div>

      {error && (
        <div className="alert alert-error"><span>⚠️</span><span>{error}</span></div>
      )}

      {loading ? (
        <div className="loading-center"><span className="loading-spinner lg" /></div>
      ) : !report || report.items.length === 0 ? (
        <div className="empty-state">
          <div className="empty-state-icon">📈</div>
          <div className="empty-state-title">Gelir Verisi Yok</div>
          <div className="empty-state-desc">Seçilen dönemde ödenmiş kayıt bulunamadı.</div>
        </div>
      ) : (
        <>
          {/* Özet kartlar */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: 12, marginBottom: 24 }}>
            <div className="card">
              <div className="card-body" style={{ textAlign: 'center', padding: '16px 12px' }}>
                <div style={{ fontSize: 12, color: 'var(--color-text-muted)', marginBottom: 4 }}>Toplam Gelir</div>
                <div style={{ fontSize: 22, fontWeight: 700, color: 'var(--color-success)' }}>
                  {fmtAmount(report.toplam_gelir)}
                </div>
              </div>
            </div>
            <div className="card">
              <div className="card-body" style={{ textAlign: 'center', padding: '16px 12px' }}>
                <div style={{ fontSize: 12, color: 'var(--color-text-muted)', marginBottom: 4 }}>Toplam İşlem</div>
                <div style={{ fontSize: 22, fontWeight: 700 }}>
                  {report.items.reduce((s, i) => s + i.adet, 0)}
                </div>
              </div>
            </div>
            <div className="card">
              <div className="card-body" style={{ textAlign: 'center', padding: '16px 12px' }}>
                <div style={{ fontSize: 12, color: 'var(--color-text-muted)', marginBottom: 4 }}>Aktif Ay</div>
                <div style={{ fontSize: 22, fontWeight: 700 }}>{sortedMonths.length}</div>
              </div>
            </div>
          </div>

          {/* Ödeme türü dağılımı */}
          {byType.size > 1 && (
            <div className="card" style={{ marginBottom: 24 }}>
              <div className="card-header"><div className="card-title">📊 Tür Bazında Özet</div></div>
              <div className="card-body" style={{ padding: 0 }}>
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Ödeme Türü</th>
                      <th style={{ textAlign: 'right' }}>İşlem Adedi</th>
                      <th style={{ textAlign: 'right' }}>Toplam</th>
                    </tr>
                  </thead>
                  <tbody>
                    {Array.from(byType.entries())
                      .sort((a, b) => b[1].toplam - a[1].toplam)
                      .map(([type, data]) => (
                        <tr key={type}>
                          <td>{type}</td>
                          <td style={{ textAlign: 'right' }}>{data.adet}</td>
                          <td style={{ textAlign: 'right', fontWeight: 600, color: 'var(--color-success)' }}>
                            {data.toplam.toLocaleString('tr-TR', { minimumFractionDigits: 2 })} ₺
                          </td>
                        </tr>
                      ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Aylık detay */}
          <div className="table-container">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Ay</th>
                  <th>Ödeme Türü</th>
                  <th style={{ textAlign: 'right' }}>Adet</th>
                  <th style={{ textAlign: 'right' }}>Toplam</th>
                </tr>
              </thead>
              <tbody>
                {sortedMonths.map((ay) => {
                  const rows = byMonth.get(ay)!
                  const ayToplam = rows.reduce((s, r) => s + parseFloat(r.toplam), 0)
                  const ayAdet = rows.reduce((s, r) => s + r.adet, 0)

                  if (rows.length === 1) {
                    return (
                      <tr key={ay}>
                        <td><strong>{fmtMonth(ay)}</strong></td>
                        <td>{rows[0].payment_type ?? '—'}</td>
                        <td style={{ textAlign: 'right' }}>{rows[0].adet}</td>
                        <td style={{ textAlign: 'right', fontWeight: 600, color: 'var(--color-success)' }}>
                          {fmtAmount(rows[0].toplam)}
                        </td>
                      </tr>
                    )
                  }

                  return (
                    <>
                      {rows.map((r, i) => (
                        <tr key={`${ay}-${i}`} style={{ background: i % 2 === 1 ? 'var(--color-bg-subtle)' : undefined }}>
                          <td style={{ color: 'var(--color-text-muted)', fontSize: 13 }}>
                            {i === 0 ? <strong>{fmtMonth(ay)}</strong> : ''}
                          </td>
                          <td style={{ fontSize: 13 }}>{r.payment_type ?? '—'}</td>
                          <td style={{ textAlign: 'right', fontSize: 13 }}>{r.adet}</td>
                          <td style={{ textAlign: 'right', fontSize: 13 }}>
                            {fmtAmount(r.toplam)}
                          </td>
                        </tr>
                      ))}
                      <tr style={{ borderTop: '2px solid var(--color-border)', background: 'var(--color-bg-subtle)' }}>
                        <td style={{ fontWeight: 600 }}>{fmtMonth(ay)} toplamı</td>
                        <td />
                        <td style={{ textAlign: 'right', fontWeight: 600 }}>{ayAdet}</td>
                        <td style={{ textAlign: 'right', fontWeight: 700, color: 'var(--color-success)' }}>
                          {ayToplam.toLocaleString('tr-TR', { minimumFractionDigits: 2 })} ₺
                        </td>
                      </tr>
                    </>
                  )
                })}
              </tbody>
            </table>
          </div>
        </>
      )}
    </AppShell>
  )
}
