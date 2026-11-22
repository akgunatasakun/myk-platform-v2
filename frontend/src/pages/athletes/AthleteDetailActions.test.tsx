import { describe, expect, it } from 'vitest'
import { renderToStaticMarkup } from 'react-dom/server'
import AthleteDetailActions from './AthleteDetailActions'

const roles = ['super_admin', 'kulup_yonetici', 'sportif_direktor', 'basantrenor', 'antrenor', 'baskan', 'yk_uyesi', 'genel_sekreter', 'muhasebe', 'personel', 'saglik_sorumlusu', 'guvenlik_operasyon', 'veli', 'sporcu', 'uye', 'misafir', 'unknown', undefined]

describe('Athlete detail action visibility matches server permissions', () => {
  it.each(roles)('checks existing and missing profile controls for %s', role => {
    for (const hasProfile of [false, true]) {
      const html = renderToStaticMarkup(<AthleteDetailActions role={role} hasProfile={hasProfile} onEdit={() => {}} onPerson={() => {}} />)
      expect(html.includes(hasProfile ? 'Profil Düzenle' : 'Profil Oluştur')).toBe(['super_admin', 'kulup_yonetici', 'sportif_direktor'].includes(role ?? ''))
      expect(html.includes('Kişi Kartı')).toBe(['super_admin', 'kulup_yonetici', 'muhasebe', 'antrenor'].includes(role ?? ''))
    }
  })
})
