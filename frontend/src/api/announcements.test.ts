import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import apiClient from './client'
import { announcementsApi, publicationLabel } from './announcements'
import type { AnnouncementInput } from './announcements'
vi.mock('./client', () => ({ default: { get: vi.fn() } }))

describe('Announcement publication dates', () => {
  afterEach(() => vi.useRealTimers())
  const item: AnnouncementInput = { title: 'Başlık', body: 'Metin', status: 'yayinda', important: false, starts_on: null, ends_on: null, target_roles: [] }
  it('uses Istanbul date and includes the final publication day', () => {
    vi.useFakeTimers(); vi.setSystemTime(new Date('2026-11-19T21:30:00Z'))
    expect(publicationLabel({ ...item, starts_on: '2026-11-20', ends_on: '2026-11-20' })).toBe('Yayında')
    expect(publicationLabel({ ...item, starts_on: '2026-11-21' })).toBe('Planlandı')
    expect(publicationLabel({ ...item, ends_on: '2026-11-19' })).toBe('Süresi Doldu')
    expect(publicationLabel({ ...item, status: 'taslak', ends_on: '2026-11-19' })).toBe('Taslak')
    expect(publicationLabel({ ...item, status: 'arsiv' })).toBe('Arşiv')
  })
})

describe('Announcement export', () => {
  const get = vi.mocked(apiClient.get)
  beforeEach(() => vi.resetAllMocks())
  it('keeps manager scope and filters across all pages', async () => {
    get.mockResolvedValueOnce({ data: { items: [{ id: '1' }], total: 2 } })
    get.mockResolvedValueOnce({ data: { items: [{ id: '2' }], total: 2 } })
    expect(await announcementsApi.listAll({ manage: true, search: 'ders' })).toHaveLength(2)
    expect(get).toHaveBeenNthCalledWith(2, '/announcements', { params: { manage: true, search: 'ders', skip: 1, limit: 200 } })
  })
  it('does not export partial data when a later page fails', async () => {
    get.mockResolvedValueOnce({ data: { items: [{ id: '1' }], total: 2 } })
    get.mockRejectedValueOnce(new Error('offline'))
    await expect(announcementsApi.listAll({})).rejects.toThrow('offline')
  })
  it('rejects an incomplete empty page', async () => {
    get.mockResolvedValueOnce({ data: { items: [], total: 1 } })
    await expect(announcementsApi.listAll({})).rejects.toThrow('Duyuru listesi tamamlanamadı.')
  })
})
