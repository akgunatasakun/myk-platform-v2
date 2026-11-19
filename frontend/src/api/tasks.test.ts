import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import apiClient from './client'
import { tasksApi, taskIsOverdue } from './tasks'
import type { Task } from './tasks'
vi.mock('./client', () => ({ default: { get: vi.fn() } }))

describe('Task export pagination', () => {
  const get = vi.mocked(apiClient.get)
  beforeEach(() => vi.resetAllMocks())
  it('fetches every page while retaining filters', async () => {
    get.mockResolvedValueOnce({ data: { items: [{ id: '1' }], total: 2 } })
    get.mockResolvedValueOnce({ data: { items: [{ id: '2' }], total: 2 } })
    expect(await tasksApi.listAll({ open_only: true, assigned_person_id: 'person' })).toHaveLength(2)
    expect(get).toHaveBeenNthCalledWith(2, '/tasks', { params: { open_only: true, assigned_person_id: 'person', skip: 1, limit: 200 } })
  })
  it('rejects a partial export after a failed page', async () => {
    get.mockResolvedValueOnce({ data: { items: [{ id: '1' }], total: 2 } })
    get.mockRejectedValueOnce(new Error('offline'))
    await expect(tasksApi.listAll({})).rejects.toThrow('offline')
  })
  it('rejects an incomplete empty page', async () => {
    get.mockResolvedValueOnce({ data: { items: [], total: 1 } })
    await expect(tasksApi.listAll({})).rejects.toThrow('Görev listesi tamamlanamadı.')
  })
})

describe('Task due date in Turkey', () => {
  afterEach(() => vi.useRealTimers())
  it('uses the Istanbul date across UTC midnight and ignores completed tasks', () => {
    vi.useFakeTimers(); vi.setSystemTime(new Date('2026-11-19T21:30:00Z'))
    expect(taskIsOverdue({ due_date: '2026-11-19', status: 'acik' } as Task)).toBe(true)
    expect(taskIsOverdue({ due_date: '2026-11-20', status: 'acik' } as Task)).toBe(false)
    expect(taskIsOverdue({ due_date: '2026-11-19', status: 'tamamlandi' } as Task)).toBe(false)
    expect(taskIsOverdue({ due_date: null, status: 'acik' } as Task)).toBe(false)
  })
})
