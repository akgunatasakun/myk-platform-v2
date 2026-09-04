/**
 * /sporcular/:person_id — Sporcu detay sayfası
 *
 * Kişisel bilgiler (Person) + Sporcu profili (AthleteProfile) birleşik görünümü.
 * Backend: GET /api/v1/athletes/{person_id}
 */
import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import AppShell from '@/components/layout/AppShell'
import AthleteProfileModal from './AthleteProfileModal'
import { athletesApi } from '@/api/athletes'
import type { AthleteDetailOut, DocumentStatus } from '@/types/athlete'
import { formatPersonAge } from '@/utils/personAge'

function fmtDate(d?: string | null) {
  if (!d) return '—'
  return new Date(d + 'T00:00:00').toLocaleDateString('tr-TR')
}

function DetailItem({ label, value }: { label: string; value?: string | null }) {
  return (
    <div className="detail-item">
      <span className="detail-label">{label}</span>
      <span className="detail-value">{value || '—'}</span>
    </div>
  )
}

function DocStatusBadge({ status, date: d }: { status: DocumentStatus; date?: string | null }) {
  const colors: Record<DocumentStatus, string> = {
    gecerli: 'var(--color-success)',
    yaklasan: 'var(--color-warning)',
    dolmus: 'var(--color-danger)',
    eksik: 'var(--color-text-muted)',
  }
  const labels: Record<DocumentStatus, string> = {
    gecerli: 'Geçerli',
    yaklasan: 'Yaklaşıyor',
    dolmus: 'Dolmuş',
    eksik: 'Eksik',
  }
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
      <span style={{ color: colors[status], fontWeight: 600 }}>{labels[status]}</span>
      {d && <span style={{ fontSize: 13, color: 'var(--color-text-muted)' }}>{fmtDate(d)}</span>}
    </div>
  )
}

const LEVEL_LABELS: Record<string, string> = {
  baslangic: 'Başlangıç',
  orta: 'Orta',
  ileri: 'İleri',
  elit: 'Elit',
}

const GENDER_LABELS: Record<string, string> = {
  erkek: 'Erkek',
  kadin: 'Kadın',
  belirtilmedi: 'Belirtilmedi',
}

