import { useNavigate } from 'react-router-dom'
import AppShell from '@/components/layout/AppShell'

export default function Forbidden() {
  const navigate = useNavigate()

  return (
    <AppShell title="Erişim Reddedildi">
      <div
        className="empty-state"
        style={{ minHeight: '60vh', justifyContent: 'center' }}
      >
        <div className="empty-state-icon">🚫</div>
        <div className="empty-state-title">Erişim Reddedildi</div>
        <div className="empty-state-desc" style={{ marginBottom: '24px' }}>
          Bu sayfayı görüntülemek için gerekli yetkiye sahip değilsiniz.
        </div>
        <button className="btn btn-primary" onClick={() => navigate('/dashboard')}>
          Ana Sayfaya Dön
        </button>
      </div>
    </AppShell>
  )
}
