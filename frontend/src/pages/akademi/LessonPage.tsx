/**
 * LessonPage — İzbarço (ve gelecekteki) ders ekranı.
 *
 * Akış:
 * 1. Ders yükle (lesson slug'dan)
 * 2. Session başlat → session_id al
 * 3. useHeartbeat → her 15s backend'e yuzde gönderir
 * 4. knot_animation adımı varsa KnotPlayer embed
 * 5. Progress bar (yuzde)
 * 6. Quiz section (ders tamamlanma için %60 geçiş)
 *
 * Güvenlik: correct_letter yok — backend quiz finish'te döner, sadece sonuç gösterilir.
 */
import { useCallback, useEffect, useRef, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import AppShell from '@/components/layout/AppShell'
import { academyApi } from '@/api/academy'
import { useHeartbeat } from '@/hooks/useHeartbeat'
import type {
  AcademyLessonOut,
  QuizAttemptResult,
  QuizAttemptStartOut,
  QuizQuestion,
} from '@/types/academy'

// KnotPlayer global tip — knotplayer.js window'a yüklüyor
interface KnotPlayerAPI {
  goToStep(i: number): void
  play(): void
  pause(): void
  destroy(): void
}

declare global {
  interface Window {
    KnotPlayer?: new (
      el: HTMLElement,
      timeline: unknown,
      opts?: { adapter?: string },
    ) => KnotPlayerAPI
    AnimeAdapter?: unknown
  }
}

// ─── KnotPlayer bileşeni ──────────────────────────────────────────────────────

interface KnotPlayerEmbedProps {
  knotSlug: string
  timelineUrl: string
}

function KnotPlayerEmbed({ knotSlug, timelineUrl }: KnotPlayerEmbedProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const playerRef = useRef<KnotPlayerAPI | null>(null)
  const [kpError, setKpError] = useState<string | null>(null)
  const [kpReady, setKpReady] = useState(false)

  useEffect(() => {
    let destroyed = false

    const init = async () => {
      try {
        // KnotPlayer script'i henüz yüklü değilse yükle
        if (!window.KnotPlayer) {
          await loadScript('/knots/knotplayer.js')
          await loadScript('/knots/adapters/anime-adapter.js')
        }

        const timeline = await academyApi.getTimeline(knotSlug)

        if (destroyed || !containerRef.current) return
        if (!window.KnotPlayer) {
          setKpError('KnotPlayer yüklenemedi.')
          return
        }

        playerRef.current = new window.KnotPlayer(containerRef.current, timeline, {
          adapter: 'anime',
        })
        setKpReady(true)
      } catch {
        if (!destroyed) setKpError('Animasyon yüklenemedi.')
      }
    }

    init()

    return () => {
      destroyed = true
      playerRef.current?.destroy()
      playerRef.current = null
    }
  }, [knotSlug, timelineUrl])

  if (kpError) {
    return (
      <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--color-text-secondary)' }}>
        ⚠️ {kpError}
      </div>
    )
  }

  return (
    <div
      style={{
        background: '#041224',
        borderRadius: '12px',
        overflow: 'hidden',
        marginBottom: '1.5rem',
        minHeight: 280,
        position: 'relative',
      }}
    >
      {!kpReady && (
        <div style={{ position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <span className="loading-spinner lg" />
        </div>
      )}
      <div ref={containerRef} className="kp" />
    </div>
  )
}

function loadScript(src: string): Promise<void> {
  return new Promise((resolve, reject) => {
    if (document.querySelector(`script[src="${src}"]`)) { resolve(); return }
    const s = document.createElement('script')
    s.src = src
    s.onload = () => resolve()
    s.onerror = () => reject(new Error(`Script yüklenemedi: ${src}`))
    document.head.appendChild(s)
  })
}

// ─── Quiz bileşeni ────────────────────────────────────────────────────────────

interface QuizSectionProps {
  lessonId: string
  questions: QuizQuestion[]
  onPass: () => void
}

function QuizSection({ lessonId, questions, onPass }: QuizSectionProps) {
  const [attempt, setAttempt] = useState<QuizAttemptStartOut | null>(null)
  const [answers, setAnswers] = useState<Record<string, string>>({})
  const [result, setResult] = useState<QuizAttemptResult | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [starting, setStarting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const startQuiz = async () => {
    setStarting(true)
    setError(null)
    try {
      const att = await academyApi.startQuiz(lessonId)
      setAttempt(att)
      setAnswers({})
      setResult(null)
    } catch {
      setError('Quiz başlatılamadı.')
    } finally {
      setStarting(false)
    }
  }

  const handleAnswer = (questionId: string, harf: string) => {
    setAnswers((prev) => ({ ...prev, [questionId]: harf }))
  }

  const submitQuiz = async () => {
    if (!attempt) return
    setSubmitting(true)
    setError(null)
    try {
      for (const q of attempt.questions) {
        const secilen = answers[q.id]
        if (secilen) {
          await academyApi.submitAnswer(attempt.attempt_id, q.id, secilen)
        }
      }
      const res = await academyApi.finishQuiz(attempt.attempt_id)
      setResult(res)
      if (res.gecti) onPass()
    } catch {
      setError('Quiz gönderilemedi.')
    } finally {
      setSubmitting(false)
    }
  }

  const allAnswered = attempt
    ? attempt.questions.every((q) => answers[q.id])
    : false

  if (questions.length === 0) return null

  return (
    <div className="card" style={{ marginTop: '1.5rem' }}>
      <div className="card-body">
        <h3 className="card-title">📝 Bilgi Kontrolü</h3>

        {error && <div className="alert alert-error" style={{ marginBottom: '1rem' }}>{error}</div>}

        {!attempt && !result && (
          <div>
            <p style={{ color: 'var(--color-text-secondary)', marginBottom: '1rem' }}>
              {questions.length} soruluk quiz — geçmek için %60 doğru gerekli.
            </p>
            <button className="btn btn-primary" disabled={starting} onClick={startQuiz}>
              {starting ? 'Başlatılıyor…' : 'Quiz\'e Başla'}
            </button>
          </div>
        )}

        {attempt && !result && (
          <div>
            {attempt.questions.map((q, idx) => (
              <div key={q.id} style={{ marginBottom: '1.5rem' }}>
                <p style={{ fontWeight: 600, marginBottom: '0.5rem' }}>
                  {idx + 1}. {q.soru_metni}
                </p>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.4rem' }}>
                  {Object.entries(q.secenekler).map(([harf, metin]) => (
                    <label
                      key={harf}
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: '0.5rem',
                        padding: '0.5rem 0.75rem',
                        borderRadius: '8px',
                        border: `1.5px solid ${answers[q.id] === harf ? 'var(--color-primary)' : 'var(--color-border)'}`,
                        cursor: 'pointer',
                        background: answers[q.id] === harf ? 'rgba(var(--color-primary-rgb), 0.08)' : 'transparent',
                      }}
                    >
                      <input
                        type="radio"
                        name={q.id}
                        value={harf}
                        checked={answers[q.id] === harf}
                        onChange={() => handleAnswer(q.id, harf)}
                        style={{ accentColor: 'var(--color-primary)' }}
                      />
                      <span><strong>{harf.toUpperCase()})</strong> {metin}</span>
                    </label>
                  ))}
                </div>
              </div>
            ))}
            <button
              className="btn btn-primary"
              disabled={!allAnswered || submitting}
              onClick={submitQuiz}
            >
              {submitting ? 'Gönderiliyor…' : 'Tamamla'}
            </button>
          </div>
        )}

        {result && (
          <div>
            <div
              style={{
                padding: '1rem',
                borderRadius: '10px',
                background: result.gecti ? 'rgba(0,200,150,0.1)' : 'rgba(255,60,60,0.1)',
                border: `1.5px solid ${result.gecti ? '#00c8a0' : '#ff3c3c'}`,
                marginBottom: '1rem',
              }}
            >
              <strong style={{ fontSize: '1.1rem' }}>
                {result.gecti ? '✅ Geçtiniz!' : '❌ Tekrar Deneyin'}
              </strong>
              <p style={{ margin: '0.25rem 0 0' }}>
                {result.dogru}/{result.toplam} doğru
              </p>
            </div>

            {result.sorular.map((s, i) => (
              <div key={i} style={{ marginBottom: '0.75rem', padding: '0.5rem', borderRadius: '8px', background: 'var(--color-surface)' }}>
                <p style={{ margin: 0, fontWeight: 500 }}>{i + 1}. {s.soru_metni}</p>
                <p style={{ margin: '0.25rem 0 0', fontSize: '0.875rem', color: s.dogru_mu ? '#00c8a0' : 'var(--color-danger)' }}>
                  {s.dogru_mu ? '✓' : '✗'} Seçiminiz: {s.secilen.toUpperCase()} | Doğru: {s.dogru_harf.toUpperCase()}
                </p>
                {s.aciklama && (
                  <p style={{ margin: '0.25rem 0 0', fontSize: '0.8rem', color: 'var(--color-text-secondary)' }}>
                    {s.aciklama}
                  </p>
                )}
              </div>
            ))}

            {!result.gecti && (
              <button className="btn btn-secondary" onClick={startQuiz}>
                Tekrar Dene
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

// ─── LessonPage ───────────────────────────────────────────────────────────────

export default function LessonPage() {
  const { slug } = useParams<{ slug: string }>()
  const navigate = useNavigate()

  const [lesson, setLesson] = useState<AcademyLessonOut | null>(null)
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [yuzde, setYuzde] = useState(0)
  const [tamamlandi, setTamamlandi] = useState(false)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const handleProgress = useCallback((newYuzde: number) => {
    setYuzde((prev) => Math.max(prev, newYuzde))
  }, [])

  useHeartbeat(sessionId, handleProgress)

  useEffect(() => {
    if (!slug) return

    const init = async () => {
      try {
        const les = await academyApi.getLesson(slug)
        setLesson(les)

        // Progress mevcut mu kontrol et
        try {
          const prog = await academyApi.getProgress(les.id)
          setYuzde(prog.yuzde)
          setTamamlandi(prog.tamamlandi)
        } catch {
          // Henüz progress yok — normal
        }

        // Session başlat
        const sess = await academyApi.startSession(les.id)
        setSessionId(sess.id)
      } catch {
        setError('Ders yüklenemedi.')
      } finally {
        setLoading(false)
      }
    }

    init()
  }, [slug])

  // knot_animation adımı var mı?
  const knotStep = lesson?.steps.find((s) => s.step_type === 'knot_animation')
  const knotData = knotStep?.data_json as { slug?: string; timeline_url?: string } | undefined

  return (
    <AppShell title={lesson?.title ?? 'Ders'}>
      <div className="page-header">
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <button className="btn btn-ghost btn-sm" onClick={() => navigate(-1)}>
            ← Geri
          </button>
          <h1 className="page-title" style={{ margin: 0 }}>{lesson?.title ?? '…'}</h1>
          {tamamlandi && (
            <span className="badge badge-success" style={{ marginLeft: '0.5rem' }}>Tamamlandı ✓</span>
          )}
        </div>
      </div>

      {error && <div className="alert alert-error" style={{ marginBottom: '1rem' }}>{error}</div>}

      {loading ? (
        <div style={{ display: 'flex', justifyContent: 'center', padding: '3rem' }}>
          <span className="loading-spinner lg" />
        </div>
      ) : lesson ? (
        <>
          {/* İlerleme çubuğu */}
          <div style={{ marginBottom: '1.5rem' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.25rem', fontSize: '0.875rem', color: 'var(--color-text-secondary)' }}>
              <span>İlerleme</span>
              <span>%{yuzde}</span>
            </div>
            <div style={{ height: 8, background: 'var(--color-border)', borderRadius: 4, overflow: 'hidden' }}>
              <div
                style={{
                  height: '100%',
                  width: `${yuzde}%`,
                  background: tamamlandi ? '#00c8a0' : 'var(--color-primary)',
                  transition: 'width 0.5s ease',
                  borderRadius: 4,
                }}
              />
            </div>
          </div>

          {/* KnotPlayer embed */}
          {knotData?.slug && (
            <KnotPlayerEmbed
              knotSlug={knotData.slug}
              timelineUrl={knotData.timeline_url ?? ''}
            />
          )}

          {/* Metin adımları */}
          {lesson.steps
            .filter((s) => s.step_type !== 'knot_animation')
            .map((step) => (
              <div key={step.id} className="card" style={{ marginBottom: '1rem' }}>
                <div className="card-body">
                  {step.baslik && <h4 style={{ marginBottom: '0.5rem' }}>{step.baslik}</h4>}
                  <pre style={{ whiteSpace: 'pre-wrap', fontSize: '0.875rem', color: 'var(--color-text-secondary)', margin: 0 }}>
                    {JSON.stringify(step.data_json, null, 2)}
                  </pre>
                </div>
              </div>
            ))}

          {/* Quiz */}
          {lesson.quiz_questions.length > 0 && (
            <QuizSection
              lessonId={lesson.id}
              questions={lesson.quiz_questions}
              onPass={() => {
                setTamamlandi(true)
                setYuzde(100)
              }}
            />
          )}
        </>
      ) : null}
    </AppShell>
  )
}
