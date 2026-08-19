import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import AppShell from '@/components/layout/AppShell'
import TrainingFormModal from './TrainingFormModal'
import SessionFormModal from './SessionFormModal'
import { trainingApi } from '@/api/training'
import { personsApi } from '@/api/persons'
import { PERSON_LIST_LIMIT } from '@/api/constants'
import type {
  TrainingCourse,
  TrainingEnrollment,
  TrainingSession,
  AttendanceReport,
  SessionStatus,
} from '@/types/training'
import type { Person } from '@/types/person'

// ── Sabitler ──────────────────────────────────────────────────────────────────

const COURSE_STATUS_LABEL: Record<string, string> = {
  planlandi: 'Planlandı',
  aktif: 'Aktif',
  tamamlandi: 'Tamamlandı',
  iptal: 'İptal',
}

const COURSE_STATUS_CLASS: Record<string, string> = {
  planlandi: 'badge-planlandi',
  aktif: 'badge-aktif',
  tamamlandi: 'badge-tamamlandi',
  iptal: 'badge-iptal',
}

const SESSION_STATUS_LABEL: Record<SessionStatus, string> = {
  planli: 'Planlı',
  tamamlandi: 'Tamamlandı',
  iptal: 'İptal',
}

const SESSION_STATUS_CLASS: Record<SessionStatus, string> = {
  planli: 'badge-planlandi',
  tamamlandi: 'badge-aktif',
  iptal: 'badge-iptal',
}

const ENROLL_STATUS_LABEL: Record<string, string> = {
  active: 'Aktif',
  cancelled: 'İptal',
  completed: 'Tamamlandı',
}

const PAYMENT_STATUS_LABEL: Record<string, string> = {
  pending: 'Bekliyor',
  paid: 'Ödendi',
  overdue: 'Gecikti',
}

const PAYMENT_STATUS_CLASS: Record<string, string> = {
  pending: 'badge-planlandi',
  paid: 'badge-aktif',
  overdue: 'badge-hasarli',
}

function fmt(date: string | null | undefined) {
  if (!date) return '—'
  return new Date(date + 'T00:00:00').toLocaleDateString('tr-TR')
}

function fmtTime(t: string | null) {
  if (!t) return null
  return t.slice(0, 5) // HH:MM
}

function fmtFee(fee: string) {
  const n = parseFloat(fee)
  if (!n) return 'Ücretsiz'
  return `${n.toLocaleString('tr-TR', { minimumFractionDigits: 0 })} ₺`
}

// ── Tip ───────────────────────────────────────────────────────────────────────

type Tab = 'participants' | 'sessions' | 'report'

// ── Component ─────────────────────────────────────────────────────────────────

