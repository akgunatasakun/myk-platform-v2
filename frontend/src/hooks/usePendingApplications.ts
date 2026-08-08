/**
 * Bekleyen üyelik başvurusu sayısını çeker.
 *
 * - Mount'ta /dashboard/stats endpoint'ini çağırır.
 * - 'myk:application-updated' custom event'i alındığında yeniden çeker.
 *   (ApplicationDetailPage onay/red sonrası bu event'i fırlatır.)
 * - Hata durumunda sessiz fallback: sayı 0 kalır.
 */
import { useCallback, useEffect, useState } from 'react'
import { dashboardApi } from '@/api/dashboard'

export function usePendingApplications(): number {
  const [count, setCount] = useState(0)

  const refresh = useCallback(async () => {
    try {
      const resp = await dashboardApi.stats()
      setCount(resp.data.bekleyen_basvuru ?? 0)
    } catch {
      // sessiz fallback — badge gizli kalır
    }
  }, [])

  useEffect(() => {
    refresh()

    const handler = () => { void refresh() }
    window.addEventListener('myk:application-updated', handler)
    return () => window.removeEventListener('myk:application-updated', handler)
  }, [refresh])

  return count
}
