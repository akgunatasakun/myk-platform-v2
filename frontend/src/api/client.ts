/**
 * Axios istemcisi — token yenileme interceptor'ı ile.
 *
 * Tasarım:
 * - Access token bellek içinde (memory) tutulur. localStorage'a yazılmaz.
 * - Refresh token HttpOnly cookie olarak backend tarafından yönetilir.
 * - 401 alındığında /auth/refresh çağrısı yapılır; başarısızsa login'e yönlendir.
 */
import axios, {
  AxiosError,
  AxiosInstance,
  InternalAxiosRequestConfig,
} from 'axios'

const BASE_URL = '/api/v1'

export const apiClient: AxiosInstance = axios.create({
  baseURL: BASE_URL,
  withCredentials: true, // HttpOnly cookie gönder
  headers: {
    'Content-Type': 'application/json',
  },
})

// In-memory token saklama
let _accessToken: string | null = null

export function setAccessToken(token: string | null): void {
  _accessToken = token
}

export function getAccessToken(): string | null {
  return _accessToken
}

// İstek interceptor'ı — Bearer token ekle
apiClient.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  if (_accessToken) {
    config.headers.Authorization = `Bearer ${_accessToken}`
  }
  return config
})

// Yanıt interceptor'ı — 401 → token yenile
let _isRefreshing = false
let _pendingRequests: Array<(token: string) => void> = []

apiClient.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const originalRequest = error.config as InternalAxiosRequestConfig & {
      _retry?: boolean
    }

    if (
      error.response?.status === 401 &&
      !originalRequest._retry &&
      !originalRequest.url?.includes('/auth/refresh') &&
      !originalRequest.url?.includes('/auth/login')
    ) {
      if (_isRefreshing) {
        return new Promise((resolve) => {
          _pendingRequests.push((token: string) => {
            originalRequest.headers.Authorization = `Bearer ${token}`
            resolve(apiClient(originalRequest))
          })
        })
      }

      originalRequest._retry = true
      _isRefreshing = true

      try {
        const { data } = await apiClient.post<{ access_token: string }>('/auth/refresh')
        setAccessToken(data.access_token)
        _pendingRequests.forEach((cb) => cb(data.access_token))
        _pendingRequests = []
        originalRequest.headers.Authorization = `Bearer ${data.access_token}`
        return apiClient(originalRequest)
      } catch {
        setAccessToken(null)
        _pendingRequests = []
        // Çağıran hook login sayfasına yönlendirmeyi yönetir
        window.dispatchEvent(new CustomEvent('myk:session-expired'))
        return Promise.reject(error)
      } finally {
        _isRefreshing = false
      }
    }

    return Promise.reject(error)
  }
)

export default apiClient
