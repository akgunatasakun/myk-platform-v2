import { useNavigate } from 'react-router-dom'
import AppShell from '@/components/layout/AppShell'

export default function NotFound() {
  const navigate = useNavigate()

  return (
    <AppShell title="Sayfa Bulunamadı">
      <div
        className="empty-state"
        style={{ minHeight: '60vh', justifyContent: 'center' }}
      >
        <div className="empty-state-icon">🔍</div>
        <div className="empty-state-title">404 — Sayfa Bulunamadı</div>
        <div className="empty-state-desc" style={{ marginBottom: '24px' }}>
          Aradığınız sayfa mevcut değil veya taşınmış olabilir.
        </div>
        <button className="btn btn-primary" onClick={() => navigate('/dashboard')}>
          Ana Sayfaya Dön
        </button>
      </div>
    </AppShell>
  )
}
