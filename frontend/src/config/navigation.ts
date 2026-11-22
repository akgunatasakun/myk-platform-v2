import { ADMIN, MANAGEMENT, SECRETARIAT, STAFF, COACHES, PAYMENT_READERS, isRouteAllowed } from './access'
import { DOCUMENT_READERS } from '@/api/documentAccess'
import { RENEWAL_READERS } from '@/api/renewals'
import { TASK_ROLES } from '@/api/tasks'
import { CERTIFICATE_READERS } from '@/api/certificates'

export interface NavItem { path: string; label: string; icon: string; roles?: string[]; hideFor?: string[]; activePaths?: string[] }
export interface NavGroup { id: string; label: string; icon: string; items: NavItem[] }
// /persons API'sindeki kisi:read izinleri; antrenörün kapsamını backend sınırlar.
export const DIRECTORY_ROLES = [...ADMIN, 'muhasebe', 'antrenor']
export const FULL_DIRECTORY = [...ADMIN, 'muhasebe']
export const NAV_GROUPS: NavGroup[] = [
  { id: 'home', label: 'Ana Sayfa', icon: '⌂', items: [
    { path: '/dashboard', label: 'Genel Bakış', icon: '📊' },
    { path: '/duyurular', label: 'Kulüp Panosu', icon: '📣' },
  ] },
  { id: 'people', label: 'Kişiler', icon: '👥', items: [
    { path: '/persons', label: 'Kişi Rehberi', icon: '👥', roles: DIRECTORY_ROLES, activePaths: ['/persons', '/sporcular', '/veliler', '/uyeler', '/antrenorler'] },
    { path: '/admin/applications', label: 'Başvurular', icon: '📋', roles: SECRETARIAT },
    // Rehbere yetkisi olmayan rollerin mevcut profil girişleri korunur.
    { path: '/sporcular', label: 'Sporcu Kayıtları', icon: '⛵', roles: [...STAFF, 'sporcu', 'veli'], hideFor: FULL_DIRECTORY },
    { path: '/veliler', label: 'Veli Kayıtları', icon: '👨‍👩‍👧', roles: SECRETARIAT, hideFor: FULL_DIRECTORY },
    { path: '/uyeler', label: 'Üyelik Kayıtları', icon: '🏅', roles: [...SECRETARIAT, 'uye'], hideFor: FULL_DIRECTORY },
    { path: '/antrenorler', label: 'Antrenör Kayıtları', icon: '🎯', roles: [...SECRETARIAT, 'basantrenor', 'antrenor'], hideFor: DIRECTORY_ROLES },
  ] },
  { id: 'training', label: 'Eğitim', icon: '📚', items: [
    { path: '/egitimler', label: 'Kurslar', icon: '📚', roles: [...STAFF, 'sporcu', 'veli'] },
    { path: '/takvim', label: 'Takvim', icon: '📅', roles: [...STAFF, 'sporcu', 'veli', 'uye'] },
    { path: '/yoklama', label: 'Yoklama', icon: '✅', roles: COACHES },
    { path: '/sertifikalar', label: 'Sertifika Kayıtları', icon: '📜', roles: CERTIFICATE_READERS },
    { path: '/katilim', label: 'Katılımım', icon: '🙋', roles: ['sporcu'] },
    { path: '/akademi', label: 'Deniz Akademisi', icon: '🪢', roles: [...STAFF, 'sporcu', 'veli'] },
    { path: '/kutuphane', label: 'Eğitim Kütüphanesi', icon: '📖', roles: COACHES },
    { path: '/antrenor-evrak-kuyrugu', label: 'Evrak Kontrolü', icon: '📋', roles: [...ADMIN, 'basantrenor', 'antrenor'] },
  ] },
  { id: 'operations', label: 'Operasyon', icon: '🛟', items: [
    { path: '/tekneler', label: 'Ekipmanlar', icon: '🛟', roles: STAFF },
    { path: '/gorevler', label: 'Görevler', icon: '✓', roles: TASK_ROLES },
  ] },
  { id: 'administration', label: 'Mali ve İdari', icon: '📂', items: [
    { path: '/odemeler', label: 'Ödemeler', icon: '💳', roles: PAYMENT_READERS },
    { path: '/belgeler', label: 'Belgeler', icon: '📂', roles: DOCUMENT_READERS },
    { path: '/yenilemeler', label: 'Yenilemeler', icon: '📑', roles: RENEWAL_READERS },
    { path: '/raporlar', label: 'Raporlar', icon: '📈', roles: SECRETARIAT },
  ] },
  { id: 'settings', label: 'Ayarlar', icon: '⚙️', items: [
    { path: '/ayarlar', label: 'Kulüp Ayarları', icon: '⚙️', roles: ADMIN },
    { path: '/users', label: 'Hesaplar ve Yetkiler', icon: '🔐', roles: [...MANAGEMENT, 'genel_sekreter'] },
    { path: '/audit', label: 'Denetim Kayıtları', icon: '🛡️', roles: ADMIN },
  ] },
]
export function matchesPath(pathname: string, path: string) { return pathname === path || pathname.startsWith(path + '/') }
export function itemActive(item: NavItem, pathname: string) { return (item.activePaths ?? [item.path]).some((p) => matchesPath(pathname, p)) }
export function normalizeMenuText(text: string) { return text.toLocaleLowerCase('tr-TR').replace(/ı/g, 'i').normalize('NFD').replace(/[\u0300-\u036f]/g, '') }
export function visibleNavigation(role: string, search = ''): NavGroup[] {
  const query = normalizeMenuText(search.trim())
  return NAV_GROUPS.map((group) => ({ ...group, items: group.items.map((item) => role === 'veli' && item.path === '/sporcular' ? { ...item, label: 'Bağlı Sporcular' } : item).filter((item) =>
    (!item.roles || item.roles.includes(role)) && !item.hideFor?.includes(role) && isRouteAllowed(item.path, role)
    && (!query || normalizeMenuText(group.label + ' ' + item.label).includes(query))
  ).map((item) => item.path === '/persons' && !FULL_DIRECTORY.includes(role) ? { ...item, activePaths: ['/persons'] } : item) })).filter((group) => group.items.length > 0)
}

export function peopleTarget(role: string, kind?: 'sporcu' | 'uye' | 'antrenor') {
  if (FULL_DIRECTORY.includes(role)) return kind ? `/persons?role=${kind}${kind === 'antrenor' ? '' : '&active=true'}` : '/persons'
  return kind === 'sporcu' ? '/sporcular' : kind === 'uye' ? '/uyeler' : kind === 'antrenor' ? '/antrenorler' : '/persons'
}
