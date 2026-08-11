import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import AppShell from '@/components/layout/AppShell'
import { personsApi } from '@/api/persons'
import type { Person } from '@/types/person'
import type { GuardianAthlete } from '@/types/guardian'

const RELATION_LABELS: Record<string, string> = {
  anne: 'Anne',
  baba: 'Baba',
  ebeveyn: 'Ebeveyn',
  vasi: 'Vasi',
  akraba: 'Akraba',
  diger: 'Diğer',
}

function DetailItem({
  label,
  value,
}: {
  label: string
  value?: string | null
}) {
  return (
    <div className="detail-item">
      <span className="detail-label">{label}</span>
      <span className="detail-value">{value || '—'}</span>
    </div>
  )
}

export default function GuardianDetailPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()

  const [guardian, setGuardian] = useState<Person | null>(null)
  const [athletes, setAthletes] = useState<GuardianAthlete[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!id) return

    const load = async () => {
      setLoading(true)
      setError(null)

      try {
        const [personResp, athletesResp] = await Promise.all([
          personsApi.get(id),
          personsApi.getAthletes(id),
        ])

        setGuardian(personResp.data)
        setAthletes(athletesResp.data)
      } catch {
        setError('Veli bilgileri yüklenemedi.')
      } finally {
        setLoading(false)
      }
    }

    load()
  }, [id])

  const title = guardian
    ? `${guardian.first_name} ${guardian.last_name}`
    : 'Veli Detayı'

  return (
    <AppShell title={title}>
      <div style={{ marginBottom: 16 }}>
        <button
          className="btn btn-ghost btn-sm"
          onClick={() => navigate('/veliler')}
        >
          ← Veliler Listesine Dön
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

      {guardian && !loading && (
        <>
          <div className="card" style={{ marginBottom: 20 }}>
            <div className="card-header">
              <div
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  gap: 16,
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
                    {guardian.first_name} {guardian.last_name}
                  </div>

                  <div
                    style={{
                      display: 'flex',
                      gap: 6,
                      marginTop: 6,
                      flexWrap: 'wrap',
                    }}
                  >
                    <span className="badge badge-veli">Veli</span>
                    <span
                      className={`badge ${
                        guardian.is_active
                          ? 'badge-aktif'
                          : 'badge-pasif'
                      }`}
                    >
                      {guardian.is_active ? 'Aktif' : 'Pasif'}
                    </span>
                  </div>
                </div>

                <button
                  className="btn btn-secondary"
                  onClick={() => navigate(`/persons/${guardian.id}`)}
                >
                  Kişi Kartını Aç
                </button>
              </div>
            </div>
          </div>

          <div className="card" style={{ marginBottom: 20 }}>
            <div className="card-header">İletişim Bilgileri</div>
            <div className="card-body">
              <div className="detail-grid">
                <DetailItem label="Telefon" value={guardian.phone} />
                <DetailItem label="E-posta" value={guardian.email} />
                <DetailItem label="Adres" value={guardian.address} />
                <DetailItem
                  label="Üye Numarası"
                  value={guardian.member_number}
                />
              </div>
            </div>
          </div>

          <div className="card" style={{ marginBottom: 20 }}>
            <div className="card-header">
              Bağlı Sporcular
              <span
                className="badge badge-aktif"
                style={{ marginLeft: 8 }}
              >
                {athletes.length}
              </span>
            </div>

            <div className="card-body">
              {athletes.length === 0 ? (
                <div className="empty-state">
                  <div className="empty-state-icon">⛵</div>
                  <div className="empty-state-title">
                    Bağlı Sporcu Yok
                  </div>
                  <div className="empty-state-desc">
                    Bu veli henüz herhangi bir sporcu ile ilişkilendirilmemiş.
                  </div>
                </div>
              ) : (
                <div className="table-container">
                  <table className="data-table">
                    <thead>
                      <tr>
                        <th>Sporcu</th>
                        <th>İlişki</th>
                        <th>Birincil Veli</th>
                        <th>Teslim Alma</th>
                        <th>Bildirim</th>
                      </tr>
                    </thead>

                    <tbody>
                      {athletes.map((link) => (
                        <tr
                          key={link.id}
                          onClick={() =>
                            navigate(`/sporcular/${link.athlete_person_id}`)
                          }
                          style={{ cursor: 'pointer' }}
                        >
                          <td>
                            <strong>
                              {link.athlete.first_name}{' '}
                              {link.athlete.last_name}
                            </strong>
                            {link.athlete.phone && (
                              <div
                                style={{
                                  fontSize: 12,
                                  color: 'var(--color-text-muted)',
                                  marginTop: 2,
                                }}
                              >
                                {link.athlete.phone}
                              </div>
                            )}
                          </td>

                          <td>
                            {link.relationship_type
                              ? RELATION_LABELS[
                                  link.relationship_type
                                ] ?? link.relationship_type
                              : '—'}
                          </td>

                          <td>
                            <span
                              className={`badge ${
                                link.is_primary
                                  ? 'badge-aktif'
                                  : 'badge-pasif'
                              }`}
                            >
                              {link.is_primary ? 'Evet' : 'Hayır'}
                            </span>
                          </td>

                          <td>
                            {link.can_pickup ? '✅ Yetkili' : '❌ Yetkisiz'}
                          </td>

                          <td>
                            {link.can_receive_notifications
                              ? '✅ Açık'
                              : '❌ Kapalı'}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </div>

          <div className="card">
            <div className="card-header">Acil Durum Bilgileri</div>
            <div className="card-body">
              <div className="detail-grid">
                <DetailItem
                  label="Acil Kişi"
                  value={guardian.emergency_contact_name}
                />
                <DetailItem
                  label="Acil Telefon"
                  value={guardian.emergency_contact_phone}
                />
              </div>
            </div>
          </div>
        </>
      )}
    </AppShell>
  )
}
