import { apiClient } from './client'
import type {
  AcademyLessonOut,
  AcademyProgramListItem,
  AcademyProgramOut,
  EnrollmentOut,
  ProgressOut,
  QuizAttemptResult,
  QuizAttemptStartOut,
  SessionOut,
} from '@/types/academy'

export const academyApi = {
  listPrograms(): Promise<AcademyProgramListItem[]> {
    return apiClient.get('/academy/programs').then((r) => r.data)
  },

  getProgram(slug: string): Promise<AcademyProgramOut> {
    return apiClient.get(`/academy/programs/${slug}`).then((r) => r.data)
  },

  enroll(programId: string): Promise<EnrollmentOut> {
    return apiClient.post(`/academy/programs/${programId}/enroll`).then((r) => r.data)
  },

  myEnrollments(): Promise<EnrollmentOut[]> {
    return apiClient.get('/academy/me/enrollments').then((r) => r.data)
  },

  getLesson(slug: string): Promise<AcademyLessonOut> {
    return apiClient.get(`/academy/lessons/${slug}`).then((r) => r.data)
  },

  startSession(lessonId: string): Promise<SessionOut> {
    return apiClient.post(`/academy/lessons/${lessonId}/sessions`).then((r) => r.data)
  },

  heartbeat(sessionId: string): Promise<{ sure_saniye: number; yuzde: number }> {
    return apiClient.post(`/academy/sessions/${sessionId}/heartbeat`).then((r) => r.data)
  },

  getProgress(lessonId: string): Promise<ProgressOut> {
    return apiClient.get(`/academy/lessons/${lessonId}/progress`).then((r) => r.data)
  },

  startQuiz(lessonId: string): Promise<QuizAttemptStartOut> {
    return apiClient.post(`/academy/lessons/${lessonId}/quiz/attempts`).then((r) => r.data)
  },

  submitAnswer(attemptId: string, questionId: string, secilen_harf: string): Promise<void> {
    return apiClient
      .post(`/academy/quiz/attempts/${attemptId}/answers`, { question_id: questionId, secilen_harf })
      .then(() => undefined)
  },

  finishQuiz(attemptId: string): Promise<QuizAttemptResult> {
    return apiClient.post(`/academy/quiz/attempts/${attemptId}/finish`).then((r) => r.data)
  },

  getTimeline(slug: string): Promise<unknown> {
    return apiClient.get(`/academy/knot/${slug}/timeline`).then((r) => r.data)
  },
}
