import { useCallback, useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import AppShell from '@/components/layout/AppShell'
import PersonFormModal from './PersonFormModal'
import { personsApi } from '@/api/persons'
import type { Person, PersonRoleCode, PersonListResponse } from '@/types/person'

const ROLE_LABELS: Record<PersonRoleCode, string> = {
  sporcu: 'Sporcu',
  uye: 'Üye',
  veli: 'Veli',
  antrenor: 'Antrenör',
  personel: 'Personel',
  misafir: 'Misafir',
}

const PAGE_SIZE = 20

function RoleBadge({ code }: { code: PersonRoleCode }) {
  return (
    <span className={`badge badge-${code}`}>
      {ROLE_LABELS[code] ?? code}
    </span>
  )
}

export default function PersonsPage() {
  const navigate = useNavigate()
  const [data, setData] = useState<PersonListResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const [search, setSearch] = useState('')
  const [roleFilter, setRoleFilter] = useState('')
  const [activeFilter, setActiveFilter] = useState<string>('')
  const [skip, setSkip] = useState(0)

  const [modalOpen, setModalOpen] = useState(false)
  const [editPerson, setEditPerson] = useState<Person | undefined>(undefined)

  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const fetchPersons = useCallback(
    async (searchVal: string, role: string, active: string, skipVal: number) => {
      setLoading(true)
      setError(null)
      try {
        const params: Record<string, unknown> = {
          skip: skipVal,
          limit: PAGE_SIZE,
        }
        if (searchVal) params.search = searchVal
        if (role) params.role_code = role
        if (active !== '') params.is_active = active === 'true'

        const resp = await personsApi.list(params)
        setData(resp.data)
      } catch {
        setError('Kişiler yüklenemedi.')
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
      fetchPersons(search, roleFilter, activeFilter, 0)
    }, 300)
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current)
    }
  }, [search, roleFilter, activeFilter, fetchPersons])

  useEffect(() => {
    fetchPersons(search, roleFilter, activeFilter, skip)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [skip])

  const handleSaved = (saved: Person) => {
    setData((prev) => {
      if (!prev) return prev
      const exists = prev.items.some((p) => p.id === saved.id)
      if (exists) {
        return {
          ...prev,
          items: prev.items.map((p) => (p.id === saved.id ? saved : p)),
        }
      }
      return {
        ...prev,
        items: [saved, ...prev.items],
        total: prev.total + 1,
      }
    })
  }

  const handleDeactivate = async (person: Person, e: React.MouseEvent) => {
    e.stopPropagation()
    if (!window.confirm(`${person.first_name} ${person.last_name} kişisini pasife almak istiyor musunuz?`))
      return
    try {
      const resp = await personsApi.update(person.id, { is_active: !person.is_active })
      setData((prev) =>
        prev
          ? { ...prev, items: prev.items.map((p) => (p.id === person.id ? resp.data : p)) }
          : prev
      )
    } catch {
      alert('İşlem sırasında hata oluştu.')
    }
  }

  const handleDelete = async (person: Person, e: React.MouseEvent) => {
    e.stopPropagation()
    if (
      !window.confirm(
        `${person.first_name} ${person.last_name} kişisini silmek istiyor musunuz? Bu işlem geri alınamaz.`
      )
    )
      return
    try {
      await personsApi.delete(person.id)
      setData((prev) =>
        prev
          ? { ...prev, items: prev.items.filter((p) => p.id !== person.id), total: prev.total - 1 }
          : prev
      )
    } catch {
      alert('Silme işlemi sırasında hata oluştu.')
    }
  }

  const openCreate = () => {
    setEditPerson(undefined)
    setModalOpen(true)
  }

  const openEdit = (person: Person, e: React.MouseEvent) => {
    e.stopPropagation()
    setEditPerson(person)
    setModalOpen(true)
  }

  const totalPages = data ? Math.ceil(data.total / PAGE_SIZE) : 0
  const currentPage = Math.floor(skip / PAGE_SIZE) + 1

  return (
    <AppShell title="Kişiler">
      <div className="page-header">
        <h1 className="page-title">Kişiler</h1>
        <button className="btn btn-primary" onClick={openCreate}>
          + Yeni Kişi
        </button>
      </div>

      {/* Filter bar */}
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
          style={{ width: 'auto', minWidth: 140 }}
          value={roleFilter}
          onChange={(e) => setRoleFilter(e.target.value)}
        >
          <option value="">Tüm Roller</option>
          <option value="sporcu">Sporcu</option>
          <option value="uye">Üye</option>
          <option value="veli">Veli</option>
          <option value="antrenor">Antrenör</option>
          <option value="personel">Personel</option>
          <option value="misafir">Misafir</option>
        </select>

        <select
          className="form-select"
          style={{ width: 'auto', minWidth: 120 }}
          value={activeFilter}
          onChange={(e) => setActiveFilter(e.target.value)}
        >
          <option value="">Tüm Durum</option>
          <option value="true">Aktif</option>
          <option value="false">Pasif</option>
        </select>
      </div>

      {/* Error */}
      {error && (
        <div className="alert alert-error">
          <span>⚠️</span>
          <span>{error}</span>
        </div>
      )}

      {/* Table */}
      <div className="table-container">
        {loading ? (
          <div className="loading-center">
            <span className="loading-spinner lg" />
          </div>
        ) : !data || data.items.length === 0 ? (
          <div className="empty-state">
            <div className="empty-state-icon">👥</div>
            <div className="empty-state-title">Kişi Bulunamadı</div>
            <div className="empty-state-desc">
              {search || roleFilter || activeFilter
                ? 'Arama kriterlerinize uyan kişi bulunamadı.'
                : 'Henüz kayıtlı kişi yok. Yeni kişi ekleyin.'}
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
                  <th>Roller</th>
                  <th>Durum</th>
                  <th>İşlemler</th>
                </tr>
              </thead>
              <tbody>
                {data.items.map((person) => (
                  <tr
                    key={person.id}
                    onClick={() => navigate(`/persons/${person.id}`)}
                  >
                    <td>
                      <strong>
                        {person.first_name} {person.last_name}
                      </strong>
                    </td>
                    <td>{person.phone ?? '—'}</td>
                    <td>{person.email ?? '—'}</td>
                    <td>
                      <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
                        {person.role_codes.length > 0
                          ? person.role_codes.map((code) => (
                              <RoleBadge key={code} code={code} />
                            ))
                          : '—'}
                      </div>
                    </td>
                    <td>
                      <span
                        className={`badge ${person.is_active ? 'badge-aktif' : 'badge-pasif'}`}
                      >
                        {person.is_active ? 'Aktif' : 'Pasif'}
                      </span>
                    </td>
                    <td>
                      <div style={{ display: 'flex', gap: 6 }}>
                        <button
                          className="btn btn-sm btn-secondary"
                          onClick={(e) => openEdit(person, e)}
                        >
                          Düzenle
                        </button>
                        <button
                          className="btn btn-sm btn-ghost"
                          onClick={(e) => handleDeactivate(person, e)}
                          title={person.is_active ? 'Pasife Al' : 'Aktife Al'}
                        >
                          {person.is_active ? '⏸' : '▶'}
                        </button>
                        <button
                          className="btn btn-sm btn-danger"
                          onClick={(e) => handleDelete(person, e)}
                          title="Sil"
                        >
                          🗑
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>

            {/* Pagination */}
            {data.total > PAGE_SIZE && (
              <div className="pagination">
                <span>
                  {data.total} kişiden {skip + 1}–{Math.min(skip + PAGE_SIZE, data.total)} arası
                  gösteriliyor
                </span>
                <div className="pagination-controls">
                  <button
                    className="btn btn-sm btn-secondary"
                    disabled={skip === 0}
                    onClick={() => setSkip((s) => Math.max(0, s - PAGE_SIZE))}
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
        isOpen={modalOpen}
        onClose={() => setModalOpen(false)}
        person={editPerson}
        onSaved={handleSaved}
      />
    </AppShell>
  )
}
