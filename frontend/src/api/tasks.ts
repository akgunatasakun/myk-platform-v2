import apiClient from './client'

export const TASK_MANAGERS = ['super_admin', 'kulup_yonetici', 'genel_sekreter', 'sportif_direktor', 'basantrenor']
export const TASK_READ_ALL = [...TASK_MANAGERS, 'baskan', 'yk_uyesi']
export const TASK_ROLES = [...TASK_READ_ALL, 'antrenor', 'personel', 'muhasebe', 'saglik_sorumlusu', 'guvenlik_operasyon']
export const TASK_STATUSES = { acik: 'Açık', devam_ediyor: 'Devam Ediyor', tamamlandi: 'Tamamlandı', iptal: 'İptal' }
export const TASK_PRIORITIES = { dusuk: 'Düşük', normal: 'Normal', yuksek: 'Yüksek', acil: 'Acil' }
export type TaskStatus = keyof typeof TASK_STATUSES
export type TaskPriority = keyof typeof TASK_PRIORITIES
export interface TaskInput {
  title: string
  description: string | null
  assigned_person_id: string | null
  due_date: string | null
  priority: TaskPriority
  status: TaskStatus
}
export interface Task extends TaskInput {
  id: string
  assigned_person_name: string | null
  created_at: string
  updated_at: string
}
export interface TaskParams {
  search?: string
  status?: TaskStatus
  priority?: TaskPriority
  assigned_person_id?: string
  open_only?: boolean
  overdue_only?: boolean
  skip?: number
  limit?: number
}
export interface TaskList { items: Task[]; total: number; skip: number; limit: number }
export interface TaskAssignee { id: string; name: string }
export const tasksApi = {
  list: (params?: TaskParams) => apiClient.get<TaskList>('/tasks', { params }),
  assignees: () => apiClient.get<TaskAssignee[]>('/tasks/assignees'),
  create: (data: TaskInput) => apiClient.post<Task>('/tasks', data),
  update: (id: string, data: Partial<TaskInput>) => apiClient.patch<Task>(`/tasks/${id}`, data),
  delete: (id: string) => apiClient.delete(`/tasks/${id}`),
  listAll: async (params: TaskParams): Promise<Task[]> => {
    const items: Task[] = []
    let total: number
    do {
      const { data } = await tasksApi.list({ ...params, skip: items.length, limit: 200 })
      total = data.total
      if (!data.items.length && items.length < total) throw new Error('Görev listesi tamamlanamadı.')
      items.push(...data.items)
    } while (items.length < total)
    return items
  },
}

export function taskIsOverdue(task: Task): boolean {
  const today = new Intl.DateTimeFormat('en-CA', { timeZone: 'Europe/Istanbul', year: 'numeric', month: '2-digit', day: '2-digit' }).format(new Date())
  return !!task.due_date && task.due_date < today && ['acik', 'devam_ediyor'].includes(task.status)
}
