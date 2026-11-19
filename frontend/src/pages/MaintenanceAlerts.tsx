import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { equipmentApi } from '@/api/equipment'
import { useAuth } from '@/hooks/useAuth'
import type { MaintenanceDueEquipment } from '@/types/equipment'

const EQUIPMENT_READ_ROLES = new Set([
  'super_admin', 'kulup_yonetici', 'sportif_direktor', 'basantrenor',
  'antrenor', 'personel', 'guvenlik_operasyon',
])

export default function MaintenanceAlerts() {
  const { user } = useAuth()
  const canRead = EQUIPMENT_READ_ROLES.has(user?.role ?? '')
  const [items, setItems] = useState<MaintenanceDueEquipment[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(false)
  const [attempt, setAttempt] = useState(0)

  useEffect(() => {
    if (!canRead) return
    let cancelled = false
    setLoading(true)
    setError(false)
    equipmentApi.maintenanceDue()
      .then(({ data }) => { if (!cancelled) setItems(data.items) })
      .catch(() => { if (!cancelled) setError(true) })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [canRead, attempt])

  if (!canRead) return null

  return (
    <section className="card" style={{ marginBottom: 20 }} aria-label="Bakım ve sigorta uyarıları">
      <div className="card-header">Bakım ve Sigorta Uyarıları</div>
      <div className="card-body">
        {loading ? <p role="status">Uyarılar yükleniyor…</p> : error ? (
          <div role="alert">
            <p>Bakım ve sigorta uyarıları yüklenemedi.</p>
            <button className="btn btn-ghost" onClick={() => setAttempt((value) => value + 1)}>
              Tekrar Dene
            </button>
          </div>
        ) : (
          <>
            <p>{items.length === 0
              ? 'Yaklaşan veya gecikmiş bakım / sigorta kaydı yok.'
              : `${items.length} ekipmanda yaklaşan veya gecikmiş bakım / sigorta tarihi bulunuyor.`}</p>
            {items.slice(0, 5).map((item) => (
              <div key={item.id} style={{ marginBottom: 10 }}>
                <Link to={`/tekneler/${item.id}`}>{item.name}</Link>
                <div style={{ fontSize: 13, color: 'var(--color-text-muted)' }}>
                  {item.maintenance_due && <span>Bakım {item.next_maintenance_date && new Date(`${item.next_maintenance_date}T00:00:00`).toLocaleDateString('tr-TR')} </span>}
                  {item.insurance_due && <span>Sigorta {item.insurance_expiry_date && new Date(`${item.insurance_expiry_date}T00:00:00`).toLocaleDateString('tr-TR')}</span>}
                </div>
              </div>
            ))}
            <Link to="/tekneler?tab=due">Bakım ve sigorta listesini aç</Link>
          </>
        )}
      </div>
    </section>
  )
}
