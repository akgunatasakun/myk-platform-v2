import { DOCUMENT_READERS } from '@/api/documentAccess'
import { RENEWAL_READERS } from '@/api/renewals'
import { TASK_ROLES } from '@/api/tasks'
import { CERTIFICATE_READERS } from '@/api/certificates'

// Mevcut rota izinleri. Menü düzeni bu yetkileri genişletmez.
export const PAYMENT_READERS = ['super_admin', 'kulup_yonetici', 'baskan', 'muhasebe', 'veli']
export const ADMIN       = ['super_admin', 'kulup_yonetici']
export const MANAGEMENT  = [...ADMIN, 'baskan', 'yk_uyesi']
export const SECRETARIAT = [...MANAGEMENT, 'genel_sekreter', 'muhasebe']
export const STAFF       = [...SECRETARIAT, 'sportif_direktor', 'basantrenor', 'antrenor',
                      'personel', 'saglik_sorumlusu', 'guvenlik_operasyon']
export const COACHES     = [...MANAGEMENT, 'sportif_direktor', 'basantrenor', 'antrenor', 'genel_sekreter']

// Route bazlı izin haritası — sadece kısıtlı rotalar (undefined = herkes)
const ROUTE_ROLES: Record<string, string[]> = {
  '/sertifikalar': CERTIFICATE_READERS,
  '/yenilemeler': RENEWAL_READERS,
  '/belgeler': DOCUMENT_READERS,
  '/gorevler': TASK_ROLES,
  '/admin/applications':  SECRETARIAT,
  '/admin/applications/': SECRETARIAT,
  '/persons':             STAFF,
  '/persons/':            STAFF,
  '/users':               [...MANAGEMENT, 'genel_sekreter'],
  '/audit':               ADMIN,
  '/sporcular':           [...STAFF, 'sporcu'],
  '/sporcular/':          [...STAFF, 'sporcu'],
  '/veliler':             [...SECRETARIAT, 'veli'],
  '/veliler/':            [...SECRETARIAT, 'veli'],
  '/uyeler':              [...SECRETARIAT, 'uye'],
  '/uyeler/':             [...SECRETARIAT, 'uye'],
  '/antrenorler':         [...SECRETARIAT, 'basantrenor', 'antrenor'],
  '/antrenorler/':        [...SECRETARIAT, 'basantrenor', 'antrenor'],
  '/akademi':             [...STAFF, 'sporcu', 'veli'],
  '/akademi/':            [...STAFF, 'sporcu', 'veli'],
  '/egitimler':           [...STAFF, 'sporcu', 'veli'],
  '/egitimler/':          [...STAFF, 'sporcu', 'veli'],
  '/yoklama':             COACHES,
  '/katilim':             ['sporcu'],
  '/tekneler':            STAFF,
  '/tekneler/':           STAFF,
  '/odemeler':            PAYMENT_READERS,
  '/raporlar':            SECRETARIAT,
  '/takvim':              [...STAFF, 'sporcu', 'veli', 'uye'],
  '/kutuphane':           [...MANAGEMENT, 'sportif_direktor', 'basantrenor', 'antrenor', 'genel_sekreter'],
  '/ayarlar':             ADMIN,
  '/antrenor-evrak-kuyrugu': [...ADMIN, 'basantrenor', 'antrenor'],
}

export function isRouteAllowed(pathname: string, role: string): boolean {
  // Tam eşleşme veya prefix eşleşmesi
  const matched = Object.entries(ROUTE_ROLES).find(([prefix]) =>
    pathname === prefix || pathname.startsWith(prefix.endsWith('/') ? prefix : prefix + '/')
  )
  if (!matched) return true  // Haritada yok → herkese açık
  return matched[1].includes(role)
}

