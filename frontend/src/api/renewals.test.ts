import { beforeEach, describe, expect, it, vi } from 'vitest'
import apiClient from './client'
import { renewalsApi } from './renewals'
vi.mock('./client', () => ({ default: { get: vi.fn() } }))
describe('Renewal exports preserve scope and filters', () => {
  const get = vi.mocked(apiClient.get)
  beforeEach(() => vi.resetAllMocks())
  it('loads all pages for the selected view and document kind', async () => {
    get.mockResolvedValueOnce({ data: { items: [{ id: '1' }], total: 2 } })
    get.mockResolvedValueOnce({ data: { items: [{ id: '2' }], total: 2 } })
    expect(await renewalsApi.listAll({ view: 'gecmis', kind: 'police' })).toHaveLength(2)
    expect(get).toHaveBeenNthCalledWith(2, '/renewals', { params: { view: 'gecmis', kind: 'police', skip: 1, limit: 200 } })
  })
  it('rejects failed later pages instead of exporting incomplete data', async () => {
    get.mockResolvedValueOnce({ data: { items: [{ id: '1' }], total: 2 } })
    get.mockRejectedValueOnce(new Error('offline'))
    await expect(renewalsApi.listAll({})).rejects.toThrow('offline')
  })
  it('rejects an empty page before the announced total', async () => {
    get.mockResolvedValueOnce({ data: { items: [], total: 1 } })
    await expect(renewalsApi.listAll({})).rejects.toThrow('Yenileme listesi tamamlanamadı.')
  })
})
