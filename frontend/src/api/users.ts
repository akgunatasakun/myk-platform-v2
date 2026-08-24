/**
 * Kullanıcı hesabı yönetimi API istemcisi — Sprint 18.
 * Backend: GET/POST/PATCH/DELETE /api/v1/users
 */
import apiClient from './client';
import type {
  UserOut,
  UserListOut,
  UserCreate,
  UserUpdate,
  UserCreateResponse,
  PasswordResetResponse,
} from '@/types/user';

export interface UserListParams {
  skip?: number;
  limit?: number;
  role?: string;
  is_active?: boolean;
  is_deleted?: boolean;
  search?: string;
}

export const usersApi = {
  list: (params?: UserListParams) =>
    apiClient.get<UserListOut>('/users', { params }),

  get: (id: string) =>
    apiClient.get<UserOut>(`/users/${id}`),

  create: (data: UserCreate) =>
    apiClient.post<UserCreateResponse>('/users', data),

  update: (id: string, data: UserUpdate) =>
    apiClient.patch<UserOut>(`/users/${id}`, data),

  delete: (id: string) =>
    apiClient.delete(`/users/${id}`),

  restore: (id: string) =>
    apiClient.post<UserOut>(`/users/${id}/restore`),

  resetPassword: (id: string) =>
    apiClient.post<PasswordResetResponse>(`/users/${id}/reset-password`),
};
