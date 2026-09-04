import { useCallback, useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import AppShell from '@/components/layout/AppShell'
import PersonFormModal from '@/pages/persons/PersonFormModal'
import { personsApi } from '@/api/persons'
import type { Person, PersonListResponse } from '@/types/person'
import { useAuth } from '@/hooks/useAuth'
import { canManageGuardians } from '@/utils/guardianPermissions'

const PAGE_SIZE = 20

export default function GuardiansPage() {
  const navigate = useNavigate()
  const { user } = useAuth()

  const [data, setData] = useState<PersonListResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const [search, setSearch] = useState('')
  const [activeFilter, setActiveFilter] = useState('')
  const [skip, setSkip] = useState(0)
  const [createOpen, setCreateOpen] = useState(false)

  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const fetchGuardians = useCallback(
    async (searchVal: string, active: string, skipVal: number) => {
      setLoading(true)
      setError(null)

      try {
        const params: Record<string, unknown> = {
          skip: skipVal,
          limit: PAGE_SIZE,
          role_code: 'veli',
        }

        if (searchVal) params.search = searchVal
        if (active !== '') params.is_active = active === 'true'

        const resp = await personsApi.list(params)
        setData(resp.data)
      } catch {
        setError('Veliler yüklenemedi.')
      } finally {
        setLoading(false)
      }
    },
    []
  )

  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current)

    debounceRef.current = setTimeout(() => {
      setSkip(0)
      fetchGuardians(search, activeFilter, 0)
    }, 300)

    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current)
    }
  }, [search, activeFilter, fetchGuardians])

  useEffect(() => {
    fetchGuardians(search, activeFilter, skip)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [skip])

  const totalPages = data ? Math.ceil(data.total / PAGE_SIZE) : 0
  const currentPage = Math.floor(skip / PAGE_SIZE) + 1

  const guardianName = (person: Person) =>
    `${person.first_name} ${person.last_name}`

  return (
    <AppShell title="Veliler">
      <div className="page-header">
        <h1 className="page-title">Veliler</h1>
        {canManageGuardians(user?.role) && (
          <button className="btn btn-primary" onClick={() => setCreateOpen(true)}>
            + Yeni Veli
          </button>
        )}
      </div>

      <div className="filter-bar">
        <div className="filter-search">
          <span className="filter-search-icon">🔍</span>
          <input
            type="text"
            className="filter-search-input"
            placeholder="Ad, soyad, e-posta veya telefon ara..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>

        <select
          className="form-select"
          style={{ width: 'auto', minWidth: 130 }}
          value={activeFilter}
          onChange={(e) => setActiveFilter(e.target.value)}
        >
          <option value="">Tüm Durumlar</option>
          <option value="true">Aktif</option>
          <option value="false">Pasif</option>
        </select>
      </div>

      {error && (
        <div className="alert alert-error">
          <span>⚠️</span>
          <span>{error}</span>
        </div>
      )}

      <div className="table-container">
        {loading ? (
          <div className="loading-center">
            <span className="loading-spinner lg" />
          </div>
        ) : !data || data.items.length === 0 ? (
          <div className="empty-state">
            <div className="empty-state-icon">👨‍👩‍👧</div>
            <div className="empty-state-title">Veli Bulunamadı</div>
            <div className="empty-state-desc">
              {search || activeFilter
                ? 'Arama kriterlerinize uyan veli bulunamadı.'
                : 'Henüz veli rolüne sahip kayıt bulunmuyor.'}
            </div>
          </div>
        ) : (
          <>
            <table className="data-table">
              <thead>
                <tr>
                  <th>Ad Soyad</th>
                  <th>Telefon</th>
                  <th>E-posta</th>
                  <th>Üye No</th>
                  <th>Durum</th>
                </tr>
              </thead>

              <tbody>
                {data.items.map((guardian) => (
                  <tr
                    key={guardian.id}
                    onClick={() => navigate(`/veliler/${guardian.id}`)}
                    style={{ cursor: 'pointer' }}
                  >
                    <td>
                      <strong>{guardianName(guardian)}</strong>
                    </td>
                    <td>{guardian.phone ?? '—'}</td>
                    <td>{guardian.email ?? '—'}</td>
                    <td>{guardian.member_number ?? '—'}</td>
                    <td>
                      <span
                        className={`badge ${
                          guardian.is_active
                            ? 'badge-aktif'
                            : 'badge-pasif'
                        }`}
                      >
                        {guardian.is_active ? 'Aktif' : 'Pasif'}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>

            {data.total > PAGE_SIZE && (
              <div className="pagination">
                <span>
                  {data.total} veliden {skip + 1}–
                  {Math.min(skip + PAGE_SIZE, data.total)} arası gösteriliyor
                </span>

                <div className="pagination-controls">
                  <button
                    className="btn btn-sm btn-secondary"
                    disabled={skip === 0}
                    onClick={() =>
                      setSkip((s) => Math.max(0, s - PAGE_SIZE))
                    }
                  >
                    ← Önceki
                  </button>

                  <span style={{ padding: '5px 10px', fontSize: 13 }}>
                    {currentPage} / {totalPages}
                  </span>

                  <button
                    className="btn btn-sm btn-secondary"
                    disabled={skip + PAGE_SIZE >= data.total}
                    onClick={() => setSkip((s) => s + PAGE_SIZE)}
                  >
                    Sonraki →
                  </button>
                </div>
              </div>
            )}
          </>
        )}
      </div>

      <PersonFormModal
        isOpen={createOpen}
        onClose={() => setCreateOpen(false)}
        forcedRole="veli"
        title="Yeni Veli"
        onSaved={() => {
          setCreateOpen(false)
          setSkip(0)
          void fetchGuardians(search, activeFilter, 0)
        }}
      />
    </AppShell>
  )
}
