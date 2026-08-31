/**
 * Program–yaş uyumluluk yardımcı fonksiyonu.
 *
 * Yaş bucket tablosu (kilit karar, değiştirilmez):
 *   7–10  → optimist
 *   11–14 → optimist, ilca
 *   15–17 → ilca, 420
 *   18+   → ilca, 420, wing_foil
 *   para_yelken → her yaşta muaf (uyarı yok)
 *
 * Uyarı yumuşak (soft): submit engellenmez, yönetici yönlendirir.
 */

export interface AgeBucket {
  minAge: number
  maxAge: number | null  // null = sınır yok
  programs: ReadonlySet<string>
}

export const AGE_BUCKETS: ReadonlyArray<AgeBucket> = [
  { minAge: 7,  maxAge: 10, programs: new Set(['optimist']) },
  { minAge: 11, maxAge: 14, programs: new Set(['optimist', 'ilca']) },
  { minAge: 15, maxAge: 17, programs: new Set(['ilca', '420']) },
  { minAge: 18, maxAge: null, programs: new Set(['ilca', '420', 'wing_foil']) },
]

const PROGRAM_HINTS: Record<string, string> = {
  optimist:    'Optimist programı genellikle 7–14 yaş aralığı içindir.',
  ilca:        'ILCA (Laser) programı genellikle 11 yaş ve üstü içindir.',
  '420':       '420 programı genellikle 15–17 yaş grubu içindir.',
  wing_foil:   'Wing Foil programı genellikle 18 yaş ve üstü içindir.',
  para_yelken: '',   // her zaman muaf
}

/**
 * Doğum tarihinden başvuru gününe kadar geçen tam yılı hesaplar.
 * Doğum tarihi yoksa null döner.
 */
export function calcAgeInYears(birthDateStr: string, referenceDate: Date = new Date()): number | null {
  if (!birthDateStr) return null
  const birth = new Date(birthDateStr)
  if (isNaN(birth.getTime())) return null

  let age = referenceDate.getFullYear() - birth.getFullYear()
  const m = referenceDate.getMonth() - birth.getMonth()
  if (m < 0 || (m === 0 && referenceDate.getDate() < birth.getDate())) {
    age--
  }
  return age
}

/** Geçerli program değerleri kümesi — backend enum ile senkron tutulmalı. */
export const VALID_PROGRAMS = new Set([
  'optimist', 'ilca', '420', 'wing_foil', 'para_yelken',
])

/**
 * URL `?program=` parametresini çözümler.
 *
 * Davranış:
 *   - Boş / null → { program: '', invalid: false }
 *   - Geçerli değer (büyük/küçük harf bağımsız, trim) → { program: 'normalised', invalid: false }
 *   - Geçersiz değer → { program: '', invalid: true }
 */
export function parseProgramParam(value: string | null): { program: string; invalid: boolean } {
  if (value === null || value === '') return { program: '', invalid: false }
  const normalised = value.trim().toLowerCase()
  if (VALID_PROGRAMS.has(normalised)) return { program: normalised, invalid: false }
  return { program: '', invalid: true }
}

/**
 * Verilen yaş ve program için yumuşak uyarı mesajı döner.
 * Uyumluysa ya da muafsa null döner.
 *
 * Örnekler:
 *   getProgramAgeHint('wing_foil', 8)    → uyarı mesajı
 *   getProgramAgeHint('ilca', 12)        → null
 *   getProgramAgeHint('optimist', 15)    → uyarı mesajı
 *   getProgramAgeHint('420', 21)         → null
 *   getProgramAgeHint('para_yelken', 8)  → null
 */
export function getProgramAgeHint(program: string, age: number): string | null {
  if (!program || program === 'para_yelken') return null

  const bucket = AGE_BUCKETS.find(
    b => age >= b.minAge && (b.maxAge === null || age <= b.maxAge)
  )

  if (!bucket) {
    // Yaş tanımlı bucket dışında (< 7 gibi)
    return PROGRAM_HINTS[program] ?? null
  }

  if (bucket.programs.has(program)) return null  // uyumlu

  return PROGRAM_HINTS[program] ?? 'Bu program için yaş aralığınız uygun olmayabilir.'
}
