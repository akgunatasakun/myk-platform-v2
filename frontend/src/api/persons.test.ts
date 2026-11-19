import { beforeEach, describe, expect, it, vi } from 'vitest'
import apiClient from './client'
import { personsApi } from './persons'

vi.mock('./client', () => ({ default: { get: vi.fn() } }))

describe('listActiveCoaches', () => {
  const get = vi.mocked(apiClient.get)

  beforeEach(() => vi.resetAllMocks())

  it('aktif antrenörleri 100 kayıtlık sayfalarla eksiksiz yükler', async () => {
    const firstPage = Array.from({ length: 100 }, (_, id) => ({ id: String(id) }))
    get.mockResolvedValueOnce({ data: { items: firstPage, total: 101 } })
    get.mockResolvedValueOnce({ data: { items: [{ id: '100' }], total: 101 } })

    expect(await personsApi.listActiveCoaches()).toHaveLength(101)
    expect(get).toHaveBeenNthCalledWith(1, '/persons', {
      params: { skip: 0, limit: 100, is_active: true, role_code: 'antrenor' },
    })
    expect(get).toHaveBeenNthCalledWith(2, '/persons', {
      params: { skip: 100, limit: 100, is_active: true, role_code: 'antrenor' },
    })
  })

  it('gerçekten boş bir listeyi başarılı sonuç olarak döndürür', async () => {
    get.mockResolvedValueOnce({ data: { items: [], total: 0 } })
    expect(await personsApi.listActiveCoaches()).toEqual([])
    expect(get).toHaveBeenCalledTimes(1)
  })

  it('istek hatasını boş bir listeye dönüştürmez', async () => {
    get.mockRejectedValueOnce(new Error('İstek başarısız'))
    await expect(personsApi.listActiveCoaches()).rejects.toThrow('İstek başarısız')
  })

  it('eksik bir sayfalama yanıtını reddeder', async () => {
    get.mockResolvedValueOnce({ data: { items: [{ id: '1' }], total: 2 } })
    get.mockResolvedValueOnce({ data: { items: [], total: 2 } })
    await expect(personsApi.listActiveCoaches()).rejects.toThrow('Antrenör listesi tamamlanamadı.')
  })
})
