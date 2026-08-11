/**
 * /antrenorler/:id — Antrenör detay sayfası
 *
 * Backend: GET /api/v1/persons/{id}
 */
import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import AppShell from '@/components/layout/AppShell'
import PersonFormModal from '@/pages/persons/PersonFormModal'
import { personsApi } from '@/api/persons'
import type { Person } from '@/types/person'

const ROLE_LABELS: Record<string, string> = {
  sporcu: 'Sporcu',
  uye: 'Üye',
  veli: 'Veli',
  antrenor: 'Antrenör',
  personel: 'Personel',
  misafir: 'Misafir',
}

const GENDER_LABELS: Record<string, string> = {
  erkek: 'Erkek',
  kadin: 'Kadın',
  belirtilmedi: 'Belirtilmedi',
}

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

export default function CoachDetailPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()

  const [coach, setCoach] = useState<Person | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [editOpen, setEditOpen] = useState(false)

  useEffect(() => {
    if (!id) return

    setLoading(true)
    setError(null)

    personsApi
      .get(id)
      .then((r) => setCoach(r.data))
      .catch(() => setError('Antrenör bilgileri yüklenemedi.'))
      .finally(() => setLoading(false))
  }, [id])

  const title = coach
    ? `${coach.first_name} ${coach.last_name}`
    : 'Antrenör Detayı'

  const isSporcu = coach?.role_codes.includes('sporcu')
  const isUye = coach?.role_codes.includes('uye')

  return (
    <AppShell title={title}>
      <div style={{ marginBottom: 16 }}>
        <button
          className="btn btn-ghost btn-sm"
          onClick={() => navigate('/antrenorler')}
        >
          ← Antrenörler Listesine Dön
        </button>
      </div>

      {loading && (
        <div className="loading-center">
          <span className="loading-spinner lg" />
        </div>
      )}

      {error && (
        <div className="alert alert-error">
          <span>⚠️</span>
          <span>{error}</span>
        </div>
      )}

      {coach && !loading && (
        <>
          {/* Header */}
          <div className="card" style={{ marginBottom: 20 }}>
            <div className="card-header">
              <div
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'flex-start',
                  gap: 16,
                  flexWrap: 'wrap',
                }}
              >
                <div>
                  <div
                    style={{
                      fontSize: 20,
                      fontWeight: 700,
                      color: 'var(--color-navy)',
                    }}
                  >
                    {coach.first_name} {coach.last_name}
                  </div>

                  <div
                    style={{
                      display: 'flex',
                      gap: 6,
                      marginTop: 6,
                      flexWrap: 'wrap',
                    }}
                  >
                    {coach.role_codes.map((r) => (
                      <span key={r} className={`badge badge-${r}`}>
                        {ROLE_LABELS[r] ?? r}
                      </span>
                    ))}
                    <span
                      className={`badge ${
                        coach.is_active ? 'badge-aktif' : 'badge-pasif'
                      }`}
                    >
                      {coach.is_active ? 'Aktif' : 'Pasif'}
                    </span>
                  </div>
                </div>

                <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                  {isSporcu && (
                    <button
                      className="btn btn-ghost btn-sm"
                      onClick={() => navigate(`/sporcular/${coach.id}`)}
                    >
                      ⛵ Sporcu Profili →
                    </button>
                  )}
                  {isUye && (
                    <button
                      className="btn btn-ghost btn-sm"
                      onClick={() => navigate(`/uyeler/${coach.id}`)}
                    >
                      🏅 Üye Kartı →
                    </button>
                  )}
                  <button
                    className="btn btn-secondary btn-sm"
                    onClick={() => setEditOpen(true)}
                  >
                    Düzenle
                  </button>
                  <button
                    className="btn btn-ghost btn-sm"
                    onClick={() => navigate(`/persons/${coach.id}`)}
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
                <DetailItem label="Doğum Tarihi" value={fmtDate(coach.birth_date)} />
                <DetailItem
                  label="Cinsiyet"
                  value={
                    coach.gender
                      ? GENDER_LABELS[coach.gender] ?? coach.gender
                      : undefined
                  }
                />
                <DetailItem label="Kan Grubu" value={coach.blood_type} />
                {coach.national_id && coach.national_id !== '***' && (
                  <DetailItem label="TC / Pasaport No" value={coach.national_id} />
                )}
              </div>
            </div>
          </div>

          {/* İletişim */}
          <div className="card" style={{ marginBottom: 20 }}>
            <div className="card-header">İletişim</div>
            <div className="card-body">
              <div className="detail-grid">
                <DetailItem label="Telefon" value={coach.phone} />
                <DetailItem label="E-posta" value={coach.email} />
                {coach.address && (
                  <div className="detail-item" style={{ gridColumn: '1 / -1' }}>
                    <span className="detail-label">Adres</span>
                    <span
                      className="detail-value"
                      style={{ whiteSpace: 'pre-wrap' }}
                    >
                      {coach.address}
                    </span>
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* Acil Durum */}
          {(coach.emergency_contact_name || coach.emergency_contact_phone) && (
            <div className="card" style={{ marginBottom: 20 }}>
              <div className="card-header">Acil Durum</div>
              <div className="card-body">
                <div className="detail-grid">
                  <DetailItem
                    label="Acil Kişi"
                    value={coach.emergency_contact_name}
                  />
                  <DetailItem
                    label="Acil Telefon"
                    value={coach.emergency_contact_phone}
                  />
                </div>
              </div>
            </div>
          )}

          {/* Notlar */}
          {coach.notes && (
            <div className="card" style={{ marginBottom: 20 }}>
              <div className="card-header">Notlar</div>
              <div className="card-body">
                <p style={{ whiteSpace: 'pre-wrap', margin: 0, fontSize: 14 }}>
                  {coach.notes}
                </p>
              </div>
            </div>
          )}
        </>
      )}

      {coach && (
        <PersonFormModal
          isOpen={editOpen}
          onClose={() => setEditOpen(false)}
          person={coach}
          title="Antrenör Bilgilerini Düzenle"
          forcedRole="antrenor"
          onSaved={(updated) => {
            setCoach(updated)
            setEditOpen(false)
          }}
        />
      )}
    </AppShell>
  )
}
