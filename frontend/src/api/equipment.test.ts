import { beforeEach, describe, expect, it, vi } from 'vitest'
import apiClient from './client'
import { equipmentApi } from './equipment'

vi.mock('./client', () => ({ default: { get: vi.fn() } }))

describe('equipmentApi.listAll', () => {
  const get = vi.mocked(apiClient.get)
  beforeEach(() => vi.resetAllMocks())

  it('70 kaydın tamamını tek listede döndürür', async () => {
    const items = Array.from({ length: 70 }, (_, i) => ({ id: String(i) }))
    get.mockResolvedValueOnce({ data: { items, total: 70 } })
    expect(await equipmentApi.listAll()).toEqual({ items, total: 70, skip: 0, limit: 70 })
    expect(get).toHaveBeenCalledTimes(1)
  })

  it('sunucu sınırını aşmadan tüm sayfaları yükler ve filtreyi korur', async () => {
    const first = Array.from({ length: 200 }, (_, i) => ({ id: String(i) }))
    get.mockResolvedValueOnce({ data: { items: first, total: 201 } })
    get.mockResolvedValueOnce({ data: { items: [{ id: '200' }], total: 201 } })
    expect((await equipmentApi.listAll({ status: 'aktif' })).items).toHaveLength(201)
    expect(get).toHaveBeenNthCalledWith(1, '/equipment', {
      params: { status: 'aktif', skip: 0, limit: 200 },
    })
    expect(get).toHaveBeenNthCalledWith(2, '/equipment', {
      params: { status: 'aktif', skip: 200, limit: 200 },
    })
  })

  it('boş envanteri destekler', async () => {
    get.mockResolvedValueOnce({ data: { items: [], total: 0 } })
    expect(await equipmentApi.listAll()).toEqual({ items: [], total: 0, skip: 0, limit: 0 })
  })

  it('ikinci sayfa başarısızsa kısmi listeyi tamamlanmış gibi döndürmez', async () => {
    get.mockResolvedValueOnce({ data: { items: [{ id: '1' }], total: 2 } })
    get.mockRejectedValueOnce(new Error('Bağlantı kesildi'))
    await expect(equipmentApi.listAll()).rejects.toThrow('Bağlantı kesildi')
  })

  it('ilerlemeyen sayfalama yanıtını reddeder', async () => {
    get.mockResolvedValueOnce({ data: { items: [], total: 1 } })
    await expect(equipmentApi.listAll()).rejects.toThrow('Envanter listesi tamamlanamadı.')
  })
})

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
