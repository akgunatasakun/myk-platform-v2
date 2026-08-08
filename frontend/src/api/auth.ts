/**
 * Auth API — kimlik doğrulama işlemleri.
 * Token yönetimi useAuth hook'unda; burada yalnızca ek endpoint çağrıları.
 */
import apiClient from './client'

export interface ChangePasswordPayload {
  current_password: string
  new_password: string
  confirm_password: string
}

export const authApi = {
  /** Kimlik doğrulanmış kullanıcının parolasını değiştirir. Başarıda 204 döner. */
  changePassword: (data: ChangePasswordPayload) =>
    apiClient.post('/auth/change-password', data),
}
