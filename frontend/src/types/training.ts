/**
 * Training (Fiziksel Eğitim) TypeScript tipleri.
 * Kaynak: backend/app/schemas/training.py
 */

export type CourseStatus = 'planlandi' | 'aktif' | 'tamamlandi' | 'iptal'
export type SessionStatus = 'planli' | 'tamamlandi' | 'iptal'
export type EnrollmentStatus = 'active' | 'cancelled' | 'completed'
export type PaymentStatus = 'pending' | 'paid' | 'overdue'
export type AttendanceStatus = 'var' | 'yok' | 'izinli' | 'gecikti'

// ── TrainingCourse ────────────────────────────────────────────────────────────

export interface TrainingCourse {
  id: string
  club_id: string
  name: string
  description: string | null
  class_name: string | null
  level: string | null
  start_date: string | null
  end_date: string | null
  schedule_text: string | null
  capacity: number
  fee: string
  instructor_person_id: string | null
  instructor_name: string | null
  status: CourseStatus
  is_active: boolean
  is_deleted: boolean
  enrollment_count: number
  created_at: string
  updated_at: string
}

export interface TrainingCourseListResponse {
  items: TrainingCourse[]
  total: number
  skip: number
  limit: number
}

export interface TrainingCourseCreate {
  name: string
  description?: string | null
  class_name?: string | null
  level?: string | null
  start_date?: string | null
  end_date?: string | null
  schedule_text?: string | null
  capacity?: number
  fee?: string
  instructor_person_id?: string | null
  status?: CourseStatus
}

export interface TrainingCourseUpdate {
  name?: string
  description?: string | null
  class_name?: string | null
  level?: string | null
  start_date?: string | null
  end_date?: string | null
  schedule_text?: string | null
  capacity?: number
  fee?: string
  instructor_person_id?: string | null
  status?: CourseStatus
  is_active?: boolean
}

// ── TrainingSession ───────────────────────────────────────────────────────────

export interface TrainingSession {
  id: string
  club_id: string
  course_id: string
  session_date: string
  start_time: string | null
  end_time: string | null
  instructor_person_id: string | null
  instructor_name: string | null
  status: SessionStatus
  notes: string | null
  attendance_count: number
  created_at: string
  updated_at: string
}

export interface TrainingSessionCreate {
  session_date: string
  start_time?: string | null
  end_time?: string | null
  instructor_person_id?: string | null
  notes?: string | null
  status?: SessionStatus
}

export interface TrainingSessionUpdate {
  session_date?: string
  start_time?: string | null
  end_time?: string | null
  instructor_person_id?: string | null
  notes?: string | null
  status?: SessionStatus
}

// ── TrainingEnrollment ────────────────────────────────────────────────────────

export interface TrainingEnrollment {
  id: string
  club_id: string
  course_id: string
  person_id: string
  person_name: string | null
  status: EnrollmentStatus
  payment_status: PaymentStatus
  notes: string | null
  enrolled_at: string
  cancelled_at: string | null
  created_at: string
  updated_at: string
}

// ── TrainingAttendance ────────────────────────────────────────────────────────

export interface AttendanceRecord {
  person_id: string
  status: AttendanceStatus
  check_in_time?: string | null
  check_out_time?: string | null
  notes?: string | null
}

export interface AttendanceBulkUpdate {
  records: AttendanceRecord[]
}

export interface TrainingAttendance {
  id: string
  club_id: string
  session_id: string
  person_id: string
  person_name: string | null
  status: AttendanceStatus
  check_in_time: string | null
  check_out_time: string | null
  notes: string | null
  recorded_by_user_id: string | null
  created_at: string
  updated_at: string
}

export interface AttendanceBulkResult {
  updated: number
  created: number
}

// ── Attendance Report ─────────────────────────────────────────────────────────

export interface AttendancePersonSummary {
  person_id: string
  person_name: string
  var: number
  yok: number
  izinli: number
  gecikti: number
  toplam_oturum: number
  devam_yuzdesi: number
}

export interface AttendanceReport {
  course_id: string
  course_name: string
  toplam_oturum: number
  katilimcilar: AttendancePersonSummary[]
}
