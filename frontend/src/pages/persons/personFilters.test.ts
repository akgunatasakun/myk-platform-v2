import { describe, expect, it } from 'vitest'
import { PERSON_FILTERS, personFilters, personListParams } from './personFilters'

describe('Directory filters', () => {
  it.each(PERSON_FILTERS.filter((f) => f.value))('sends $label as a server filter', ({ value }) => {
    expect(personListParams(new URLSearchParams({ role: value })).role_code).toBe(value)
  })
  it('preserves search, inactive records and page state when restoring a URL', () => {
    const params = new URLSearchParams('q=Deniz+Yelken&role=veli&active=false&page=3')
    expect(personFilters(params)).toEqual({ search: 'Deniz Yelken', role: 'veli', active: 'false', skip: 40 })
    expect(personListParams(params)).toEqual({ search: 'Deniz Yelken', role_code: 'veli', is_active: false, skip: 40, limit: 20 })
  })
  it('treats all people as an unfiltered server query', () => {
    expect(personListParams(new URLSearchParams())).toEqual({ search: undefined, role_code: undefined, is_active: undefined, skip: 0, limit: 20 })
  })
  it.each(['-1', '0', '1.5', 'bad', '999999999999999999999'])('rejects invalid page %s', (page) => {
    expect(personFilters(new URLSearchParams({ page })).skip).toBe(0)
  })
  it('ignores unknown role and active values and trims API searches', () => {
    const filters = personListParams(new URLSearchParams({ role: 'super_admin', active: 'bad', q: ' Deniz ' }))
    expect(filters.role_code).toBeUndefined()
    expect(filters.is_active).toBeUndefined()
    expect(filters.search).toBe('Deniz')
  })
})
