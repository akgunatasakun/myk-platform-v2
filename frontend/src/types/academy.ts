// ─── Academy TypeScript Tipleri ───────────────────────────────────────────────

export interface AcademyProgramListItem {
  id: string
  slug: string
  title: string
  description: string | null
  seviye: string
  is_published: boolean
  club_id: string | null
}

export interface AcademyModule {
  id: string
  slug: string
  title: string
  siralama: number
  lessons: AcademyLessonSummary[]
}

export interface AcademyLessonSummary {
  id: string
  slug: string
  title: string
  lesson_type: string
  siralama: number
  sure_dakika: number | null
}

export interface AcademyProgramOut extends AcademyProgramListItem {
  modules: AcademyModule[]
}

export interface EnrollmentOut {
  id: string
  program_id: string
  person_id: string
  enrolled_at: string
}

export interface LessonStep {
  id: string
  step_type: string
  siralama: number
  baslik: string | null
  data_json: Record<string, unknown>
}

export interface QuizQuestion {
  id: string
  soru_metni: string
  secenekler: Record<string, string>
  aciklama: string | null
}

export interface AcademyLessonOut {
  id: string
  slug: string
  title: string
  lesson_type: string
  siralama: number
  sure_dakika: number | null
  steps: LessonStep[]
  quiz_questions: QuizQuestion[]
}

export interface SessionOut {
  id: string
  lesson_id: string
  started_at: string
}

export interface ProgressOut {
  lesson_id: string
  yuzde: number
  tamamlandi: boolean
  sure_saniye: number
}

export interface QuizAttemptStartOut {
  attempt_id: string
  questions: QuizQuestion[]
}

export interface QuizSoruResult {
  soru_metni: string
  secilen: string
  dogru_harf: string
  dogru_mu: boolean
  aciklama: string | null
}

export interface QuizAttemptResult {
  attempt_id: string
  dogru: number
  toplam: number
  gecti: boolean
  sorular: QuizSoruResult[]
}

// KnotPlayer global tip bildirimi (knotplayer.js window global'dan yükleniyor)
export interface KnotPlayerInstance {
  goToStep(index: number): void
  play(): void
  pause(): void
  setSpeed(multiplier: number): void
  destroy(): void
}

export interface KnotPlayerConstructor {
  new (container: HTMLElement, timeline: unknown, options?: { adapter?: string }): KnotPlayerInstance
  registerAdapter(name: string, AdapterClass: unknown): void
}
