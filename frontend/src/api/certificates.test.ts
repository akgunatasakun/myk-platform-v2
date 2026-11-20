import { describe, expect, it } from 'vitest'
import { certificateParams, CERTIFICATE_MANAGERS, CERTIFICATE_READERS } from './certificates'
import { isRouteAllowed } from '@/config/access'
import { visibleNavigation } from '@/config/navigation'

describe('Certificate filters and access', () => {
  it('restores filters and pagination from the training links', () => {
    expect(certificateParams(new URLSearchParams('q=%20Deniz%20&state=issued&course_id=course&enrollment_id=enrollment&page=3'))).toEqual({ search: 'Deniz', state: 'issued', course_id: 'course', enrollment_id: 'enrollment', skip: 40, limit: 20 })
  })
  it.each(['0', '-1', '1.5', 'bad', '99999999999999999'])('ignores invalid page %s', (page) => {
    expect(certificateParams(new URLSearchParams({ page, state: 'unknown' })).skip).toBe(0)
    expect(certificateParams(new URLSearchParams({ page, state: 'unknown' })).state).toBeUndefined()
  })
  it.each(CERTIFICATE_READERS)('shows certificate menu and route to %s', (role) => {
    expect(isRouteAllowed('/sertifikalar', role)).toBe(true)
    expect(visibleNavigation(role).flatMap((g) => g.items.map((i) => i.path))).toContain('/sertifikalar')
  })
  it.each(['uye', 'misafir', 'muhasebe', 'personel', 'saglik_sorumlusu', 'guvenlik_operasyon'])('keeps certificate menu closed to %s', (role) => {
    expect(isRouteAllowed('/sertifikalar', role)).toBe(false)
    expect(visibleNavigation(role).flatMap((g) => g.items.map((i) => i.path))).not.toContain('/sertifikalar')
  })
  it('keeps certificate management with administrators and secretary', () => {
    expect(CERTIFICATE_MANAGERS).toEqual(['super_admin', 'kulup_yonetici', 'genel_sekreter'])
  })
})
