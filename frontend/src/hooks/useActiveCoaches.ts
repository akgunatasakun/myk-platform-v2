import { useEffect, useState } from 'react'
import { personsApi } from '@/api/persons'
import type { Person } from '@/types/person'

export function useActiveCoaches(isOpen: boolean) {
  const [coaches, setCoaches] = useState<Person[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [attempt, setAttempt] = useState(0)

  useEffect(() => {
    if (!isOpen) return
    let cancelled = false
    setCoaches([])
    setLoading(true)
    setError(null)
    personsApi.listActiveCoaches()
      .then((items) => {
        if (!cancelled) setCoaches(items)
      })
      .catch(() => {
        if (!cancelled) setError('Antrenör listesi yüklenemedi. Lütfen tekrar deneyin.')
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => { cancelled = true }
  }, [isOpen, attempt])

  return { coaches, loading, error, retry: () => setAttempt((value) => value + 1) }
}
