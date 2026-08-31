/**
 * programAge.ts — unit testler
 *
 * Kilit kararlar (değiştirilmez):
 *   8+wing_foil  → uyarı
 *   12+ilca      → uyarı yok
 *   15+optimist  → uyarı
 *   21+420       → uyarı yok
 *   para_yelken  → daima uyarı yok
 *   invalid URL  → boş seçim + bilgilendirme (frontend mantığı, helper bazlı)
 */

import { describe, it, expect } from 'vitest'
import { getProgramAgeHint, calcAgeInYears, parseProgramParam } from './programAge'

// ─── parseProgramParam ────────────────────────────────────────────────────────

describe('parseProgramParam', () => {
  it('geçerli değer → program dolu, invalid false', () => {
    expect(parseProgramParam('ilca')).toEqual({ program: 'ilca', invalid: false })
  })

  it('büyük harf → normalise edilir, invalid false', () => {
    expect(parseProgramParam('ILCA')).toEqual({ program: 'ilca', invalid: false })
  })

  it('geçersiz değer → program boş, invalid true', () => {
    expect(parseProgramParam('foo')).toEqual({ program: '', invalid: true })
  })

  it('null → program boş, invalid false', () => {
    expect(parseProgramParam(null)).toEqual({ program: '', invalid: false })
  })

  it('boş string → program boş, invalid false', () => {
    expect(parseProgramParam('')).toEqual({ program: '', invalid: false })
  })

  it('trim sonrası geçerli → program dolu', () => {
    expect(parseProgramParam('  420  ')).toEqual({ program: '420', invalid: false })
  })
})

// ─── calcAgeInYears ────────────────────────────────────────────────────────────

describe('calcAgeInYears', () => {
  it('boş string → null', () => {
    expect(calcAgeInYears('')).toBeNull()
  })

  it('bugün doğanın yaşı 0', () => {
    const today = new Date()
    const isoToday = today.toISOString().slice(0, 10)
    expect(calcAgeInYears(isoToday, today)).toBe(0)
  })

  it('tam yıl önce doğulanın yaşı 12', () => {
    const ref = new Date('2026-06-15')
    expect(calcAgeInYears('2014-06-15', ref)).toBe(12)
  })

  it('henüz doğum günü gelmemiş — bir yaş az', () => {
    const ref = new Date('2026-06-14')
    expect(calcAgeInYears('2014-06-15', ref)).toBe(11)
  })
})

// ─── getProgramAgeHint — kilit kararlar ──────────────────────────────────────

describe('getProgramAgeHint — kilit kararlar', () => {
  it('8 yaş + wing_foil → uyarı', () => {
    expect(getProgramAgeHint('wing_foil', 8)).not.toBeNull()
  })

  it('12 yaş + ilca → uyarı yok', () => {
    expect(getProgramAgeHint('ilca', 12)).toBeNull()
  })

  it('15 yaş + optimist → uyarı', () => {
    expect(getProgramAgeHint('optimist', 15)).not.toBeNull()
  })

  it('21 yaş + 420 → uyarı yok', () => {
    expect(getProgramAgeHint('420', 21)).toBeNull()
  })

  it('para_yelken her yaşta uyarı yok', () => {
    for (const age of [6, 10, 18, 50]) {
      expect(getProgramAgeHint('para_yelken', age)).toBeNull()
    }
  })

  it('boş program → uyarı yok', () => {
    expect(getProgramAgeHint('', 10)).toBeNull()
  })
})

// ─── getProgramAgeHint — bucket sınır kontrolleri ────────────────────────────

describe('getProgramAgeHint — bucket sınırları', () => {
  // Bucket: 7–10 → sadece optimist
  it('7 yaş + optimist → uyarı yok', () => {
    expect(getProgramAgeHint('optimist', 7)).toBeNull()
  })
  it('10 yaş + ilca → uyarı', () => {
    expect(getProgramAgeHint('ilca', 10)).not.toBeNull()
  })

  // Bucket: 11–14 → optimist, ilca
  it('11 yaş + ilca → uyarı yok', () => {
    expect(getProgramAgeHint('ilca', 11)).toBeNull()
  })
  it('14 yaş + 420 → uyarı', () => {
    expect(getProgramAgeHint('420', 14)).not.toBeNull()
  })

  // Bucket: 15–17 → ilca, 420
  it('15 yaş + ilca → uyarı yok', () => {
    expect(getProgramAgeHint('ilca', 15)).toBeNull()
  })
  it('17 yaş + wing_foil → uyarı', () => {
    expect(getProgramAgeHint('wing_foil', 17)).not.toBeNull()
  })

  // Bucket: 18+ → ilca, 420, wing_foil
  it('18 yaş + wing_foil → uyarı yok', () => {
    expect(getProgramAgeHint('wing_foil', 18)).toBeNull()
  })
  it('30 yaş + optimist → uyarı', () => {
    expect(getProgramAgeHint('optimist', 30)).not.toBeNull()
  })
})
