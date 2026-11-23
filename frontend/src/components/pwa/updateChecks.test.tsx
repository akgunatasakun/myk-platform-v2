import { describe, expect, it, vi } from 'vitest'
import { renderToStaticMarkup } from 'react-dom/server'
import { confirmUpdate, createUpdateCheck } from './updateChecks'
import UpdateNotice from './UpdateNotice'

const noop = () => {}
const notice = { ready: true, deferred: false, busy: false, error: '', onUpdate: noop, onDefer: noop, onOpen: noop }

describe('Panel update notification', () => {
  it('is absent without a pending version and retains a deferred update entry', () => {
    expect(renderToStaticMarkup(<UpdateNotice {...notice} ready={false} />)).toBe('')
    const deferred = renderToStaticMarkup(<UpdateNotice {...notice} deferred />)
    expect(deferred).toContain('Yeni sürüm hazır')
    expect(deferred).not.toContain('Güncellemeden önce')
  })
  it('warns about unsaved information and disables actions during update', () => {
    const html = renderToStaticMarkup(<UpdateNotice {...notice} busy error="Tekrar deneyin." />)
    expect(html).toContain('açık panel sekmelerindeki bilgilerinizi kaydedin')
    expect(html).toContain('Güncelleniyor…')
    expect(html.match(/disabled=""/g)).toHaveLength(2)
    expect(html).toContain('role="alert"')
  })
  it('never applies an update after the user declines', async () => {
    const update = vi.fn()
    expect(await confirmUpdate(() => false, update)).toBe(false)
    expect(update).not.toHaveBeenCalled()
    expect(await confirmUpdate(() => true, update)).toBe(true)
    expect(update).toHaveBeenCalledOnce()
  })
  it('propagates application failures so the prompt can offer a retry', async () => {
    await expect(confirmUpdate(() => true, async () => { throw new Error('failed') })).rejects.toThrow('failed')
  })
})

describe('Update checks', () => {
  it('skips offline, hidden and installing states and throttles repeated focus events', async () => {
    let online = false, visible = true, time = 0
    const registration = { installing: null as unknown, update: vi.fn().mockResolvedValue(undefined) }
    const check = createUpdateCheck(registration, () => online, () => visible, () => time)
    await check(); expect(registration.update).not.toHaveBeenCalled()
    online = true; visible = false
    await check(); expect(registration.update).not.toHaveBeenCalled()
    visible = true; registration.installing = {}
    await check(); expect(registration.update).not.toHaveBeenCalled()
    registration.installing = null
    await check(); await check(); expect(registration.update).toHaveBeenCalledOnce()
    time = 60_000
    await check(); expect(registration.update).toHaveBeenCalledTimes(2)
  })
  it('does not overlap checks and can recover after an unavailable server', async () => {
    let finish!: () => void
    let time = 0
    const registration = { installing: null, update: vi.fn().mockImplementationOnce(() => new Promise<void>(resolve => { finish = resolve })).mockRejectedValueOnce(new Error('offline')).mockResolvedValue(undefined) }
    const check = createUpdateCheck(registration, () => true, () => true, () => time)
    const first = check(); time = 60_000; await check()
    expect(registration.update).toHaveBeenCalledOnce()
    finish(); await first; await check()
    time = 120_000; await check()
    expect(registration.update).toHaveBeenCalledTimes(3)
  })
})
