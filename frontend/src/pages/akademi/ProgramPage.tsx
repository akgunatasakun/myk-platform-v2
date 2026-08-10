import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import AppShell from '@/components/layout/AppShell'
import { academyApi } from '@/api/academy'
import type { AcademyProgramOut, EnrollmentOut } from '@/types/academy'

export default function ProgramPage() {
  const { slug } = useParams<{ slug: string }>()
  const navigate = useNavigate()
  const [program, setProgram] = useState<AcademyProgramOut | null>(null)
  const [enrollments, setEnrollments] = useState<EnrollmentOut[]>([])
  const [loading, setLoading] = useState(true)
  const [enrolling, setEnrolling] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!slug) return
    Promise.all([academyApi.getProgram(slug), academyApi.myEnrollments()])
      .then(([prog, enrs]) => {
        setProgram(prog)
        setEnrollments(enrs)
      })
      .catch(() => setError('Program yüklenemedi.'))
      .finally(() => setLoading(false))
  }, [slug])

  const isEnrolled = program ? enrollments.some((e) => e.program_id === program.id) : false

  const handleEnroll = async () => {
    if (!program) return
    setEnrolling(true)
    try {
      const enr = await academyApi.enroll(program.id)
      setEnrollments((prev) => [...prev, enr])
    } catch {
      setError('Kayıt başarısız.')
    } finally {
      setEnrolling(false)
    }
  }

  return (
    <AppShell title={program?.ad ?? 'Program'}>
      <div className="page-header">
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <button className="btn btn-ghost btn-sm" onClick={() => navigate('/akademi')}>
            ← Geri
          </button>
          <h1 className="page-title" style={{ margin: 0 }}>{program?.ad ?? '…'}</h1>
        </div>
      </div>

      {error && <div className="alert alert-error" style={{ marginBottom: '1rem' }}>{error}</div>}

      {loading ? (
        <div style={{ display: 'flex', justifyContent: 'center', padding: '3rem' }}>
          <span className="loading-spinner lg" />
        </div>
      ) : program ? (
        <>
          {program.aciklama && (
            <p style={{ color: 'var(--color-text-secondary)', marginBottom: '1.5rem' }}>
              {program.aciklama}
            </p>
          )}

          {!isEnrolled && (
            <div className="card" style={{ marginBottom: '1.5rem' }}>
              <div className="card-body" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <span>Bu programa kayıtlı değilsiniz.</span>
                <button className="btn btn-primary" disabled={enrolling} onClick={handleEnroll}>
                  {enrolling ? 'Kaydediliyor…' : 'Kayıt Ol'}
                </button>
              </div>
            </div>
          )}

          {program.modules.map((mod) => (
            <div key={mod.id} className="card" style={{ marginBottom: '1rem' }}>
              <div className="card-body">
                <h3 className="card-title">{mod.ad}</h3>
                <ul style={{ listStyle: 'none', padding: 0, margin: 0 }}>
                  {mod.lessons.map((lesson) => (
                    <li key={lesson.id} style={{ padding: '0.5rem 0', borderBottom: '1px solid var(--color-border)' }}>
                      <Link
                        to={`/akademi/ders/${lesson.slug}`}
                        style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', textDecoration: 'none', color: 'var(--color-text)' }}
                      >
                        <span>🪢</span>
                        <span>{lesson.ad}</span>
                        {lesson.tahmini_sure_dk && (
                          <span style={{ marginLeft: 'auto', color: 'var(--color-text-secondary)', fontSize: '0.8rem' }}>
                            {lesson.tahmini_sure_dk} dk
                          </span>
                        )}
                      </Link>
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          ))}
        </>
      ) : null}
    </AppShell>
  )
}
