/**
 * /uyeler — Üye listesi
 *
 * Backend: GET /api/v1/persons?role_code=uye
 * Özellikler:
 *   - Arama (ad, soyad, e-posta, telefon)
 *   - Aktif/pasif filtresi
 *   - Pagination (20 kayıt/sayfa)
 *   - Satıra tıkla → /uyeler/:id
 *   - Yeni Üye ekle (PersonFormModal, forcedRole=uye)
 */
import { useCallback, useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import AppShell from '@/components/layout/AppShell'
import PersonFormModal from '@/pages/persons/PersonFormModal'
import { personsApi } from '@/api/persons'
import type { Person, PersonListResponse } from '@/types/person'

const PAGE_SIZE = 20

const ROLE_LABELS: Record<string, string> = {
  sporcu: 'Sporcu',
  uye: 'Üye',
  veli: 'Veli',
  antrenor: 'Antrenör',
  personel: 'Personel',
  misafir: 'Misafir',
}

export default function MembersPage() {
  const navigate = useNavigate()

  const [data, setData] = useState<PersonListResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const [search, setSearch] = useState('')
  const [activeFilter, setActiveFilter] = useState('')
  const [skip, setSkip] = useState(0)
  const [formOpen, setFormOpen] = useState(false)

  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const fetchMembers = useCallback(
    async (searchVal: string, active: string, skipVal: number) => {
      setLoading(true)
      setError(null)

      try {
        const params: Record<string, unknown> = {
          skip: skipVal,
          limit: PAGE_SIZE,
          role_code: 'uye',
        }

        if (searchVal) params.search = searchVal
        if (active !== '') params.is_active = active === 'true'

        const resp = await personsApi.list(params)
        setData(resp.data)
      } catch {
        setError('Üyeler yüklenemedi.')
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
      fetchMembers(search, activeFilter, 0)
    }, 300)

    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current)
    }
  }, [search, activeFilter, fetchMembers])

  useEffect(() => {
    fetchMembers(search, activeFilter, skip)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [skip])

  const totalPages = data ? Math.ceil(data.total / PAGE_SIZE) : 0
  const currentPage = Math.floor(skip / PAGE_SIZE) + 1

  const otherRoles = (member: Person) =>
    member.role_codes
      .filter((r) => r !== 'uye')
      .map((r) => ROLE_LABELS[r] ?? r)

  return (
    <AppShell title="Üyeler">
      <div className="page-header">
        <h1 className="page-title">
          Üyeler{data && data.total > 0 && ` (${data.total})`}
        </h1>
        <button
          className="btn btn-primary btn-sm"
          onClick={() => setFormOpen(true)}
        >
          + Yeni Üye
        </button>
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
            <div className="empty-state-icon">🏅</div>
            <div className="empty-state-title">Üye Bulunamadı</div>
            <div className="empty-state-desc">
              {search || activeFilter
                ? 'Arama kriterlerinize uyan üye bulunamadı.'
                : 'Henüz üye kaydı bulunmuyor.'}
            </div>
            {!search && !activeFilter && (
              <button
                className="btn btn-primary"
                style={{ marginTop: 12 }}
                onClick={() => setFormOpen(true)}
              >
                İlk Üyeyi Ekle
              </button>
            )}
          </div>
        ) : (
          <>
            <table className="data-table">
              <thead>
                <tr>
                  <th>Üye No</th>
                  <th>Ad Soyad</th>
                  <th>Telefon</th>
                  <th>E-posta</th>
                  <th>Diğer Roller</th>
                  <th>Durum</th>
                </tr>
              </thead>

              <tbody>
                {data.items.map((member) => {
                  const others = otherRoles(member)
                  return (
                    <tr
                      key={member.id}
                      onClick={() => navigate(`/uyeler/${member.id}`)}
                      style={{ cursor: 'pointer' }}
                    >
                      <td style={{ fontFamily: 'monospace', fontSize: 13 }}>
                        {member.member_number ?? '—'}
                      </td>
                      <td>
                        <strong>
                          {member.first_name} {member.last_name}
                        </strong>
                      </td>
                      <td>{member.phone ?? '—'}</td>
                      <td style={{ fontSize: 13 }}>{member.email ?? '—'}</td>
                      <td>
                        {others.length > 0 ? (
                          <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
                            {others.map((r) => (
                              <span
                                key={r}
                                className="badge"
                                style={{ background: '#f0f9ff', color: '#0369a1', fontSize: 11 }}
                              >
                                {r}
                              </span>
                            ))}
                          </div>
                        ) : (
                          '—'
                        )}
                      </td>
                      <td>
                        <span
                          className={`badge ${
                            member.is_active ? 'badge-aktif' : 'badge-pasif'
                          }`}
                        >
                          {member.is_active ? 'Aktif' : 'Pasif'}
                        </span>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>

            {data.total > PAGE_SIZE && (
              <div className="pagination">
                <span>
                  {data.total} üyeden {skip + 1}–
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
        isOpen={formOpen}
        onClose={() => setFormOpen(false)}
        title="Yeni Üye Ekle"
        forcedRole="uye"
        onSaved={() => {
          setFormOpen(false)
          fetchMembers(search, activeFilter, skip)
        }}
      />
    </AppShell>
  )
}
