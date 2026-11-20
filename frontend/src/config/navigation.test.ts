import { describe, expect, it } from 'vitest'
import { visibleNavigation, itemActive, peopleTarget } from './navigation'
import { isRouteAllowed } from './access'
const paths = (role: string, query = '') => visibleNavigation(role, query).flatMap((g) => g.items.map((i) => i.path))

describe('Role-aware grouped navigation', () => {
  it('consolidates the administrator directory and removes sidebar notification duplication', () => {
    const result = paths('kulup_yonetici')
    expect(result).toContain('/persons')
    expect(result).not.toContain('/bildirimler')
    for (const path of ['/sporcular', '/veliler', '/uyeler', '/antrenorler']) expect(result).not.toContain(path)
    expect(visibleNavigation('kulup_yonetici').map((g) => g.id)).toEqual(['home', 'people', 'training', 'operations', 'administration', 'settings'])
  })
  it.each(['veli', 'sporcu', 'uye', 'misafir'])('does not expose administrative menus to %s', (role) => {
    const result = paths(role)
    for (const path of ['/persons', '/users', '/audit', '/ayarlar', '/yenilemeler', '/gorevler']) expect(result).not.toContain(path)
  })
  it('retains self-profile entries without giving directory access', () => {
    expect(paths('veli')).toContain('/veliler')
    expect(paths('sporcu')).toContain('/sporcular')
    expect(paths('uye')).toContain('/uyeler')
  })
  it('retains coach sport operations and does not mark two links active', () => {
    const items = visibleNavigation('antrenor').flatMap((g) => g.items)
    expect(items.map((i) => i.path)).toContain('/sporcular')
    expect(items.filter((i) => itemActive(i, '/sporcular/athlete-id')).map((i) => i.path)).toEqual(['/sporcular'])
  })
  it('keeps management documents and renewal route restrictions', () => {
    expect(paths('sportif_direktor')).not.toContain('/yenilemeler')
    expect(paths('muhasebe')).toContain('/yenilemeler')
    expect(paths('muhasebe')).not.toContain('/belgeler')
    expect(isRouteAllowed('/yenilemeler', 'veli')).toBe(false)
    expect(isRouteAllowed('/users/some-id', 'sporcu')).toBe(false)
    expect(isRouteAllowed('/belgeler/some-id', 'uye')).toBe(false)
  })
  it('handles Turkish and unaccented menu searches', () => {
    expect(paths('kulup_yonetici', 'KISI REHBERI')).toEqual(['/persons'])
    expect(paths('kulup_yonetici', 'yetkiler')).toEqual(['/users'])
    expect(paths('veli', 'yetkiler')).toEqual([])
    expect(paths('kulup_yonetici', 'bulunmayan')).toEqual([])
  })
  it('finds all available children when searching a group name', () => {
    expect(paths('kulup_yonetici', 'operasyon')).toEqual(['/tekneler', '/gorevler'])
  })
  it('opens the directory group for legacy administrator profile links', () => {
    const item = visibleNavigation('kulup_yonetici').flatMap((g) => g.items).find((i) => i.path === '/persons')!
    expect(itemActive(item, '/uyeler/member-id')).toBe(true)
    expect(itemActive(item, '/persons-other')).toBe(false)
  })
  it('uses filtered directory targets for admin counters while retaining scoped self-profile routes', () => {
    expect(peopleTarget('kulup_yonetici', 'sporcu')).toBe('/persons?role=sporcu&active=true')
    expect(peopleTarget('muhasebe', 'uye')).toBe('/persons?role=uye&active=true')
    expect(peopleTarget('veli', 'sporcu')).toBe('/sporcular')
    expect(peopleTarget('baskan', 'antrenor')).toBe('/antrenorler')
  })
})
