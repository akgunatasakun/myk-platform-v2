import apiClient from './client'
import type {
  AttendanceBulkResult,
  AttendanceBulkUpdate,
  AttendanceReport,
  SelfCheckinSession,
  TrainingAttendance,
  TrainingCourse,
  TrainingCourseCreate,
  TrainingCourseListResponse,
  TrainingCourseUpdate,
  TrainingEnrollment,
  TrainingSession,
  TrainingSessionCreate,
  TrainingSessionUpdate,
} from '@/types/training'

export interface TrainingCourseListParams {
  skip?: number
  limit?: number
  status?: string
  active_only?: boolean
}

export const trainingApi = {
  // ── Kurslar ────────────────────────────────────────────────────────────────
  listCourses: (params?: TrainingCourseListParams) =>
    apiClient.get<TrainingCourseListResponse>('/trainings', { params }),

  getCourse: (id: string) =>
    apiClient.get<TrainingCourse>(`/trainings/${id}`),

  createCourse: (body: TrainingCourseCreate) =>
    apiClient.post<TrainingCourse>('/trainings', body),

  updateCourse: (id: string, body: TrainingCourseUpdate) =>
    apiClient.patch<TrainingCourse>(`/trainings/${id}`, body),

  deleteCourse: (id: string) =>
    apiClient.delete<void>(`/trainings/${id}`),

  // ── Katılımcılar ───────────────────────────────────────────────────────────
  listParticipants: (courseId: string) =>
    apiClient.get<TrainingEnrollment[]>(`/trainings/${courseId}/participants`),

  addParticipant: (courseId: string, body: { person_id: string; notes?: string | null }) =>
    apiClient.post<TrainingEnrollment>(`/trainings/${courseId}/participants`, body),

  removeParticipant: (courseId: string, personId: string) =>
    apiClient.delete<void>(`/trainings/${courseId}/participants/${personId}`),

  // ── Oturumlar ──────────────────────────────────────────────────────────────
  listSessions: (courseId: string) =>
    apiClient.get<TrainingSession[]>(`/trainings/${courseId}/sessions`),

  createSession: (courseId: string, body: TrainingSessionCreate) =>
    apiClient.post<TrainingSession>(`/trainings/${courseId}/sessions`, body),

  updateSession: (courseId: string, sessionId: string, body: TrainingSessionUpdate) =>
    apiClient.patch<TrainingSession>(`/trainings/${courseId}/sessions/${sessionId}`, body),

  // ── Yoklama ────────────────────────────────────────────────────────────────
  getAttendance: (courseId: string, sessionId: string) =>
    apiClient.get<TrainingAttendance[]>(
      `/trainings/${courseId}/sessions/${sessionId}/attendance`
    ),

  bulkUpdateAttendance: (courseId: string, sessionId: string, body: AttendanceBulkUpdate) =>
    apiClient.put<AttendanceBulkResult>(
      `/trainings/${courseId}/sessions/${sessionId}/attendance`,
      body
    ),

  // ── Devam Raporu ───────────────────────────────────────────────────────────
  getAttendanceReport: (courseId: string) =>
    apiClient.get<AttendanceReport>(`/trainings/${courseId}/attendance/report`),

  // ── Self Check-in (Yetişkin Sporcu) ────────────────────────────────────────
  getSelfCheckinSessions: () =>
    apiClient.get<SelfCheckinSession[]>('/trainings/me/self-checkin-sessions'),

  selfCheckin: (courseId: string, sessionId: string) =>
    apiClient.post<TrainingAttendance>(
      `/trainings/${courseId}/sessions/${sessionId}/self-checkin`,
      {}
    ),
}
