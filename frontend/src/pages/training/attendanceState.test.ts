import { describe, expect, it, vi } from 'vitest'
import { loadCurrent, mayLeaveAttendance } from './attendanceState'

function deferred<T>() {
  let resolve!: (value: T) => void
  let reject!: (reason: unknown) => void
  const promise = new Promise<T>((yes, no) => { resolve = yes; reject = no })
  return { promise, resolve, reject }
}
const flush = async () => { await Promise.resolve(); await Promise.resolve(); await Promise.resolve() }

describe('attendance request ownership', () => {
  it('keeps the newer session when the old session arrives last', async () => {
    const old = deferred<string>(), next = deferred<string>()
    const apply = vi.fn(), fail = vi.fn(), done = vi.fn()
    const cancel = loadCurrent(() => old.promise, apply, fail, done)
    cancel()
    loadCurrent(() => next.promise, apply, fail, done)
    next.resolve('new session'); await flush()
    old.resolve('old session'); await flush()
    expect(apply.mock.calls).toEqual([['new session']])
    expect(done).toHaveBeenCalledTimes(1)
    expect(fail).not.toHaveBeenCalled()
  })
  it('ignores a late failure and completion after course change or unmount', async () => {
    const request = deferred<string>()
    const apply = vi.fn(), fail = vi.fn(), done = vi.fn()
    const cancel = loadCurrent(() => request.promise, apply, fail, done)
    cancel(); request.reject(new Error('old response')); await flush()
    expect(apply).not.toHaveBeenCalled()
    expect(fail).not.toHaveBeenCalled()
    expect(done).not.toHaveBeenCalled()
  })
  it('reports the active request failure and finishes loading', async () => {
    const error = new Error('network')
    const fail = vi.fn(), done = vi.fn()
    loadCurrent(() => Promise.reject(error), vi.fn(), fail, done)
    await flush()
    expect(fail).toHaveBeenCalledWith(error)
    expect(done).toHaveBeenCalledOnce()
  })
})

describe('attendance selection warning', () => {
  it('allows a clean selection without asking', () => {
    const confirm = vi.fn()
    expect(mayLeaveAttendance(false, confirm)).toBe(true)
    expect(confirm).not.toHaveBeenCalled()
  })
  it('keeps selection when discarding changes is declined', () => {
    expect(mayLeaveAttendance(true, () => false)).toBe(false)
  })
  it('allows selection when discarding changes is accepted', () => {
    expect(mayLeaveAttendance(true, () => true)).toBe(true)
  })
})
