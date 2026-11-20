import { useEffect, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import AppShell from '@/components/layout/AppShell'
import PersonFormModal from './PersonFormModal'
import { useAuth } from '@/hooks/useAuth'
import { ADMIN, isRouteAllowed } from '@/config/access'
import { PERSON_FILTERS, PERSON_PAGE_SIZE, personFilters, personListParams } from './personFilters'
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

const PAGE_SIZE = PERSON_PAGE_SIZE
const PROFILE_PATHS: Partial<Record<PersonRoleCode, string>> = { sporcu: '/sporcular', veli: '/veliler', uye: '/uyeler', antrenor: '/antrenorler' }

function RoleBadge({ code, personId, userRole }: { code: PersonRoleCode; personId: string; userRole: string }) {
  const path = PROFILE_PATHS[code]
  return path && isRouteAllowed(path, userRole)
    ? <Link className={`badge badge-${code}`} to={`${path}/${personId}`} onClick={(e) => e.stopPropagation()} title={`${ROLE_LABELS[code]} ayrıntılarını aç`}>{ROLE_LABELS[code]}</Link>
    : <span className={`badge badge-${code}`}>{ROLE_LABELS[code] ?? code}</span>
}

export default function PersonsPage() {
  const navigate = useNavigate()
  const { user } = useAuth()
  const canWrite = ADMIN.includes(user?.role ?? '')
  const [params, setParams] = useSearchParams()
  const { search, role: roleFilter, active: activeFilter, skip } = personFilters(params)
  const [refresh, setRefresh] = useState(0)
  const filterPath = PROFILE_PATHS[roleFilter as PersonRoleCode]
  const changeFilter = (key: string, value: string) => setParams((old) => {
    const next = new URLSearchParams(old)
    if (value) next.set(key, value); else next.delete(key)
    next.delete('page')
    return next
  }, { replace: key === 'q' })
  const changePage = (nextSkip: number) => setParams((old) => {
    const next = new URLSearchParams(old)
    if (nextSkip) next.set('page', String(nextSkip / PAGE_SIZE + 1)); else next.delete('page')
    return next
  })
  const [data, setData] = useState<PersonListResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const [modalOpen, setModalOpen] = useState(false)
  const [editPerson, setEditPerson] = useState<Person | undefined>(undefined)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)
    const requestParams = personListParams(new URLSearchParams({ q: search, role: roleFilter, active: activeFilter, page: String(skip / PAGE_SIZE + 1) }))
    const timer = setTimeout(async () => {
      try {
        const response = await personsApi.list(requestParams)
        if (cancelled) return
        if (skip > 0 && skip >= response.data.total) {
          const lastPage = Math.max(1, Math.ceil(response.data.total / PAGE_SIZE))
          setParams((old) => { const next = new URLSearchParams(old); if (lastPage > 1) next.set('page', String(lastPage)); else next.delete('page'); return next }, { replace: true })
          return
        }
        setData(response.data)
      } catch { if (!cancelled) setError('Kişi rehberi yüklenemedi.') }
      finally { if (!cancelled) setLoading(false) }
    }, 300)
    return () => { cancelled = true; clearTimeout(timer) }
  }, [search, roleFilter, activeFilter, skip, refresh, setParams])

  const handleSaved = () => setRefresh((value) => value + 1)

  const handleDeactivate = async (person: Person, e: React.MouseEvent) => {
    e.stopPropagation()
    if (!window.confirm(`${person.first_name} ${person.last_name} kişisini ${person.is_active ? 'pasife' : 'aktife'} almak istiyor musunuz?`))
      return
    try {
      await personsApi.update(person.id, { is_active: !person.is_active })
      setRefresh((value) => value + 1)
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
      setRefresh((value) => value + 1)
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
    <AppShell title="Kişi Rehberi">
      <div className="page-header">
        <div><h1 className="page-title">Kişi Rehberi</h1><p>Kişi türünü seçerek listeyi daraltın. Bir kişi birden fazla grupta yer alabilir.</p></div>
        {canWrite && <button className="btn btn-primary" onClick={openCreate}>
          + Yeni Kişi
        </button>}
      </div>

      <div className="person-role-filters" role="group" aria-label="Kişi türü">
        {PERSON_FILTERS.map((filter) => <button type="button" key={filter.value} className={`person-role-filter${roleFilter === filter.value ? ' selected' : ''}`} aria-pressed={roleFilter === filter.value} onClick={() => changeFilter('role', filter.value)}>{filter.label}</button>)}
      </div>
      {/* Filter bar */}
      <div className="filter-bar">
        <div className="filter-search">
          <span className="filter-search-icon">🔍</span>
          <input
            type="text"
            className="filter-search-input"
            placeholder="Ad, soyad, e-posta veya telefon ara..."
            aria-label="Kişi ara"
            value={search}
            onChange={(e) => changeFilter('q', e.target.value)}
          />
        </div>

        <select
          className="form-select"
          style={{ width: 'auto', minWidth: 120 }}
          aria-label="Kişi durumu"
          value={activeFilter}
          onChange={(e) => changeFilter('active', e.target.value)}
        >
          <option value="">Tüm Durum</option>
          <option value="true">Aktif</option>
          <option value="false">Pasif</option>
        </select>
      </div>

      <div className="directory-context">
        <p role="status">{loading ? 'Kişiler yükleniyor…' : error ? '' : `${data?.total ?? 0} kişi${roleFilter ? ` · ${ROLE_LABELS[roleFilter as PersonRoleCode]}` : ''}`}</p>
        {filterPath && isRouteAllowed(filterPath, user?.role ?? '') && <Link className="btn btn-sm btn-secondary" to={filterPath}>{ROLE_LABELS[roleFilter as PersonRoleCode]} İşlemlerini Aç</Link>}
      </div>
      {/* Error */}
      {error && (
        <div className="alert alert-error" role="alert">
          <span>⚠️</span>
          <span>{error}</span><button className="btn btn-sm btn-ghost" onClick={() => setRefresh((value) => value + 1)}>Tekrar Dene</button>
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
                  <th>Kişi Türü</th>
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
                              <RoleBadge key={code} code={code} personId={person.id} userRole={user?.role ?? ''} />
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
                      {canWrite && <div style={{ display: 'flex', gap: 6 }}>
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
                      </div>}
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
                    onClick={() => changePage(Math.max(0, skip - PAGE_SIZE))}
                  >
                    ← Önceki
                  </button>
                  <span style={{ padding: '5px 10px', fontSize: 13 }}>
                    {currentPage} / {totalPages}
                  </span>
                  <button
                    className="btn btn-sm btn-secondary"
                    disabled={skip + PAGE_SIZE >= data.total}
                    onClick={() => changePage(skip + PAGE_SIZE)}
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
