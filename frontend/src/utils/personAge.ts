export interface PersonAge {
  completedYears: number
  birthYear: number
}

function parseIsoDate(value: string): { year: number; month: number; day: number } | null {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value)
  if (!match) return null
  const year = Number(match[1])
  const month = Number(match[2])
  const day = Number(match[3])
  const check = new Date(Date.UTC(year, month - 1, day))
  if (check.getUTCFullYear() !== year || check.getUTCMonth() !== month - 1 || check.getUTCDate() !== day) return null
  return { year, month, day }
}

/** Tamamlanmış yaşı yerel takvim gününe göre hesaplar; sonucu DB'ye yazmaz. */
export function getPersonAge(birthDate?: string | null, today = new Date()): PersonAge | null {
  if (!birthDate) return null
  const birth = parseIsoDate(birthDate)
  if (!birth || Number.isNaN(today.getTime())) return null
  const current = { year: today.getFullYear(), month: today.getMonth() + 1, day: today.getDate() }
  if (birth.year > current.year ||
      (birth.year === current.year && birth.month > current.month) ||
      (birth.year === current.year && birth.month === current.month && birth.day > current.day)) return null

  let completedYears = current.year - birth.year
  if (current.month < birth.month || (current.month === birth.month && current.day < birth.day)) completedYears -= 1
  return { completedYears, birthYear: birth.year }
}

export function formatPersonAge(birthDate?: string | null, today = new Date()): string {
  const age = getPersonAge(birthDate, today)
  return age ? `${age.completedYears} yaş · ${age.birthYear}` : '—'
}
