import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import AppShell from '@/components/layout/AppShell'
import { academyApi } from '@/api/academy'
import type { AcademyProgramListItem, EnrollmentOut } from '@/types/academy'

export default function AkademiPage() {
  const navigate = useNavigate()
  const [programs, setPrograms] = useState<AcademyProgramListItem[]>([])
  const [enrollments, setEnrollments] = useState<EnrollmentOut[]>([])
  const [loading, setLoading] = useState(true)
  const [enrolling, setEnrolling] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    Promise.allSettled([academyApi.listPrograms(), academyApi.myEnrollments()])
      .then(([progsResult, enrsResult]) => {
        if (progsResult.status === 'fulfilled') {
          setPrograms(progsResult.value)
        } else {
          setError('Programlar yüklenemedi.')
        }
        if (enrsResult.status === 'fulfilled') {
          setEnrollments(enrsResult.value)
        }
        // Kayıt listesi 403 dönse de (person kaydı olmayan yöneticiler) programlar gösterilir
      })
      .finally(() => setLoading(false))
  }, [])

  const enrolledProgramIds = new Set(enrollments.map((e) => e.program_id))

  const handleEnroll = async (program: AcademyProgramListItem) => {
    setEnrolling(program.id)
    try {
      const enr = await academyApi.enroll(program.id)
      setEnrollments((prev) => [...prev, enr])
    } catch {
      setError('Kayıt başarısız. Lütfen tekrar deneyin.')
    } finally {
      setEnrolling(null)
    }
  }

  const seviyeLabel: Record<number, string> = {
    1: 'Başlangıç',
    2: 'Orta',
    3: 'İleri',
  }

  return (
    <AppShell title="Deniz Akademisi">
      <div className="page-header">
        <h1 className="page-title">Deniz Akademisi</h1>
        <p className="page-subtitle">Yelkencilik eğitim programları</p>
      </div>

      {error && (
        <div className="alert alert-error" style={{ marginBottom: '1rem' }}>
          {error}
        </div>
      )}

      {loading ? (
        <div style={{ display: 'flex', justifyContent: 'center', padding: '3rem' }}>
          <span className="loading-spinner lg" />
        </div>
      ) : programs.length === 0 ? (
        <div className="empty-state">
          <div className="empty-state-icon">⚓</div>
          <h3>Henüz program yok</h3>
          <p>Yakında eğitim programları eklenecek.</p>
        </div>
      ) : (
        <div className="card-grid">
          {programs.map((program) => {
            const isEnrolled = enrolledProgramIds.has(program.id)
            return (
              <div key={program.id} className="card">
                <div className="card-body">
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '0.5rem' }}>
                    <h3 className="card-title" style={{ margin: 0 }}>{program.ad}</h3>
                    <span className="badge badge-info" style={{ flexShrink: 0, marginLeft: '0.5rem' }}>
                      {seviyeLabel[program.seviye] ?? `Seviye ${program.seviye}`}
                    </span>
                  </div>
                  <div style={{ display: 'flex', gap: '0.5rem', marginTop: 'auto' }}>
                    {isEnrolled ? (
                      <button
                        className="btn btn-primary"
                        onClick={() => navigate(`/akademi/program/${program.slug}`)}
                      >
                        Devam Et
                      </button>
                    ) : (
                      <>
                        <button
                          className="btn btn-secondary"
                          onClick={() => navigate(`/akademi/program/${program.slug}`)}
                        >
                          İncele
                        </button>
                        <button
                          className="btn btn-primary"
                          disabled={enrolling === program.id}
                          onClick={() => handleEnroll(program)}
                        >
                          {enrolling === program.id ? 'Kaydediliyor…' : 'Kayıt Ol'}
                        </button>
                      </>
                    )}
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      )}
    </AppShell>
  )
}
