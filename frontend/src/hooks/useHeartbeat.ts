import { useCallback, useEffect, useRef } from 'react'
import { academyApi } from '@/api/academy'

const INTERVAL_MS = 15_000
const VISIBILITY_TIMEOUT_MS = 60_000

/**
 * 15 saniyede bir heartbeat gönderir.
 * Koşullar: sekme görünür + son 60s kullanıcı aktivitesi var.
 * sessionId null/undefined ise heartbeat başlamaz.
 */
export function useHeartbeat(
  sessionId: string | null | undefined,
  onProgress?: (yuzde: number) => void,
) {
  const lastActivity = useRef<number>(Date.now())
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const recordActivity = useCallback(() => {
    lastActivity.current = Date.now()
  }, [])

  useEffect(() => {
    window.addEventListener('mousemove', recordActivity, { passive: true })
    window.addEventListener('keydown', recordActivity, { passive: true })
    window.addEventListener('scroll', recordActivity, { passive: true })
    window.addEventListener('touchstart', recordActivity, { passive: true })
    return () => {
      window.removeEventListener('mousemove', recordActivity)
      window.removeEventListener('keydown', recordActivity)
      window.removeEventListener('scroll', recordActivity)
      window.removeEventListener('touchstart', recordActivity)
    }
  }, [recordActivity])

  useEffect(() => {
    if (!sessionId) return

    const tick = async () => {
      if (document.hidden) return
      if (Date.now() - lastActivity.current > VISIBILITY_TIMEOUT_MS) return

      try {
        const result = await academyApi.heartbeat(sessionId)
        if (onProgress) onProgress(result.yuzde)
      } catch {
        // Sessizce geç — bağlantı kesilse bile UI'yi kırma
      }
    }

    timerRef.current = setInterval(tick, INTERVAL_MS)
    return () => {
      if (timerRef.current) clearInterval(timerRef.current)
    }
  }, [sessionId, onProgress])
}
