// ─── Academy TypeScript Tipleri — backend şemalarıyla birebir eşleşir ──────────
// Backend alan adları Türkçedir (ad, aciklama, sira, vb.).
// Frontend bileşenlerinde bu alan adları doğrudan kullanılmalıdır.

export interface AcademyProgramListItem {
  id: string
  slug: string
  ad: string
  kod: string
  seviye: number // int: 1=Başlangıç, 2=Orta, 3=İleri
}

export interface AcademyLessonSummary {
  id: string
  slug: string
  ad: string
  ders_tipi: string
  sira: number
  tahmini_sure_dk: number | null
}

export interface AcademyModule {
  id: string
  slug: string
  ad: string
  sira: number
  lessons: AcademyLessonSummary[]
}

export interface AcademyProgramOut {
  id: string
  slug: string
  ad: string
  kod: string
  aciklama: string | null
  seviye: number
  modules: AcademyModule[]
}

export interface EnrollmentOut {
  id: string
  program_id: string
  status: string
  enrolled_at: string
}

export interface LessonStep {
  id: string
  tip: string // 'knot_animation' | 'text' | ...
  sira: number
  baslik: string | null
  data_json: Record<string, unknown>
}

export interface QuizQuestion {
  id: string
  sira: number
  soru_metni: string
  options: Array<{ harf: string; metin: string }> // [{"harf":"A","metin":"..."}]
}

export interface AcademyLessonOut {
  id: string
  slug: string
  ad: string
  aciklama: string | null
  ders_tipi: string
  sira: number
  tahmini_sure_dk: number | null
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
  tamamlandi: boolean
  yuzde: number
  toplam_sure_sn: number
  son_adim_sira: number | null
}

export interface QuizAttemptOut {
  id: string
  lesson_id: string
  basladi_at: string
  bitti_at: string | null
  dogru: number
  toplam: number
  gecti: boolean | null
}

export interface QuizAttemptStartOut {
  attempt: QuizAttemptOut
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

// KnotPlayer global tip bildirimi (knotplayer.js window'a yüklüyor)
export interface KnotPlayerInstance {
  goToStep(index: number): void
  play(): void
  pause(): void
  destroy(): void
}
