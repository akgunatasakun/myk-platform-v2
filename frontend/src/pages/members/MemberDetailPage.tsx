/**
 * /uyeler/:id — Üye detay sayfası
 *
 * Backend: GET /api/v1/persons/{id}
 * Kişisel bilgiler, iletişim, üyelik bilgileri ve roller.
 * Sporcu veya veli rolü varsa ilgili modüle cross-link verilir.
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

export default function MemberDetailPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()

  const [member, setMember] = useState<Person | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [editOpen, setEditOpen] = useState(false)

  useEffect(() => {
    if (!id) return

    setLoading(true)
    setError(null)

    personsApi
      .get(id)
      .then((r) => setMember(r.data))
      .catch(() => setError('Üye bilgileri yüklenemedi.'))
      .finally(() => setLoading(false))
  }, [id])

  const title = member
    ? `${member.first_name} ${member.last_name}`
    : 'Üye Detayı'

  const isSporcu = member?.role_codes.includes('sporcu')
  const isVeli = member?.role_codes.includes('veli')

  return (
    <AppShell title={title}>
      <div style={{ marginBottom: 16 }}>
        <button
          className="btn btn-ghost btn-sm"
          onClick={() => navigate('/uyeler')}
        >
          ← Üyeler Listesine Dön
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

      {member && !loading && (
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
                    {member.first_name} {member.last_name}
                  </div>

                  <div
                    style={{
                      display: 'flex',
                      gap: 6,
                      marginTop: 6,
                      flexWrap: 'wrap',
                    }}
                  >
                    {member.role_codes.map((r) => (
                      <span
                        key={r}
                        className={`badge badge-${r}`}
                      >
                        {ROLE_LABELS[r] ?? r}
                      </span>
                    ))}
                    <span
                      className={`badge ${
                        member.is_active ? 'badge-aktif' : 'badge-pasif'
                      }`}
                    >
                      {member.is_active ? 'Aktif' : 'Pasif'}
                    </span>
                  </div>
                </div>

                <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                  {isSporcu && (
                    <button
                      className="btn btn-ghost btn-sm"
                      onClick={() => navigate(`/sporcular/${member.id}`)}
                      title="Sporcu profilini aç"
                    >
                      ⛵ Sporcu Profili →
                    </button>
                  )}
                  {isVeli && (
                    <button
                      className="btn btn-ghost btn-sm"
                      onClick={() => navigate(`/veliler/${member.id}`)}
                      title="Veli profilini aç"
                    >
                      👨‍👩‍👧 Veli Profili →
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
                    onClick={() => navigate(`/persons/${member.id}`)}
                    title="Genel kişi kartını aç"
                  >
                    Kişi Kartı →
                  </button>
                </div>
              </div>
            </div>
          </div>

          {/* Üyelik Bilgileri */}
          <div className="card" style={{ marginBottom: 20 }}>
            <div className="card-header">Üyelik Bilgileri</div>
            <div className="card-body">
              <div className="detail-grid">
                <div className="detail-item">
                  <span className="detail-label">Üye Numarası</span>
                  <span
                    className="detail-value"
                    style={{ fontFamily: 'monospace', fontWeight: 600 }}
                  >
                    {member.member_number ?? '—'}
                  </span>
                </div>
                <div className="detail-item">
                  <span className="detail-label">Üyelik Durumu</span>
                  <span className="detail-value">
                    <span
                      className={`badge ${
                        member.is_active ? 'badge-aktif' : 'badge-pasif'
                      }`}
                    >
                      {member.is_active ? 'Aktif' : 'Pasif'}
                    </span>
                  </span>
                </div>
                <DetailItem
                  label="Sisteme Kayıt"
                  value={fmtDate(member.created_at.substring(0, 10))}
                />
              </div>
            </div>
          </div>

          {/* Kişisel Bilgiler */}
          <div className="card" style={{ marginBottom: 20 }}>
            <div className="card-header">Kişisel Bilgiler</div>
            <div className="card-body">
              <div className="detail-grid">
                <DetailItem label="Doğum Tarihi" value={fmtDate(member.birth_date)} />
                <DetailItem
                  label="Cinsiyet"
                  value={
                    member.gender
                      ? GENDER_LABELS[member.gender] ?? member.gender
                      : undefined
                  }
                />
                <DetailItem label="Kan Grubu" value={member.blood_type} />
                {member.national_id && member.national_id !== '***' && (
                  <DetailItem label="TC / Pasaport No" value={member.national_id} />
                )}
              </div>
            </div>
          </div>

          {/* İletişim */}
          <div className="card" style={{ marginBottom: 20 }}>
            <div className="card-header">İletişim</div>
            <div className="card-body">
              <div className="detail-grid">
                <DetailItem label="Telefon" value={member.phone} />
                <DetailItem label="E-posta" value={member.email} />
                {member.address && (
                  <div
                    className="detail-item"
                    style={{ gridColumn: '1 / -1' }}
                  >
                    <span className="detail-label">Adres</span>
                    <span className="detail-value" style={{ whiteSpace: 'pre-wrap' }}>
                      {member.address}
                    </span>
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* Acil Durum */}
          {(member.emergency_contact_name || member.emergency_contact_phone) && (
            <div className="card" style={{ marginBottom: 20 }}>
              <div className="card-header">Acil Durum</div>
              <div className="card-body">
                <div className="detail-grid">
                  <DetailItem
                    label="Acil Kişi"
                    value={member.emergency_contact_name}
                  />
                  <DetailItem
                    label="Acil Telefon"
                    value={member.emergency_contact_phone}
                  />
                </div>
              </div>
            </div>
          )}

          {/* Notlar */}
          {member.notes && (
            <div className="card" style={{ marginBottom: 20 }}>
              <div className="card-header">Notlar</div>
              <div className="card-body">
                <p style={{ whiteSpace: 'pre-wrap', margin: 0, fontSize: 14 }}>
                  {member.notes}
                </p>
              </div>
            </div>
          )}
        </>
      )}

      {member && (
        <PersonFormModal
          isOpen={editOpen}
          onClose={() => setEditOpen(false)}
          person={member}
          title="Üye Bilgilerini Düzenle"
          forcedRole="uye"
          onSaved={(updated) => {
            setMember(updated)
            setEditOpen(false)
          }}
        />
      )}
    </AppShell>
  )
}
