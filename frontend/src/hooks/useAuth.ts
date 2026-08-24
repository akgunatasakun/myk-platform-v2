/**
 * Auth hook — Zustand store üzerinden.
 * Bileşenler bu hook'u kullanır; doğrudan apiClient çağırmazlar.
 */
import { useEffect } from 'react'
import { create } from 'zustand'

import apiClient, { setAccessToken } from '@/api/client'
import type { AuthState, LoginRequest, UserResponse } from '@/types/auth'

interface AuthActions {
  login: (credentials: LoginRequest) => Promise<void>
  logout: () => Promise<void>
  fetchMe: () => Promise<void>
  clearSession: () => void
}

type AuthStore = AuthState & AuthActions

const useAuthStore = create<AuthStore>((set, get) => ({
  user: null,
  accessToken: null,
  isAuthenticated: false,
  // Başlangıçta true: ilk render'da ProtectedRoute spinner gösterir,
  // fetchMe tamamlanmadan login sayfasına yönlendirmez.
  isLoading: true,

  login: async (credentials) => {
    set({ isLoading: true })
    try {
      const { data } = await apiClient.post<{ access_token: string }>(
        '/auth/login',
        credentials
      )
      setAccessToken(data.access_token)
      set({ accessToken: data.access_token })
      await get().fetchMe()
    } finally {
      set({ isLoading: false })
    }
  },

  logout: async () => {
    try {
      await apiClient.post('/auth/logout')
    } catch {
      // Sessizce geç
    }
    setAccessToken(null)
    set({ user: null, accessToken: null, isAuthenticated: false })
  },

  fetchMe: async () => {
    set({ isLoading: true })
    try {
      const { data } = await apiClient.get<UserResponse>('/auth/me')
      set({ user: data, isAuthenticated: true, isLoading: false })
    } catch {
      set({ user: null, isAuthenticated: false, isLoading: false })
    }
  },

  clearSession: () => {
    setAccessToken(null)
    set({ user: null, accessToken: null, isAuthenticated: false, isLoading: false })
  },
}))

/** Sayfa yüklendiğinde /auth/me ile oturumu restore et. */
export function useAuthInit(): void {
  const fetchMe = useAuthStore((s) => s.fetchMe)
  const clearSession = useAuthStore((s) => s.clearSession)

  useEffect(() => {
    fetchMe()

    const handler = () => clearSession()
    window.addEventListener('myk:session-expired', handler)
    return () => window.removeEventListener('myk:session-expired', handler)
  }, [fetchMe, clearSession])
}

export function useAuth() {
  return useAuthStore()
}
