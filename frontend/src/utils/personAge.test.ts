import { describe, expect, it } from 'vitest'
import { formatPersonAge, getPersonAge } from './personAge'

describe('getPersonAge', () => {
  it('bugün doğum günü olan kişinin yaşını artırır', () => {
    expect(getPersonAge('2015-09-04', new Date(2026, 8, 4))).toEqual({ completedYears: 11, birthYear: 2015 })
  })
  it('doğum günü yarın olan kişinin tamamlanmış yaşını döndürür', () => {
    expect(getPersonAge('2015-09-05', new Date(2026, 8, 4))?.completedYears).toBe(10)
  })
  it('29 Şubat doğumunu artık olmayan yılda 1 Martta artırır', () => {
    expect(getPersonAge('2012-02-29', new Date(2026, 1, 28))?.completedYears).toBe(13)
    expect(getPersonAge('2012-02-29', new Date(2026, 2, 1))?.completedYears).toBe(14)
  })
  it('null için yaş üretmez', () => {
    expect(getPersonAge(null, new Date(2026, 8, 4))).toBeNull()
    expect(formatPersonAge(null, new Date(2026, 8, 4))).toBe('—')
  })
  it('gelecekteki veya geçersiz tarihi reddeder', () => {
    expect(getPersonAge('2027-01-01', new Date(2026, 8, 4))).toBeNull()
    expect(getPersonAge('2026-02-30', new Date(2026, 8, 4))).toBeNull()
  })
  it('gösterimi yaş ve doğum yılı olarak biçimler', () => {
    expect(formatPersonAge('2015-09-04', new Date(2026, 8, 4))).toBe('11 yaş · 2015')
  })
})