export default function AthleteDetailPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [athlete, setAthlete] = useState<AthleteDetailOut | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [profileModalOpen, setProfileModalOpen] = useState(false)

  useEffect(() => {
    if (!id) return
    setLoading(true)
    athletesApi.get(id)
      .then((r) => setAthlete(r.data))
      .catch(() => setError('Sporcu bulunamadı.'))
      .finally(() => setLoading(false))
  }, [id])

  const ap = athlete?.athlete_profile

  const title = athlete
    ? `${athlete.first_name} ${athlete.last_name}`
    : 'Sporcu Detayı'

  return (
    <AppShell title={title}>
      <div style={{ marginBottom: 16 }}>
        <button className="btn btn-ghost btn-sm" onClick={() => navigate('/sporcular')}>
          ← Sporculara Dön
        </button>
      </div>

      {loading && <div className="loading-center"><span className="loading-spinner lg" /></div>}
      {error && <div className="alert alert-error"><span>⚠️</span><span>{error}</span></div>}

      {athlete && !loading && (
        <>
          {/* Header */}
          <div className="card" style={{ marginBottom: 20 }}>
            <div className="card-header">
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
                  <div style={{
                    width: 56, height: 56, borderRadius: '50%',
                    background: 'var(--color-ocean)', color: '#fff',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    fontSize: 22, fontWeight: 700, flexShrink: 0,
                  }}>
                    {athlete.first_name[0]}{athlete.last_name[0]}
                  </div>
                  <div>
                    <div style={{ fontSize: 20, fontWeight: 700, color: 'var(--color-navy)' }}>
                      {athlete.first_name} {athlete.last_name}
                    </div>
                    <div style={{ display: 'flex', gap: 8, marginTop: 6, flexWrap: 'wrap' }}>
                      <span className="badge badge-sporcu">Sporcu</span>
                      {ap?.class_name && (
                        <span className="badge badge-planlandi">{ap.class_name}</span>
                      )}
                      {ap?.level && (
                        <span className="badge" style={{ background: '#f5f3ff', color: '#6d28d9' }}>
                          {LEVEL_LABELS[ap.level] ?? ap.level}
                        </span>
                      )}
                      <span className={`badge ${athlete.is_active ? 'badge-aktif' : 'badge-pasif'}`}>
                        {athlete.is_active ? 'Aktif' : 'Pasif'}
                      </span>
                    </div>
                  </div>
                </div>
                <div style={{ display: 'flex', gap: 10 }}>
                  <button
                    className="btn btn-secondary"
                    onClick={() => setProfileModalOpen(true)}
                  >
                    {ap ? 'Profil Düzenle' : 'Profil Oluştur'}
                  </button>
                  <button
                    className="btn btn-ghost btn-sm"
                    onClick={() => navigate(`/persons/${id}`)}
                    title="Kişi profiline git"
                  >
                    Kişi Kartı →
                  </button>
                </div>
              </div>
            </div>
          </div>

          {/* Kişisel Bilgiler */}
          <div className="card" style={{ marginBottom: 20 }}>
            <div className="card-header">Kişisel Bilgiler</div>
            <div className="card-body">
              <div className="detail-grid">
                <DetailItem label="Doğum Tarihi" value={fmtDate(athlete.birth_date)} />
                <DetailItem label="Güncel Yaş" value={formatPersonAge(athlete.birth_date)} />
                <DetailItem
                  label="Cinsiyet"
                  value={athlete.gender ? GENDER_LABELS[athlete.gender] ?? athlete.gender : undefined}
                />
                {athlete.member_number && (
                  <DetailItem label="Üye No" value={athlete.member_number} />
                )}
              </div>
            </div>
          </div>

          {/* Sporcu Profili */}
          {!ap ? (
            <div className="card" style={{ marginBottom: 20 }}>
              <div className="card-header">Sporcu Profili</div>
              <div className="card-body">
                <div className="empty-state" style={{ padding: '24px 0' }}>
                  <div className="empty-state-icon">⛵</div>
                  <div className="empty-state-title">Profil Girilmemiş</div>
                  <div className="empty-state-desc">Lisans, sınıf, sağlık ve KVKK bilgileri henüz eklenmemiş.</div>
                  <button
                    className="btn btn-primary"
                    style={{ marginTop: 12 }}
                    onClick={() => setProfileModalOpen(true)}
                  >
                    Profil Oluştur
                  </button>
                </div>
              </div>
            </div>
          ) : (
            <>
              {/* Lisans & Vize */}
              <div className="card" style={{ marginBottom: 20 }}>
                <div className="card-header">Lisans & Vize</div>
                <div className="card-body">
                  <div className="detail-grid">
                    <DetailItem label="Lisans No" value={ap.license_no} />
                    <div className="detail-item">
                      <span className="detail-label">Lisans Durumu</span>
                      <DocStatusBadge status={ap.license_status} date={ap.license_expiry_date} />
                    </div>
                    <div className="detail-item">
                      <span className="detail-label">Vize Durumu</span>
                      <DocStatusBadge status={ap.visa_status} date={ap.visa_expiry_date} />
                    </div>
                  </div>
                </div>
              </div>

              {/* Sağlık */}
              <div className="card" style={{ marginBottom: 20 }}>
                <div className="card-header">Sağlık</div>
                <div className="card-body">
                  <div className="detail-grid">
                    <div className="detail-item">
                      <span className="detail-label">Sağlık Raporu</span>
                      <DocStatusBadge status={ap.health_status} date={ap.health_report_expiry_date} />
                    </div>
                    <div className="detail-item">
                      <span className="detail-label">Yüzme Yeterliliği</span>
                      <span className="detail-value">
                        {ap.swimming_qualified
                          ? <span style={{ color: 'var(--color-success)', fontWeight: 600 }}>✓ Var</span>
                          : <span style={{ color: 'var(--color-text-muted)' }}>Yok</span>
                        }
                      </span>
                    </div>
                    {ap.allergies && (
                      <div className="detail-item" style={{ gridColumn: '1 / -1' }}>
                        <span className="detail-label">Alerji</span>
                        <span className="detail-value" style={{ whiteSpace: 'pre-wrap' }}>{ap.allergies}</span>
                      </div>
                    )}
                    {ap.special_conditions && (
                      <div className="detail-item" style={{ gridColumn: '1 / -1' }}>
                        <span className="detail-label">Özel Durum</span>
                        <span className="detail-value" style={{ whiteSpace: 'pre-wrap' }}>{ap.special_conditions}</span>
                      </div>
                    )}
                  </div>
                </div>
              </div>

              {/* KVKK & İzinler */}
              <div className="card" style={{ marginBottom: 20 }}>
                <div className="card-header">KVKK & İzinler</div>
                <div className="card-body">
                  <div className="detail-grid">
                    <div className="detail-item">
                      <span className="detail-label">KVKK Onayı</span>
                      <span className="detail-value">
                        {ap.kvkk_consent
                          ? <span style={{ color: 'var(--color-success)', fontWeight: 600 }}>✓ Onaylandı{ap.kvkk_consent_at ? ` (${fmtDate(ap.kvkk_consent_at.substring(0, 10))})` : ''}</span>
                          : <span style={{ color: 'var(--color-danger)' }}>✗ Onaylanmadı</span>
                        }
                      </span>
                    </div>
                    <div className="detail-item">
                      <span className="detail-label">Fotoğraf/Video İzni</span>
                      <span className="detail-value">
                        {ap.photo_video_consent
                          ? <span style={{ color: 'var(--color-success)', fontWeight: 600 }}>✓ Var</span>
                          : <span style={{ color: 'var(--color-text-muted)' }}>Yok</span>
                        }
                      </span>
                    </div>
                    {ap.kvkk_text_version && (
                      <DetailItem label="KVKK Metni" value={`Sürüm ${ap.kvkk_text_version}`} />
                    )}
                  </div>
                </div>
              </div>
            </>
          )}
        </>
      )}

      {athlete && (
        <AthleteProfileModal
          isOpen={profileModalOpen}
          onClose={() => setProfileModalOpen(false)}
          personId={athlete.person_id}
          profile={athlete}
          onSaved={(updated) => {
            setAthlete(updated)
            setProfileModalOpen(false)
          }}
        />
      )}
    </AppShell>
  )
}
