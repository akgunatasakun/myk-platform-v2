import apiClient from './client'
import type { Notification, UnreadCount } from '@/types/notifications'

export const notificationsApi = {
  list: (params?: { limit?: number; unread_only?: boolean }) =>
    apiClient.get<Notification[]>('/notifications', { params }),

  unreadCount: () =>
    apiClient.get<UnreadCount>('/notifications/unread-count'),

  markRead: (id: string) =>
    apiClient.post<Notification>(`/notifications/${id}/read`),

  markAllRead: () =>
    apiClient.post<void>('/notifications/read-all'),
}
