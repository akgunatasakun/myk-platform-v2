import { useLocation } from 'react-router-dom'
import AppShell from '@/components/layout/AppShell'

const PAGE_NAMES: Record<string, string> = {
  '/sporcular': 'Sporcular',
  '/veliler': 'Veliler',
  '/uyeler': 'Üyeler',
  '/antrenorler': 'Antrenörler',
  '/egitimler': 'Eğitimler',
  '/gruplar': 'Gruplar',
  '/yoklama': 'Yoklama',
  '/tekneler': 'Tekneler',
  '/odemeler': 'Ödemeler',
  '/raporlar': 'Raporlar',
  '/ayarlar': 'Ayarlar',
}

export default function ComingSoon() {
  const { pathname } = useLocation()
  const pageName = PAGE_NAMES[pathname] ?? 'Bu Sayfa'

  return (
    <AppShell title={pageName}>
      <div
        className="empty-state"
        style={{ minHeight: '60vh', justifyContent: 'center' }}
      >
        <div className="empty-state-icon">🚧</div>
        <div className="empty-state-title">{pageName} — Yapım Aşamasında</div>
        <div className="empty-state-desc">
          Bu modül henüz geliştirme aşamasındadır. Yakında kullanıma açılacaktır.
        </div>
      </div>
    </AppShell>
  )
}
