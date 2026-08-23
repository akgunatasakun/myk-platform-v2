import { useCallback, useEffect, useRef, useState } from 'react'
import AppShell from '@/components/layout/AppShell'
import UserFormModal from './UserFormModal'
import { usersApi } from '@/api/users'
import type { UserListItem, UserListOut, UserOut } from '@/types/user'
import type { Role } from '@/types/auth'

const ROLE_LABELS: Partial<Record<Role, string>> = {
  super_admin: 'Süper Admin',
  kulup_yonetici: 'Kulüp Yöneticisi',
  genel_sekreter: 'Genel Sekreter',
  baskan: 'Başkan',
  yk_uyesi: 'YK Üyesi',
  muhasebe: 'Muhasebe',
  sportif_direktor: 'Sportif Direktör',
  basantrenor: 'Baş Antrenör',
  antrenor: 'Antrenör',
  personel: 'Personel',
  saglik_sorumlusu: 'Sağlık Sorumlusu',
  guvenlik_operasyon: 'Güvenlik / Operasyon',
  veli: 'Veli',
  sporcu: 'Sporcu',
  uye: 'Üye',
  misafir: 'Misafir',
}

const PAGE_SIZE = 20

export default function UsersPage() {
  const [data, setData] = useState<UserListOut | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const [search, setSearch] = useState('')
  const [roleFilter, setRoleFilter] = useState('')
  const [activeFilter, setActiveFilter] = useState('')
  const [skip, setSkip] = useState(0)

  const [modalOpen, setModalOpen] = useState(false)
  const [editUser, setEditUser] = useState<UserOut | undefined>(undefined)

  // G5: Geçici parola bir kez gösterilir
  const [tempPassword, setTempPassword] = useState<string | null>(null)

  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const fetchUsers = useCallback(
    async (searchVal: string, role: string, active: string, skipVal: number) => {
      setLoading(true)
      setError(null)
      try {
        const params: Record<string, unknown> = { skip: skipVal, limit: PAGE_SIZE }
        if (searchVal) params.search = searchVal
        if (role) params.role = role
        if (active !== '') params.is_active = active === 'true'

        const resp = await usersApi.list(params)
        setData(resp.data)
      } catch {
        setError('Kullanıcılar yüklenemedi.')
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
      fetchUsers(search, roleFilter, activeFilter, 0)
    }, 300)
    return () => { if (debounceRef.current) clearTimeout(debounceRef.current) }
  }, [search, roleFilter, activeFilter, fetchUsers])

  useEffect(() => {
    fetchUsers(search, roleFilter, activeFilter, skip)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [skip])

  const handleSaved = (saved: UserOut) => {
    setData((prev) => {
      if (!prev) return prev
      const exists = prev.items.some((u) => u.id === saved.id)
      if (exists) {
        return { ...prev, items: prev.items.map((u) => (u.id === saved.id ? saved : u)) }
      }
      return { ...prev, items: [saved, ...prev.items], total: prev.total + 1 }
    })
  }

  const handleDelete = async (user: UserListItem, e: React.MouseEvent) => {
    e.stopPropagation()
    if (!window.confirm(`${user.full_name} kullanıcısını silmek istiyor musunuz?`)) return
    try {
      await usersApi.delete(user.id)
      setData((prev) =>
        prev ? { ...prev, items: prev.items.filter((u) => u.id !== user.id), total: prev.total - 1 } : prev
      )
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? 'Silme işlemi başarısız.'
      alert(msg)
    }
  }

  const handleResetPassword = async (user: UserListItem, e: React.MouseEvent) => {
    e.stopPropagation()
    if (!window.confirm(`${user.full_name} kullanıcısının parolasını sıfırlamak istiyor musunuz?`)) return
    try {
      const resp = await usersApi.resetPassword(user.id)
      setTempPassword(resp.data.temp_password)
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? 'Parola sıfırlama başarısız.'
      alert(msg)
    }
  }

  const openCreate = () => {
    setEditUser(undefined)
    setModalOpen(true)
  }

  const openEdit = async (item: UserListItem, e: React.MouseEvent) => {
    e.stopPropagation()
    try {
      const resp = await usersApi.get(item.id)
      setEditUser(resp.data)
      setModalOpen(true)
    } catch {
      alert('Kullanıcı bilgileri yüklenemedi.')
    }
  }

  const totalPages = data ? Math.ceil(data.total / PAGE_SIZE) : 0
  const currentPage = Math.floor(skip / PAGE_SIZE) + 1

  return (
    <AppShell title="Kullanıcılar">
      {/* G5: Geçici parola uyarısı */}
      {tempPassword && (
        <div className="alert alert-warning" style={{ marginBottom: 16 }}>
          <strong>Geçici Parola (yalnızca bir kez görüntülenir):</strong>{' '}
          <code style={{ fontSize: 16, letterSpacing: 1 }}>{tempPassword}</code>
          {' '}
          <button
            className="btn btn-sm btn-secondary"
            onClick={() => { navigator.clipboard.writeText(tempPassword); }}
          >
            Kopyala
          </button>
          {' '}
          <button className="btn btn-sm btn-secondary" onClick={() => setTempPassword(null)}>
            Kapat
          </button>
        </div>
      )}

      <div className="page-header">
        <h1 className="page-title">Kullanıcılar</h1>
        <button className="btn btn-primary" onClick={openCreate}>
          + Yeni Kullanıcı
        </button>
      </div>

      {/* Filter bar */}
      <div className="filter-bar">
        <div className="filter-search">
          <span className="filter-search-icon">🔍</span>
          <input
            type="text"
            className="filter-search-input"
            placeholder="Ad veya e-posta ara..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>

        <select
          className="form-select"
          style={{ width: 'auto', minWidth: 160 }}
          value={roleFilter}
          onChange={(e) => setRoleFilter(e.target.value)}
        >
          <option value="">Tüm Roller</option>
          {Object.entries(ROLE_LABELS).map(([val, label]) => (
            <option key={val} value={val}>{label}</option>
          ))}
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

      {error && (
        <div className="alert alert-error">
          <span>⚠️</span><span>{error}</span>
        </div>
      )}

      <div className="table-container">
        {loading ? (
          <div className="loading-center"><span className="loading-spinner lg" /></div>
        ) : !data || data.items.length === 0 ? (
          <div className="empty-state">
            <div className="empty-state-icon">👤</div>
            <div className="empty-state-title">Kullanıcı Bulunamadı</div>
            <div className="empty-state-desc">
              {search || roleFilter || activeFilter
                ? 'Arama kriterlerinize uyan kullanıcı bulunamadı.'
                : 'Henüz kayıtlı kullanıcı yok. Yeni kullanıcı ekleyin.'}
            </div>
          </div>
        ) : (
          <>
            <table className="data-table">
              <thead>
                <tr>
                  <th>Ad Soyad</th>
                  <th>E-posta</th>
                  <th>Rol</th>
                  <th>Durum</th>
                  <th>Son Giriş</th>
                  <th>İşlemler</th>
                </tr>
              </thead>
              <tbody>
                {data.items.map((user) => (
                  <tr key={user.id}>
                    <td>
                      <strong>{user.full_name}</strong>
                    </td>
                    <td>{user.email}</td>
                    <td>
                      <span className="badge badge-uye">
                        {ROLE_LABELS[user.role] ?? user.role}
                      </span>
                    </td>
                    <td>
                      {user.is_active ? (
                        <span className="badge badge-active">Aktif</span>
                      ) : (
                        <span className="badge badge-inactive">Pasif</span>
                      )}
                    </td>
                    <td>
                      {user.last_login_at
                        ? new Date(user.last_login_at).toLocaleDateString('tr-TR')
                        : '—'}
                    </td>
                    <td>
                      <div className="action-buttons">
                        <button
                          className="btn btn-sm btn-secondary"
                          onClick={(e) => openEdit(user, e)}
                          title="Düzenle"
                        >
                          ✏️
                        </button>
                        <button
                          className="btn btn-sm btn-secondary"
                          onClick={(e) => handleResetPassword(user, e)}
                          title="Parola Sıfırla"
                        >
                          🔑
                        </button>
                        <button
                          className="btn btn-sm btn-danger"
                          onClick={(e) => handleDelete(user, e)}
                          title="Sil"
                        >
                          🗑️
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>

            {/* Pagination */}
            {totalPages > 1 && (
              <div className="pagination">
                <button
                  className="btn btn-sm btn-secondary"
                  disabled={currentPage === 1}
                  onClick={() => setSkip((p) => Math.max(0, p - PAGE_SIZE))}
                >
                  ←
                </button>
                <span className="pagination-info">
                  {currentPage} / {totalPages} ({data.total} kayıt)
                </span>
                <button
                  className="btn btn-sm btn-secondary"
                  disabled={currentPage >= totalPages}
                  onClick={() => setSkip((p) => p + PAGE_SIZE)}
                >
                  →
                </button>
              </div>
            )}
          </>
        )}
      </div>

      <UserFormModal
        isOpen={modalOpen}
        onClose={() => setModalOpen(false)}
        user={editUser}
        onSaved={handleSaved}
        onCreated={(pw) => setTempPassword(pw)}
      />
    </AppShell>
  )
}
