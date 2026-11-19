import { beforeEach, describe, expect, it, vi } from 'vitest'
import apiClient from './client'
import { equipmentApi } from './equipment'

vi.mock('./client', () => ({ default: { get: vi.fn() } }))

describe('equipmentApi.maintenanceDue', () => {
  const get = vi.mocked(apiClient.get)
  beforeEach(() => vi.resetAllMocks())

  it('sunucunun dizi yanıtını bakım ekranının liste biçimine dönüştürür', async () => {
    const items = [{ id: 'boat-1', name: 'Hansa 303', maintenance_due: true }]
    get.mockResolvedValueOnce({ data: items, status: 200 })
    const response = await equipmentApi.maintenanceDue()
    expect(response.data).toEqual({ items, total: 1 })
    expect(response.status).toBe(200)
    expect(get).toHaveBeenCalledWith('/equipment/maintenance-due')
  })

  it('boş dizi için geçerli boş liste döndürür', async () => {
    get.mockResolvedValueOnce({ data: [] })
    expect((await equipmentApi.maintenanceDue()).data).toEqual({ items: [], total: 0 })
  })

  it('items biçimindeki yanıtı korur', async () => {
    const data = { items: [{ id: 'boat-2' }], total: 1 }
    get.mockResolvedValueOnce({ data })
    expect((await equipmentApi.maintenanceDue()).data).toEqual(data)
  })

  it('yükleme hatasını boş listeye dönüştürmez', async () => {
    get.mockRejectedValueOnce(new Error('Bağlantı kesildi'))
    await expect(equipmentApi.maintenanceDue()).rejects.toThrow('Bağlantı kesildi')
  })
})
