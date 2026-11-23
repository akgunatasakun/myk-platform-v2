import { useEffect, useRef, useState } from 'react'
import { useRegisterSW } from 'virtual:pwa-register/react'
import UpdateNotice from './UpdateNotice'
import { confirmUpdate, createUpdateCheck } from './updateChecks'

export default function PwaUpdatePrompt() {
  const [registration, setRegistration] = useState<ServiceWorkerRegistration>()
  const [deferred, setDeferred] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const timeout = useRef<ReturnType<typeof setTimeout>>()
  const { needRefresh: [ready], updateServiceWorker } = useRegisterSW({
    onRegisteredSW(_url, value) { setRegistration(value) },
  })

  useEffect(() => {
    if (!registration) return
    const check = createUpdateCheck(registration, () => navigator.onLine, () => document.visibilityState === 'visible')
    const trigger = () => { void check() }
    const interval = window.setInterval(trigger, 15 * 60_000)
    window.addEventListener('focus', trigger)
    window.addEventListener('online', trigger)
    document.addEventListener('visibilitychange', trigger)
    trigger()
    return () => {
      clearInterval(interval)
      window.removeEventListener('focus', trigger)
      window.removeEventListener('online', trigger)
      document.removeEventListener('visibilitychange', trigger)
    }
  }, [registration])

  useEffect(() => () => clearTimeout(timeout.current), [])

  const update = async () => {
    if (busy) return
    setError('')
    try {
      const accepted = await confirmUpdate(
        () => window.confirm('Açık panel sekmelerindeki kaydedilmemiş bilgiler kaybolabilir. Güncellensin mi?'),
        async () => { setBusy(true); await updateServiceWorker(true) },
      )
      if (accepted) timeout.current = setTimeout(() => { setBusy(false); setError('Güncelleme tamamlanamadı. Diğer panel sekmelerini kapatıp tekrar deneyin.') }, 15_000)
    } catch { setBusy(false); setError('Güncelleme başlatılamadı. Tekrar deneyin.') }
  }

  return <UpdateNotice ready={ready} deferred={deferred} busy={busy} error={error}
    onUpdate={() => { void update() }} onDefer={() => setDeferred(true)} onOpen={() => setDeferred(false)} />
}
