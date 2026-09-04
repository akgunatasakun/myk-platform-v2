import { describe, expect, it } from 'vitest'
import { canManageGuardians } from './guardianPermissions'

describe('canManageGuardians', () => {
  it.each(['super_admin', 'kulup_yonetici'])(
    '%s rolüne veli oluşturma eylemini gösterir',
    (role) => expect(canManageGuardians(role)).toBe(true)
  )
  it.each(['baskan', 'yk_uyesi', 'genel_sekreter', 'muhasebe', 'veli', 'sporcu', 'uye', 'misafir', 'antrenor', 'personel'])(
    '%s rolüne yönetim eylemini göstermez',
    (role) => expect(canManageGuardians(role)).toBe(false)
  )
})
