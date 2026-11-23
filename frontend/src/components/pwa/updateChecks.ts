export interface UpdateRegistration {
  installing: unknown
  update: () => Promise<unknown>
}

export function createUpdateCheck(registration: UpdateRegistration, online: () => boolean, visible: () => boolean, now = Date.now) {
  let running = false
  let last = -Infinity
  return async () => {
    if (running || registration.installing || !online() || !visible() || now() - last < 60_000) return
    running = true
    last = now()
    try { await registration.update() } catch { /* Bağlantı hatasında sonraki kontrolde tekrar denenir. */ }
    finally { running = false }
  }
}

export async function confirmUpdate(confirm: () => boolean, update: () => Promise<void>) {
  if (!confirm()) return false
  await update()
  return true
}