export default function TrainingDetailPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()

  const [course, setCourse] = useState<TrainingCourse | null>(null)
  const [enrollments, setEnrollments] = useState<TrainingEnrollment[]>([])
  const [sessions, setSessions] = useState<TrainingSession[]>([])
  const [report, setReport] = useState<AttendanceReport | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const [tab, setTab] = useState<Tab>('sessions')

  const [editOpen, setEditOpen] = useState(false)
  const [sessionModalOpen, setSessionModalOpen] = useState(false)
  const [editSession, setEditSession] = useState<TrainingSession | undefined>(undefined)

  // Katılımcı ekleme
  const [persons, setPersons] = useState<Person[]>([])
  const [addPersonId, setAddPersonId] = useState('')
  const [addNotes, setAddNotes] = useState('')
  const [addError, setAddError] = useState<string | null>(null)
  const [adding, setAdding] = useState(false)

  const load = async () => {
    if (!id) return
    setLoading(true)
    setError(null)
    try {
      const [cResp, eResp, sResp] = await Promise.all([
        trainingApi.getCourse(id),
        trainingApi.listParticipants(id),
        trainingApi.listSessions(id),
      ])
      setCourse(cResp.data)
      setEnrollments(eResp.data)
      setSessions(sResp.data)
    } catch {
      setError('Eğitim yüklenemedi.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [id])

  useEffect(() => {
    personsApi.list({ limit: PERSON_LIST_LIMIT, is_active: true })
      .then((r) => setPersons(r.data.items))
      .catch((err) => console.error('[TrainingDetailPage] kişi listesi alınamadı:', err))
  }, [])

  const loadReport = async () => {
    if (!id || report) return
    try {
      const r = await trainingApi.getAttendanceReport(id)
      setReport(r.data)
    } catch {
      setReport({ course_id: id, course_name: course?.name ?? '', toplam_oturum: 0, katilimcilar: [] })
    }
  }

  useEffect(() => {
    if (tab === 'report') loadReport()
  }, [tab])

  const handleDelete = async () => {
    if (!course) return
    if (!window.confirm(`"${course.name}" eğitimini silmek istiyor musunuz?`)) return
    try {
      await trainingApi.deleteCourse(course.id)
      navigate('/egitimler')
    } catch {
      alert('Silme işlemi sırasında hata oluştu.')
    }
  }

  const handleAddParticipant = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!id || !addPersonId) { setAddError('Kişi seçiniz.'); return }
    setAdding(true)
    setAddError(null)
    try {
      const resp = await trainingApi.addParticipant(id, {
        person_id: addPersonId,
        notes: addNotes || null,
      })
      setEnrollments((prev) => [...prev, resp.data])
      setAddPersonId('')
      setAddNotes('')
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      setAddError(msg ?? 'Kayıt eklenemedi.')
    } finally {
      setAdding(false)
    }
  }

  const handleRemoveParticipant = async (enr: TrainingEnrollment) => {
    if (!id) return
    if (!window.confirm(`"${enr.person_name ?? enr.person_id}" kişiyi kurs kaydını iptal etmek istiyor musunuz?`)) return
    try {
      await trainingApi.removeParticipant(id, enr.person_id)
      setEnrollments((prev) => prev.filter((e) => e.id !== enr.id))
    } catch {
      alert('İşlem sırasında hata oluştu.')
    }
  }

  const openNewSession = () => { setEditSession(undefined); setSessionModalOpen(true) }
  const openEditSession = (s: TrainingSession) => { setEditSession(s); setSessionModalOpen(true) }

  if (loading) {
    return (
      <AppShell title="Eğitim Detayı">
        <div className="loading-center"><span className="loading-spinner lg" /></div>
      </AppShell>
    )
  }

  if (error || !course) {
    return (
      <AppShell title="Eğitim Detayı">
        <div className="alert alert-error"><span>⚠️</span><span>{error ?? 'Eğitim bulunamadı.'}</span></div>
      </AppShell>
    )
  }

  const activeEnrollments = enrollments.filter((e) => e.status === 'active')

  return (
    <AppShell title={course.name}>
      {/* Üst bar */}
      <div className="page-header">
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <button className="btn btn-ghost btn-sm" onClick={() => navigate('/egitimler')}>
            ← Geri
          </button>
          <h1 className="page-title" style={{ margin: 0 }}>{course.name}</h1>
          <span className={`badge ${COURSE_STATUS_CLASS[course.status] ?? ''}`}>
            {COURSE_STATUS_LABEL[course.status] ?? course.status}
          </span>
          {!course.is_active && <span className="badge badge-pasif">Pasif</span>}
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <button className="btn btn-secondary" onClick={() => setEditOpen(true)}>Düzenle</button>
          <button className="btn btn-danger" onClick={handleDelete}>Sil</button>
        </div>
      </div>

      {/* Kurs bilgileri */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))', gap: 16, marginBottom: 24 }}>
        <div className="card">
          <div className="card-header"><div className="card-title">📅 Genel Bilgiler</div></div>
          <div className="card-body">
            <Row label="Sınıf" value={course.class_name} />
            <Row label="Seviye" value={course.level} />
            <Row label="Program" value={course.schedule_text} />
            <Row
              label="Eğitmen"
              value={
                course.instructors && course.instructors.length > 0
                  ? course.instructors.map((i) => i.name).join(', ')
                  : (course.instructor_name ?? '—')
              }
            />
          </div>
        </div>
        <div className="card">
          <div className="card-header"><div className="card-title">📆 Tarih & Kontenjan</div></div>
          <div className="card-body">
            <Row label="Başlangıç" value={fmt(course.start_date)} />
            <Row label="Bitiş" value={fmt(course.end_date)} />
            <Row
              label="Kontenjan"
              value={course.capacity > 0 ? `${activeEnrollments.length} / ${course.capacity}` : `${activeEnrollments.length} (sınırsız)`}
            />
            <Row label="Ücret" value={fmtFee(course.fee)} />
          </div>
        </div>
        {course.description && (
          <div className="card">
            <div className="card-header"><div className="card-title">📝 Açıklama</div></div>
            <div className="card-body">
              <p style={{ margin: 0, whiteSpace: 'pre-wrap', fontSize: 13 }}>{course.description}</p>
            </div>
          </div>
        )}
      </div>

      {/* Tabs */}
      <div style={{ display: 'flex', gap: 8, marginBottom: 16, borderBottom: '2px solid var(--color-border)', paddingBottom: 0 }}>
        {([
          { key: 'sessions', label: `Oturumlar (${sessions.length})` },
          { key: 'participants', label: `Katılımcılar (${activeEnrollments.length})` },
          { key: 'report', label: 'Devam Raporu' },
        ] as { key: Tab; label: string }[]).map((t) => (
          <button
            key={t.key}
            className={`btn btn-sm ${tab === t.key ? 'btn-primary' : 'btn-ghost'}`}
            style={{ borderRadius: '4px 4px 0 0' }}
            onClick={() => setTab(t.key)}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* Sessions tab */}
      {tab === 'sessions' && (
        <>
          <div className="page-header" style={{ marginBottom: 12 }}>
            <span />
            <button className="btn btn-primary btn-sm" onClick={openNewSession}>+ Yeni Oturum</button>
          </div>
          <div className="table-container">
            {sessions.length === 0 ? (
              <div className="empty-state">
                <div className="empty-state-icon">📅</div>
                <div className="empty-state-title">Oturum Yok</div>
                <div className="empty-state-desc">Bu eğitim için henüz oturum eklenmemiş.</div>
              </div>
            ) : (
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Tarih</th>
                    <th>Saat</th>
                    <th>Durum</th>
                    <th>Yoklama</th>
                    <th>Notlar</th>
                    <th>İşlemler</th>
                  </tr>
                </thead>
                <tbody>
                  {sessions.map((s) => (
                    <tr key={s.id}>
                      <td>{fmt(s.session_date)}</td>
                      <td>
                        {fmtTime(s.start_time)
                          ? `${fmtTime(s.start_time)}${s.end_time ? ` – ${fmtTime(s.end_time)}` : ''}`
                          : '—'}
                      </td>
                      <td>
                        <span className={`badge ${SESSION_STATUS_CLASS[s.status] ?? ''}`}>
                          {SESSION_STATUS_LABEL[s.status] ?? s.status}
                        </span>
                      </td>
                      <td>{s.attendance_count} kişi</td>
                      <td style={{ fontSize: 12, maxWidth: 180, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                        {s.notes ?? '—'}
                      </td>
                      <td>
                        <div style={{ display: 'flex', gap: 6 }}>
                          <button
                            className="btn btn-sm btn-primary"
                            onClick={() => navigate(`/yoklama?course=${course.id}&session=${s.id}`)}
                          >
                            ✅ Yoklama
                          </button>
                          <button className="btn btn-sm btn-secondary" onClick={() => openEditSession(s)}>
                            Düzenle
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </>
      )}

      {/* Participants tab */}
      {tab === 'participants' && (
        <>
          {/* Katılımcı ekle */}
          <form onSubmit={handleAddParticipant} style={{ display: 'flex', gap: 8, marginBottom: 16, alignItems: 'flex-end' }}>
            <div className="form-group" style={{ margin: 0, flex: 2 }}>
              <label className="form-label">Katılımcı Ekle</label>
              <select
                className="form-select"
                value={addPersonId}
                onChange={(e) => setAddPersonId(e.target.value)}
              >
                <option value="">— Kişi seçiniz —</option>
                {persons
                  .filter((p) => !enrollments.some((e) => e.person_id === p.id && e.status === 'active'))
                  .map((p) => (
                    <option key={p.id} value={p.id}>{p.first_name} {p.last_name}</option>
                  ))}
              </select>
            </div>
            <div className="form-group" style={{ margin: 0, flex: 1 }}>
              <label className="form-label">Not</label>
              <input
                className="form-input"
                value={addNotes}
                onChange={(e) => setAddNotes(e.target.value)}
                placeholder="opsiyonel"
              />
            </div>
            <button type="submit" className="btn btn-primary" disabled={adding} style={{ flexShrink: 0 }}>
              {adding ? '…' : '+ Ekle'}
            </button>
          </form>
          {addError && (
            <div className="alert alert-error" style={{ marginBottom: 12 }}>
              <span>⚠️</span><span>{addError}</span>
            </div>
          )}

          <div className="table-container">
            {enrollments.length === 0 ? (
              <div className="empty-state">
                <div className="empty-state-icon">👥</div>
                <div className="empty-state-title">Katılımcı Yok</div>
                <div className="empty-state-desc">Bu eğitime henüz kayıt yapılmamış.</div>
              </div>
            ) : (
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Kişi</th>
                    <th>Kayıt Durumu</th>
                    <th>Ödeme</th>
                    <th>Kayıt Tarihi</th>
                    <th>Notlar</th>
                    <th>İşlem</th>
                  </tr>
                </thead>
                <tbody>
                  {enrollments.map((e) => (
                    <tr key={e.id} style={{ opacity: e.status !== 'active' ? 0.6 : 1 }}>
                      <td><strong>{e.person_name ?? e.person_id}</strong></td>
                      <td>
                        <span className={`badge ${e.status === 'active' ? 'badge-aktif' : 'badge-iptal'}`}>
                          {ENROLL_STATUS_LABEL[e.status] ?? e.status}
                        </span>
                      </td>
                      <td>
                        <span className={`badge ${PAYMENT_STATUS_CLASS[e.payment_status] ?? ''}`}>
                          {PAYMENT_STATUS_LABEL[e.payment_status] ?? e.payment_status}
                        </span>
                      </td>
                      <td>{new Date(e.enrolled_at).toLocaleDateString('tr-TR')}</td>
                      <td style={{ fontSize: 12 }}>{e.notes ?? '—'}</td>
                      <td>
                        {e.status === 'active' && (
                          <button
                            className="btn btn-sm btn-danger"
                            onClick={() => handleRemoveParticipant(e)}
                          >
                            İptal
                          </button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </>
      )}

      {/* Report tab */}
      {tab === 'report' && (
        <div className="table-container">
          {!report ? (
            <div className="loading-center"><span className="loading-spinner lg" /></div>
          ) : report.katilimcilar.length === 0 ? (
            <div className="empty-state">
              <div className="empty-state-icon">📊</div>
              <div className="empty-state-title">Yoklama Verisi Yok</div>
              <div className="empty-state-desc">
                Bu eğitim için henüz yoklama kaydı girilmemiş ({report.toplam_oturum} oturum var).
              </div>
            </div>
          ) : (
            <>
              <div style={{ marginBottom: 12, fontSize: 13, color: 'var(--color-text-muted)' }}>
                Toplam {report.toplam_oturum} oturum
              </div>
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Katılımcı</th>
                    <th style={{ textAlign: 'center' }}>Var</th>
                    <th style={{ textAlign: 'center' }}>Yok</th>
                    <th style={{ textAlign: 'center' }}>İzinli</th>
                    <th style={{ textAlign: 'center' }}>Geç</th>
                    <th style={{ textAlign: 'center' }}>Devam %</th>
                  </tr>
                </thead>
                <tbody>
                  {report.katilimcilar.map((k) => (
                    <tr key={k.person_id.toString()}>
                      <td><strong>{k.person_name}</strong></td>
                      <td style={{ textAlign: 'center' }}>
                        <span style={{ color: 'var(--color-success)', fontWeight: 600 }}>{k.var}</span>
                      </td>
                      <td style={{ textAlign: 'center' }}>
                        <span style={{ color: 'var(--color-danger)' }}>{k.yok}</span>
                      </td>
                      <td style={{ textAlign: 'center' }}>
                        <span style={{ color: 'var(--color-warning)' }}>{k.izinli}</span>
                      </td>
                      <td style={{ textAlign: 'center' }}>
                        <span style={{ color: 'var(--color-text-muted)' }}>{k.gecikti}</span>
                      </td>
                      <td style={{ textAlign: 'center' }}>
                        <span style={{
                          fontWeight: 600,
                          color: k.devam_yuzdesi >= 75
                            ? 'var(--color-success)'
                            : k.devam_yuzdesi >= 50
                            ? 'var(--color-warning)'
                            : 'var(--color-danger)',
                        }}>
                          %{k.devam_yuzdesi.toFixed(1)}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </>
          )}
        </div>
      )}

      <TrainingFormModal
        isOpen={editOpen}
        onClose={() => setEditOpen(false)}
        course={course}
        onSaved={(saved) => setCourse(saved)}
      />

      <SessionFormModal
        isOpen={sessionModalOpen}
        onClose={() => setSessionModalOpen(false)}
        courseId={course.id}
        session={editSession}
        onSaved={(saved) => {
          setSessions((prev) => {
            const exists = prev.some((s) => s.id === saved.id)
            if (exists) return prev.map((s) => (s.id === saved.id ? saved : s))
            return [...prev, saved].sort((a, b) =>
              a.session_date.localeCompare(b.session_date)
            )
          })
        }}
      />
    </AppShell>
  )
}

function Row({ label, value }: { label: string; value: string | null | undefined }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', padding: '6px 0', borderBottom: '1px solid var(--color-border)' }}>
      <span style={{ color: 'var(--color-text-muted)', fontSize: 13 }}>{label}</span>
      <span style={{ fontWeight: 500, fontSize: 13 }}>{value || '—'}</span>
    </div>
  )
}
