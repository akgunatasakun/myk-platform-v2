import type { PersonListParams } from '@/api/persons'
export const PERSON_PAGE_SIZE = 20
export const PERSON_FILTERS = [
  { value: '', label: 'Tümü' }, { value: 'sporcu', label: 'Sporcu' }, { value: 'veli', label: 'Veli' },
  { value: 'uye', label: 'Üye' }, { value: 'antrenor', label: 'Antrenör' },
  { value: 'personel', label: 'Personel' }, { value: 'misafir', label: 'Misafir' },
]
export function personFilters(params: URLSearchParams) {
  const role = params.get('role') ?? ''
  const active = params.get('active') ?? ''
  const page = Number(params.get('page') ?? '1')
  return {
    search: params.get('q') ?? '',
    role: PERSON_FILTERS.some((f) => f.value === role) ? role : '',
    active: ['true', 'false'].includes(active) ? active : '',
    skip: (Number.isSafeInteger(page) && page >= 1 && page <= 1000000 ? page - 1 : 0) * PERSON_PAGE_SIZE,
  }
}
export function personListParams(params: URLSearchParams): PersonListParams {
  const f = personFilters(params)
  return { skip: f.skip, limit: PERSON_PAGE_SIZE, search: f.search.trim() || undefined, role_code: f.role || undefined, is_active: f.active === '' ? undefined : f.active === 'true' }
}
