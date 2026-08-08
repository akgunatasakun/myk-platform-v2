import { useEffect, useRef, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import AppShell from '@/components/layout/AppShell'
import { applicationsApi } from '@/api/applications'
import { personsApi } from '@/api/persons'
import type { MembershipApplication, ApplicationStatus } from '@/types/application'
import type { Person } from '@/types/person'

// ─── Durum meta ───────────────────────────────────────────────────────────────

const STATUS_META: Record<ApplicationStatus, { label: string; badgeClass: string }> = {
  draft:     { label: 'Taslak',     badgeClass: 'badge-status-draft'     },
  submitted: { label: 'Beklemede',  badgeClass: 'badge-status-submitted' },
  approved:  { label: 'Onaylandı',  badgeClass: 'badge-status-approved'  },
  rejected:  { label: 'Reddedildi', badgeClass: 'badge-status-rejected'  },
  cancelled: { label: 'İptal',      badgeClass: 'badge-status-cancelled' },
}

function StatusBadge({ status }: { status: ApplicationStatus }) {
  const meta = STATUS_META[status] ?? { label: status, badgeClass: 'badge-default' }
  return <span className={`badge ${meta.badgeClass}`}>{meta.label}</span>
}

// ─── Yardımcılar ──────────────────────────────────────────────────────────────

function fmt(iso: string | null | undefined): string {
  if (!iso) return '—'
  return new Date(iso).toLocaleString('tr-TR', {
    day: '2-digit', month: '2-digit', year: 'numeric',
    hour: '2-digit', minute: '2-digit',
  })
}

function fmtDate(iso: string | null | undefined): string {
  if (!iso) return '—'
  return new Date(iso).toLocaleDateString('tr-TR', {
    day: '2-digit', month: '2-digit', year: 'numeric',
  })
}

function DetailItem({ label, value }: { label: string; value?: string | null | React.ReactNode }) {
  return (
    <div className="detail-item">
      <span className="detail-label">{label}</span>
      <span className="detail-value">{value || '—'}</span>
    </div>
  )
}

function SectionCard({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="card" style={{ marginBottom: 16 }}>
      <div className="card-header">{title}</div>
      <div className="card-body">
        <div className="detail-grid">{children}</div>
      </div>
    </div>
  )
}

// ─── Onay/Red panel bileşeni ─────────────────────────────────────────────────

type ActionMode = 'idle' | 'confirm-approve' | 'reject-form'

interface ActionPanelProps {
  onApprove: () => Promise<void>
  onReject: (reason: string) => Promise<void>
  busy: boolean
}

function ActionPanel({ onApprove, onReject, busy }: ActionPanelProps) {
  const [mode, setMode] = useState<ActionMode>('idle')
  const [reason, setReason] = useState('')
  const [reasonError, setReasonError] = useState('')
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  useEffect(() => {
    if (mode === 'reject-form') {
      textareaRef.current?.focus()
    }
  }, [mode])

  const handleRejectSubmit = async () => {
    if (!reason.trim()) {
      setReasonError('Red gerekçesi zorunludur.')
      return
    }
    setReasonError('')
    await onReject(reason.trim())
  }

  if (mode === 'confirm-approve') {
    return (
      <div className="action-panel action-panel--approve">
        <p className="action-panel__question">
          Bu başvuruyu onaylamak istediğinize emin misiniz? Onay sonrası üye kaydı oluşturulur.
        </p>
        <div className="action-panel__buttons">
          <button
            className="btn btn-secondary btn-sm"
            onClick={() => setMode('idle')}
            disabled={busy}
          >
            İptal
          </button>
          <button
            className="btn btn-primary btn-sm"
            onClick={onApprove}
            disabled={busy}
          >
            {busy ? 'Onaylanıyor…' : 'Evet, Onayla'}
          </button>
        </div>
      </div>
    )
  }

  if (mode === 'reject-form') {
    return (
      <div className="action-panel action-panel--reject">
        <label className="form-label required" htmlFor="reject-reason">
          Red Gerekçesi
        </label>
        <textarea
          id="reject-reason"
          ref={textareaRef}
          className={`form-textarea${reasonError ? ' error' : ''}`}
          rows={3}
          placeholder="Başvurunun neden reddedildiğini açıklayın…"
          value={reason}
          onChange={(e) => {
            setReason(e.target.value)
            if (e.target.value.trim()) setReasonError('')
          }}
        />
        {reasonError && <span className="form-error">{reasonError}</span>}
        <div className="action-panel__buttons" style={{ marginTop: 10 }}>
          <button
            className="btn btn-secondary btn-sm"
            onClick={() => { setMode('idle'); setReason(''); setReasonError('') }}
            disabled={busy}
          >
            İptal
          </button>
          <button
            className="btn btn-danger btn-sm"
            onClick={handleRejectSubmit}
            disabled={busy}
          >
            {busy ? 'Reddediliyor…' : 'Reddet'}
          </button>
        </div>
      </div>
    )
  }

  // idle
  return (
    <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
      <button
        className="btn btn-primary"
        onClick={() => setMode('confirm-approve')}
        disabled={busy}
      >
        ✓ Onayla
      </button>
      <button
        className="btn btn-danger"
        onClick={() => setMode('reject-form')}
        disabled={busy}
      >
        ✗ Reddet
      </button>
    </div>
  )
}

// ─── Ana sayfa bileşeni ───────────────────────────────────────────────────────

export default function ApplicationDetailPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()

  const [app, setApp] = useState<MembershipApplication | null>(null)
  const [person, setPerson] = useState<Person | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [actionBusy, setActionBusy] = useState(false)
  const [actionError, setActionError] = useState<string | null>(null)
  const [actionSuccess, setActionSuccess] = useState<string | null>(null)

  const fetchApp = async (appId: string) => {
    setLoading(true)
    setError(null)
    try {
      const resp = await applicationsApi.get(appId)
      setApp(resp.data)
      // person_id varsa üye bilgilerini yükle (member_number için)
      if (resp.data.person_id) {
        try {
          const pResp = await personsApi.get(resp.data.person_id)
          setPerson(pResp.data)
        } catch {
          // person yüklenemese de sayfa çalışmaya devam eder
          setPerson(null)
        }
      } else {
        setPerson(null)
      }
    } catch (err: unknown) {
      const status = (err as { response?: { status?: number } })?.response?.status
      if (status === 404) setError('Başvuru bulunamadı.')
      else if (status === 403) setError('Bu başvuruya erişim yetkiniz yok.')
      else setError('Başvuru yüklenemedi.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    if (id) fetchApp(id)
  }, [id])

  const handleApprove = async () => {
    if (!id) return
    setActionBusy(true)
    setActionError(null)
    setActionSuccess(null)
    try {
      await applicationsApi.transition(id, 'approved')
      setActionSuccess('Başvuru onaylandı. Üye kaydı oluşturuldu.')
      window.dispatchEvent(new CustomEvent('myk:application-updated'))
      await fetchApp(id)
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      setActionError(detail ?? 'Onaylama sırasında hata oluştu.')
    } finally {
      setActionBusy(false)
    }
  }

  const handleReject = async (reason: string) => {
    if (!id) return
    setActionBusy(true)
    setActionError(null)
    setActionSuccess(null)
    try {
      await applicationsApi.transition(id, 'rejected', reason)
      setActionSuccess('Başvuru reddedildi.')
      window.dispatchEvent(new CustomEvent('myk:application-updated'))
      await fetchApp(id)
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      setActionError(detail ?? 'Red işlemi sırasında hata oluştu.')
    } finally {
      setActionBusy(false)
    }
  }

  const pageTitle = app
    ? (`${app.first_name ?? ''} ${app.last_name ?? ''}`.trim() || app.application_number || 'Başvuru Detayı')
    : 'Başvuru Detayı'

  return (
    <AppShell title="Üyelik Başvurusu">
      {/* Geri */}
      <div style={{ marginBottom: 16 }}>
        <button className="btn btn-ghost btn-sm" onClick={() => navigate('/admin/applications')}>
          ← Başvuru Listesine Dön
        </button>
      </div>

      {/* Loading */}
      {loading && (
        <div className="loading-center" style={{ minHeight: 300 }}>
          <span className="loading-spinner lg" />
        </div>
      )}

      {/* Hata */}
      {!loading && error && (
        <div className="alert alert-error">
          <span>⚠️</span>
          <span>{error}</span>
        </div>
      )}

      {/* İçerik */}
      {!loading && app && (
        <>
          {/* Başlık + durum + onay/red */}
          <div className="page-header" style={{ flexWrap: 'wrap', gap: 12 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
              <h1 className="page-title">{pageTitle}</h1>
              <StatusBadge status={app.status} />
              {app.application_number && (
                <span style={{ fontFamily: 'monospace', fontSize: 13, color: 'var(--color-muted)' }}>
                  {app.application_number}
                </span>
              )}
            </div>

            {/* Onay/Red butonları — yalnızca submitted durumunda */}
            {app.status === 'submitted' && (
              <ActionPanel
                onApprove={handleApprove}
                onReject={handleReject}
                busy={actionBusy}
              />
            )}
          </div>

          {/* Action feedback */}
          {actionSuccess && (
            <div className="alert alert-success" style={{ marginBottom: 16 }}>
              <span>✓</span>
              <span>{actionSuccess}</span>
            </div>
          )}
          {actionError && (
            <div className="alert alert-error" style={{ marginBottom: 16 }}>
              <span>⚠️</span>
              <span>{actionError}</span>
            </div>
          )}

          {/* Başvuru Bilgileri */}
          <SectionCard title="Başvuru Bilgileri">
            <DetailItem label="Başvuru No" value={app.application_number} />
            <DetailItem label="Durum" value={STATUS_META[app.status]?.label ?? app.status} />
            <DetailItem label="Gönderilme Tarihi" value={fmt(app.submitted_at)} />
            <DetailItem label="Oluşturulma" value={fmt(app.created_at)} />
            <DetailItem label="Son Güncelleme" value={fmt(app.updated_at)} />
          </SectionCard>

          {/* Kişisel Bilgiler */}
          <SectionCard title="Kişisel Bilgiler">
            <DetailItem label="Ad" value={app.first_name} />
            <DetailItem label="Soyad" value={app.last_name} />
            <DetailItem
              label="T.C. / Pasaport No"
              value={app.national_id ?? null}
            />
            <DetailItem label="Doğum Tarihi" value={fmtDate(app.birth_date)} />
            <DetailItem
              label="Cinsiyet"
              value={
                app.gender === 'erkek' ? 'Erkek'
                : app.gender === 'kadin' ? 'Kadın'
                : app.gender === 'belirtilmedi' ? 'Belirtilmedi'
                : null
              }
            />
            <DetailItem label="Kan Grubu" value={app.blood_type} />
          </SectionCard>

          {/* İletişim */}
          <SectionCard title="İletişim">
            <DetailItem label="Telefon" value={app.phone} />
            <DetailItem label="E-posta" value={app.email} />
            <DetailItem label="Adres" value={app.address} />
          </SectionCard>

          {/* Acil Durum / Veli */}
          {(app.emergency_contact_name || app.emergency_contact_phone ||
            app.guardian_name || app.guardian_phone) && (
            <SectionCard title="Acil Durum & Veli">
              <DetailItem label="Acil Kişi" value={app.emergency_contact_name} />
              <DetailItem label="Acil Telefon" value={app.emergency_contact_phone} />
              <DetailItem label="Veli Adı" value={app.guardian_name} />
              <DetailItem label="Veli Telefonu" value={app.guardian_phone} />
            </SectionCard>
          )}

          {/* Onay Bilgileri — yalnızca approved durumunda */}
          {app.status === 'approved' && (
            <SectionCard title="Üye Bilgileri">
              <DetailItem label="Onay Tarihi" value={fmt(app.approved_at)} />
              {person?.member_number && (
                <DetailItem label="Üye Numarası" value={person.member_number} />
              )}
              {app.person_id && (
                <div className="detail-item">
                  <span className="detail-label">Kişi Kaydı</span>
                  <span className="detail-value">
                    <Link
                      to={`/persons/${app.person_id}`}
                      style={{ color: 'var(--color-ocean)', textDecoration: 'underline' }}
                    >
                      {person
                        ? `${person.first_name} ${person.last_name}`
                        : 'Kişi Detayına Git →'}
                    </Link>
                  </span>
                </div>
              )}
            </SectionCard>
          )}

          {/* Red Bilgileri — yalnızca rejected durumunda */}
          {app.status === 'rejected' && (
            <SectionCard title="Red Bilgileri">
              <DetailItem label="Red Tarihi" value={fmt(app.rejected_at)} />
              <DetailItem label="Red Gerekçesi" value={app.rejection_reason} />
            </SectionCard>
          )}

          {/* İptal Bilgileri — yalnızca cancelled durumunda */}
          {app.status === 'cancelled' && (
            <SectionCard title="İptal Bilgileri">
              <DetailItem label="İptal Tarihi" value={fmt(app.cancelled_at)} />
              <DetailItem label="İptal Gerekçesi" value={app.cancellation_reason} />
            </SectionCard>
          )}
        </>
      )}
    </AppShell>
  )
}
