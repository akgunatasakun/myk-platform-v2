/**
 * /yoklama — Oturum yoklama ekranı
 *
 * URL: /yoklama?course=<courseId>&session=<sessionId>
 * Oturum detay sayfasından "✅ Yoklama" butonuyla yönlendirilir.
 * Bu sayfada da kurs/oturum manuel seçilebilir.
 *
 * P0-1 fix:
 *  - Backend artık sadece aktif kayıtları döndürüyor (status='active' filtresi)
 *  - Frontend JS filtresi korundu (savunma amaçlı ikinci kat)
 *  - Kurs/oturum yükleme hataları kullanıcıya gösteriliyor
 */
import { useCallback, useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import AppShell from '@/components/layout/AppShell'
import { trainingApi } from '@/api/training'
import type {
  TrainingCourse,
  TrainingSession,
  TrainingEnrollment,
  TrainingAttendance,
  AttendanceStatus,
} from '@/types/training'

const STATUS_BUTTONS: { value: AttendanceStatus; label: string; color: string }[] = [
  { value: 'var', label: 'Var', color: 'var(--color-success)' },
  { value: 'yok', label: 'Yok', color: 'var(--color-danger)' },
  { value: 'izinli', label: 'İzinli', color: 'var(--color-warning)' },
  { value: 'gecikti', label: 'Geç', color: 'var(--color-text-muted)' },
]

interface AttendanceRow {
  person_id: string
  person_name: string
  status: AttendanceStatus | null
  check_in_time: string
  check_out_time: string
  notes: string
}

function fmt(date: string) {
  return new Date(date + 'T00:00:00').toLocaleDateString('tr-TR')
}

export default function AttendancePage() {
  const [searchParams, setSearchParams] = useSearchParams()

  // Seçimler
  const [courses, setCourses] = useState<TrainingCourse[]>([])
  const [sessions, setSessions] = useState<TrainingSession[]>([])
  const [selectedCourseId, setSelectedCourseId] = useState(searchParams.get('course') ?? '')
  const [selectedSessionId, setSelectedSessionId] = useState(searchParams.get('session') ?? '')

  // Yoklama verileri
  const [rows, setRows] = useState<AttendanceRow[]>([])
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [saveResult, setSaveResult] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  // P0-1 fix: kurs/oturum yükleme hataları için ayrı state
  const [courseLoadError, setCourseLoadError] = useState<string | null>(null)
  const [sessionLoadError, setSessionLoadError] = useState<string | null>(null)

  // Kurs listesi yükle (aktif)
  useEffect(() => {
    setCourseLoadError(null)
    trainingApi.listCourses({ active_only: false, limit: 100 })
      .then((r) => setCourses(r.data.items))
      .catch(() => {
        // P0-1 fix: hata sessizce yutulmuyordu; kullanıcıya göster
        setCourseLoadError('Eğitim listesi yüklenemedi. Sayfayı yenileyin.')
      })
  }, [])

  // Kurs değişince oturum listesi yükle
  useEffect(() => {
    if (!selectedCourseId) { setSessions([]); setSelectedSessionId(''); return }
    setSessionLoadError(null)
    trainingApi.listSessions(selectedCourseId)
      .then((r) => setSessions(r.data))
      .catch(() => {
        setSessions([])
        setSessionLoadError('Oturum listesi yüklenemedi.')
      })
  }, [selectedCourseId])

  // Oturum seçince katılımcı + mevcut yoklama yükle
  const loadAttendance = useCallback(async () => {
    if (!selectedCourseId || !selectedSessionId) return
    setLoading(true)
    setError(null)
    setSaveResult(null)
    try {
      const [enrollResp, attResp] = await Promise.all([
        trainingApi.listParticipants(selectedCourseId),
        trainingApi.getAttendance(selectedCourseId, selectedSessionId),
      ])

      // P0-1: Backend artık sadece aktif kayıtları döndürüyor.
      // Frontend filtresi savunma amaçlı korunuyor.
      const activeEnrollments: TrainingEnrollment[] = enrollResp.data.filter(
        (e) => e.status === 'active'
      )
      const attMap = new Map<string, TrainingAttendance>(
        attResp.data.map((a) => [a.person_id, a])
      )

      setRows(
        activeEnrollments.map((e) => {
          const existing = attMap.get(e.person_id)
          return {
            person_id: e.person_id,
            person_name: e.person_name ?? e.person_id,
            status: (existing?.status as AttendanceStatus) ?? null,
            check_in_time: existing?.check_in_time?.slice(0, 5) ?? '',
            check_out_time: existing?.check_out_time?.slice(0, 5) ?? '',
            notes: existing?.notes ?? '',
          }
        })
      )
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      setError(detail ?? 'Yoklama verileri yüklenemedi.')
    } finally {
      setLoading(false)
    }
  }, [selectedCourseId, selectedSessionId])

  useEffect(() => {
    loadAttendance()
  }, [loadAttendance])

  // URL'yi sync et
  useEffect(() => {
    const params: Record<string, string> = {}
    if (selectedCourseId) params.course = selectedCourseId
    if (selectedSessionId) params.session = selectedSessionId
    setSearchParams(params, { replace: true })
  }, [selectedCourseId, selectedSessionId])

  const setRowStatus = (personId: string, status: AttendanceStatus) => {
    setRows((prev) =>
      prev.map((r) => (r.person_id === personId ? { ...r, status } : r))
    )
  }

  const setRowField = (personId: string, field: 'check_in_time' | 'check_out_time' | 'notes', value: string) => {
    setRows((prev) =>
      prev.map((r) => (r.person_id === personId ? { ...r, [field]: value } : r))
    )
  }

  const setAll = (status: AttendanceStatus) => {
    setRows((prev) => prev.map((r) => ({ ...r, status })))
  }

  const handleSave = async () => {
    if (!selectedCourseId || !selectedSessionId) return
    const filled = rows.filter((r) => r.status !== null)
    if (filled.length === 0) { setSaveResult('Hiçbir yoklama durumu seçilmedi.'); return }

    setSaving(true)
    setSaveResult(null)
    setError(null)
    try {
      const resp = await trainingApi.bulkUpdateAttendance(selectedCourseId, selectedSessionId, {
        records: filled.map((r) => ({
          person_id: r.person_id,
          status: r.status as AttendanceStatus,
          check_in_time: r.check_in_time || null,
          check_out_time: r.check_out_time || null,
          notes: r.notes || null,
        })),
      })
      const { created, updated } = resp.data
      setSaveResult(
        `Kaydedildi — ${created > 0 ? `${created} yeni` : ''}${created > 0 && updated > 0 ? ', ' : ''}${updated > 0 ? `${updated} güncellendi` : ''}`
      )
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      setError(detail ?? 'Kayıt sırasında hata oluştu.')
    } finally {
      setSaving(false)
    }
  }

  const selectedSession = sessions.find((s) => s.id === selectedSessionId)
  const selectedCourse = courses.find((c) => c.id === selectedCourseId)

  return (
    <AppShell title="Yoklama">
      <div className="page-header">
        <h1 className="page-title">Yoklama</h1>
      </div>

      {/* P0-1 fix: kurs yükleme hatası */}
      {courseLoadError && (
        <div className="alert alert-error" style={{ marginBottom: 16 }}>
          <span>⚠️</span><span>{courseLoadError}</span>
        </div>
      )}

      {/* Kurs / Oturum seçici */}
      <div style={{ display: 'flex', gap: 12, marginBottom: 20, flexWrap: 'wrap' }}>
        <div className="form-group" style={{ margin: 0, minWidth: 260, flex: 1 }}>
          <label className="form-label">Eğitim</label>
          <select
            className="form-select"
            value={selectedCourseId}
            onChange={(e) => { setSelectedCourseId(e.target.value); setSelectedSessionId('') }}
          >
            <option value="">— Eğitim seçiniz —</option>
            {courses.map((c) => (
              <option key={c.id} value={c.id}>{c.name}{c.class_name ? ` — ${c.class_name}` : ''}</option>
            ))}
          </select>
        </div>

        <div className="form-group" style={{ margin: 0, minWidth: 220, flex: 1 }}>
          <label className="form-label">Oturum</label>
          <select
            className="form-select"
            value={selectedSessionId}
            onChange={(e) => setSelectedSessionId(e.target.value)}
            disabled={!selectedCourseId}
          >
            <option value="">— Oturum seçiniz —</option>
            {sessions.map((s) => (
              <option key={s.id} value={s.id}>
                {fmt(s.session_date)}
                {s.start_time ? ` ${s.start_time.slice(0, 5)}` : ''}
                {s.status !== 'planli' ? ` (${s.status})` : ''}
              </option>
            ))}
          </select>
          {/* P0-1 fix: oturum yükleme hatası */}
          {sessionLoadError && (
            <div style={{ color: 'var(--color-danger)', fontSize: 12, marginTop: 4 }}>
              {sessionLoadError}
            </div>
          )}
          {/* Seçili kurs varsa ama oturum yoksa yönlendirici mesaj */}
          {selectedCourseId && !sessionLoadError && sessions.length === 0 && (
            <div style={{ fontSize: 12, marginTop: 6, color: 'var(--color-text-muted)' }}>
              Bu eğitimde henüz oturum yok.{' '}
              <a href={`/egitimler/${selectedCourseId}`} style={{ color: 'var(--color-primary)' }}>
                Eğitim sayfasından oturum ekleyin →
              </a>
            </div>
          )}
        </div>
      </div>

      {/* İçerik */}
      {!selectedCourseId || !selectedSessionId ? (
        <div className="empty-state">
          <div className="empty-state-icon">✅</div>
          <div className="empty-state-title">Yoklama Almak İçin Seçin</div>
          <div className="empty-state-desc">Eğitim ve oturum seçerek yoklama formunu açın.</div>
        </div>
      ) : loading ? (
        <div className="loading-center"><span className="loading-spinner lg" /></div>
      ) : error ? (
        <div className="alert alert-error"><span>⚠️</span><span>{error}</span></div>
      ) : rows.length === 0 ? (
        <div className="empty-state">
          <div className="empty-state-icon">👥</div>
          <div className="empty-state-title">Aktif Katılımcı Yok</div>
          <div className="empty-state-desc">Bu eğitime kayıtlı aktif katılımcı bulunmuyor.</div>
        </div>
      ) : (
        <>
          {/* Başlık + toplu işlem */}
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12, flexWrap: 'wrap', gap: 8 }}>
            <div style={{ fontSize: 14, color: 'var(--color-text-muted)' }}>
              <strong>{selectedCourse?.name}</strong>
              {selectedSession && ` — ${fmt(selectedSession.session_date)}`}
              {selectedSession?.start_time && ` ${selectedSession.start_time.slice(0, 5)}`}
              {' '}· {rows.length} katılımcı
            </div>
            <div style={{ display: 'flex', gap: 6 }}>
              <span style={{ fontSize: 12, alignSelf: 'center', color: 'var(--color-text-muted)' }}>Tümünü:</span>
              {STATUS_BUTTONS.map((b) => (
                <button
                  key={b.value}
                  className="btn btn-sm btn-ghost"
                  style={{ border: `1px solid ${b.color}`, color: b.color, minWidth: 52 }}
                  onClick={() => setAll(b.value)}
                >
                  {b.label}
                </button>
              ))}
            </div>
          </div>

          {/* Yoklama tablosu */}
          <div className="table-container" style={{ marginBottom: 16 }}>
            <table className="data-table">
              <thead>
                <tr>
                  <th>#</th>
                  <th>Katılımcı</th>
                  <th>Durum</th>
                  <th>Giriş</th>
                  <th>Çıkış</th>
                  <th>Not</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row, idx) => (
                  <tr key={row.person_id}>
                    <td style={{ color: 'var(--color-text-muted)', width: 36 }}>{idx + 1}</td>
                    <td><strong>{row.person_name}</strong></td>
                    <td>
                      <div style={{ display: 'flex', gap: 4 }}>
                        {STATUS_BUTTONS.map((b) => (
                          <button
                            key={b.value}
                            className="btn btn-sm"
                            style={{
                              minWidth: 46,
                              background: row.status === b.value ? b.color : 'transparent',
                              color: row.status === b.value ? '#fff' : b.color,
                              border: `1.5px solid ${b.color}`,
                              fontWeight: row.status === b.value ? 700 : 400,
                            }}
                            onClick={() => setRowStatus(row.person_id, b.value)}
                          >
                            {b.label}
                          </button>
                        ))}
                      </div>
                    </td>
                    <td>
                      <input
                        type="time"
                        className="form-input"
                        style={{ width: 100, padding: '4px 6px', fontSize: 13 }}
                        value={row.check_in_time}
                        onChange={(e) => setRowField(row.person_id, 'check_in_time', e.target.value)}
                      />
                    </td>
                    <td>
                      <input
                        type="time"
                        className="form-input"
                        style={{ width: 100, padding: '4px 6px', fontSize: 13 }}
                        value={row.check_out_time}
                        onChange={(e) => setRowField(row.person_id, 'check_out_time', e.target.value)}
                      />
                    </td>
                    <td>
                      <input
                        className="form-input"
                        style={{ width: 140, padding: '4px 6px', fontSize: 13 }}
                        value={row.notes}
                        onChange={(e) => setRowField(row.person_id, 'notes', e.target.value)}
                        placeholder="opsiyonel"
                      />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Kaydet */}
          {saveResult && !error && (
            <div className="alert alert-success" style={{ marginBottom: 12 }}>
              <span>✅</span><span>{saveResult}</span>
            </div>
          )}
          {error && (
            <div className="alert alert-error" style={{ marginBottom: 12 }}>
              <span>⚠️</span><span>{error}</span>
            </div>
          )}

          <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
            <button className="btn btn-primary" onClick={handleSave} disabled={saving}>
              {saving ? 'Kaydediliyor…' : '💾 Yoklamayı Kaydet'}
            </button>
          </div>
        </>
      )}
    </AppShell>
  )
}
