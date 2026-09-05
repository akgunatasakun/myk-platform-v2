/**
 * Antrenör / Başantrenör — Bekleyen Evraklar Kuyruğu
 *
 * Antrenörün kulübündeki tüm sporcular listelenir; seçilen sporcu için
 * PersonDocumentsTab üzerinden bekleyen evraklar gösterilir.
 */
import { useEffect, useState } from 'react'
import AppShell from '@/components/layout/AppShell'
import PersonDocumentsTab from '@/components/persons/PersonDocumentsTab'
import type { PersonDocumentsRole } from '@/components/persons/PersonDocumentsTab'
import { athletesApi } from '@/api/athletes'
import type { AthleteListItem, AthleteListOut } from '@/types/athlete'
import { useAuth } from '@/hooks/useAuth'

export default function PersonDocumentQueuePage() {
  const { user: authUser } = useAuth()
  const [athletes, setAthletes] = useState<AthleteListItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [selectedPersonId, setSelectedPersonId] = useState<string | null>(null)

  const docsRole: PersonDocumentsRole =
    authUser?.role === 'basantrenor' ? 'basantrenor' : 'antrenor'

  useEffect(() => {
    setLoading(true)
    athletesApi
      .list({ limit: 500, is_active: true })
      .then((r) => {
        setAthletes((r.data as AthleteListOut).items)
      })
      .catch(() => setError('Sporcu listesi yüklenemedi.'))
      .finally(() => setLoading(false))
  }, [])

  return (
    <AppShell title="Bekleyen Evraklar">
      <div style={{ marginBottom: 20 }}>
        <h2 style={{ fontSize: 18, fontWeight: 700, color: 'var(--color-navy)', margin: 0 }}>
          Bekleyen Evraklar Kuyruğu
        </h2>
        <p style={{ fontSize: 14, color: 'var(--color-text-secondary)', marginTop: 4 }}>
          Sporcu seçin, ardından bekleyen evrakları onaylayın veya reddedin.
        </p>
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

      {!loading && !error && (
        <div style={{ display: 'flex', gap: 20, alignItems: 'flex-start' }}>
          {/* Sporcu listesi */}
          <div className="card" style={{ minWidth: 240, flexShrink: 0 }}>
            <div className="card-header">Sporcular</div>
            <div className="card-body" style={{ padding: 0 }}>
              {athletes.length === 0 ? (
                <div className="empty-state" style={{ padding: '16px 0' }}>
                  <div className="empty-state-title">Sporcu bulunamadı.</div>
                </div>
              ) : (
                <ul style={{ listStyle: 'none', margin: 0, padding: 0 }}>
                  {athletes.map((a) => (
                    <li
                      key={a.person_id}
                      onClick={() => setSelectedPersonId(a.person_id)}
                      style={{
                        padding: '10px 16px',
                        cursor: 'pointer',
                        borderBottom: '1px solid var(--color-border)',
                        background:
                          selectedPersonId === a.person_id
                            ? 'var(--color-ocean-light, #e0f2fe)'
                            : 'transparent',
                        fontWeight: selectedPersonId === a.person_id ? 600 : 400,
                      }}
                    >
                      {a.first_name} {a.last_name}
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>

          {/* Sağ panel: evraklar */}
          <div style={{ flex: 1 }}>
            {selectedPersonId ? (
              <PersonDocumentsTab
                subjectPersonId={selectedPersonId}
                role={docsRole}
              />
            ) : (
              <div className="card">
                <div className="card-body">
                  <div className="empty-state" style={{ padding: '32px 0' }}>
                    <div className="empty-state-icon">📋</div>
                    <div className="empty-state-title">Soldaki listeden sporcu seçin.</div>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </AppShell>
  )
}
