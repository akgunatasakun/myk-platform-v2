/**
 * /ayarlar — Kulüp Ayarları
 *
 * Sekmeler:
 *   🏢 Kulüp Bilgileri   → GET/PATCH /api/v1/settings/club
 *   ⛵ Spor Branşları    → GET/POST/PATCH /api/v1/settings/branches
 *
 * Yetkiler: kulup:read / kulup:write (kulup_yonetici veya super_admin)
 */
import { useEffect, useState } from 'react'
import AppShell from '@/components/layout/AppShell'
import { settingsApi } from '@/api/settings'
import type { Branch, ClubSettings } from '@/types/settings'

type Tab = 'club' | 'branches'

const CURRENCY_LABELS: Record<string, string> = {
  TRY: '₺ Türk Lirası',
  EUR: '€ Euro',
  USD: '$ Dolar',
}

// ── Kulüp Bilgileri Formu ─────────────────────────────────────────────────────

interface ClubFormState {
  name: string
  phone: string
  email: string
  website: string
  address: string
  timezone: string
  currency: string
}

function clubToForm(c: ClubSettings): ClubFormState {
  return {
    name: c.name,
    phone: c.phone ?? '',
    email: c.email ?? '',
    website: c.website ?? '',
    address: c.address ?? '',
    timezone: c.timezone,
    currency: c.currency,
  }
}

interface ClubTabProps {
  club: ClubSettings
  onSaved: (updated: ClubSettings) => void
}

function ClubTab({ club, onSaved }: ClubTabProps) {
  const [form, setForm] = useState<ClubFormState>(clubToForm(club))
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState(false)

  useEffect(() => {
    setForm(clubToForm(club))
  }, [club])

  const set = (field: keyof ClubFormState) => (
    e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>
  ) => setForm((f) => ({ ...f, [field]: e.target.value }))

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setSaving(true)
    setError(null)
    setSuccess(false)

    try {
      const payload: Record<string, string> = {}
      if (form.name.trim())     payload.name     = form.name.trim()
      if (form.phone.trim())    payload.phone    = form.phone.trim()
      if (form.email.trim())    payload.email    = form.email.trim()
      if (form.website.trim())  payload.website  = form.website.trim()
      if (form.address.trim())  payload.address  = form.address.trim()
      if (form.timezone.trim()) payload.timezone = form.timezone.trim()
      if (form.currency)        payload.currency = form.currency

      const resp = await settingsApi.updateClub(payload)
      onSaved(resp.data)
      setSuccess(true)
      setTimeout(() => setSuccess(false), 3000)
    } catch {
      setError('Ayarlar kaydedilemedi. Lütfen tekrar deneyin.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <form onSubmit={handleSubmit}>
      {/* Salt okunur bilgiler */}
      <div className="card" style={{ marginBottom: 20 }}>
        <div className="card-header">Kulüp Kimliği</div>
        <div className="card-body">
          <div className="detail-grid">
            <div className="detail-item">
              <span className="detail-label">Kulüp ID</span>
              <span
                className="detail-value"
                style={{ fontFamily: 'monospace', fontSize: 12 }}
              >
                {club.id}
              </span>
            </div>
            <div className="detail-item">
              <span className="detail-label">Slug</span>
              <span
                className="detail-value"
                style={{ fontFamily: 'monospace' }}
              >
                {club.slug}
              </span>
            </div>
            <div className="detail-item">
              <span className="detail-label">Plan</span>
              <span className="detail-value">
                <span
                  className="badge"
                  style={{ background: '#f0fdf4', color: '#166534', textTransform: 'capitalize' }}
                >
                  {club.plan}
                </span>
              </span>
            </div>
            <div className="detail-item">
              <span className="detail-label">Oluşturulma</span>
              <span className="detail-value">
                {new Date(club.created_at).toLocaleDateString('tr-TR')}
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Düzenlenebilir alanlar */}
      <div className="card" style={{ marginBottom: 20 }}>
        <div className="card-header">Temel Bilgiler</div>
        <div className="card-body">
          <div className="form-group">
            <label className="form-label">Kulüp Adı *</label>
            <input
              className="form-input"
              value={form.name}
              onChange={set('name')}
              required
              maxLength={200}
            />
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginTop: 16 }}>
            <div className="form-group">
              <label className="form-label">Telefon</label>
              <input
                className="form-input"
                value={form.phone}
                onChange={set('phone')}
                placeholder="+90 (000) 000 00 00"
                maxLength={30}
              />
            </div>
            <div className="form-group">
              <label className="form-label">E-posta</label>
              <input
                className="form-input"
                type="email"
                value={form.email}
                onChange={set('email')}
                placeholder="info@kulup.org.tr"
                maxLength={200}
              />
            </div>
            <div className="form-group">
              <label className="form-label">Web Sitesi</label>
              <input
                className="form-input"
                value={form.website}
                onChange={set('website')}
                placeholder="https://kulup.org.tr"
                maxLength={200}
              />
            </div>
          </div>

          <div className="form-group" style={{ marginTop: 16 }}>
            <label className="form-label">Adres</label>
            <textarea
              className="form-input"
              style={{ resize: 'vertical', minHeight: 72 }}
              value={form.address}
              onChange={set('address')}
              rows={3}
              maxLength={500}
            />
          </div>
        </div>
      </div>

      <div className="card" style={{ marginBottom: 20 }}>
        <div className="card-header">Bölgesel Ayarlar</div>
        <div className="card-body">
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
            <div className="form-group">
              <label className="form-label">Saat Dilimi</label>
              <select
                className="form-select"
                value={form.timezone}
                onChange={set('timezone')}
              >
                <option value="Europe/Istanbul">Europe/Istanbul (UTC+3)</option>
                <option value="Europe/London">Europe/London (UTC+0)</option>
                <option value="Europe/Berlin">Europe/Berlin (UTC+1/+2)</option>
                <option value="UTC">UTC</option>
              </select>
            </div>
            <div className="form-group">
              <label className="form-label">Para Birimi</label>
              <select
                className="form-select"
                value={form.currency}
                onChange={set('currency')}
              >
                {Object.entries(CURRENCY_LABELS).map(([code, label]) => (
                  <option key={code} value={code}>
                    {label}
                  </option>
                ))}
              </select>
            </div>
          </div>
        </div>
      </div>

      {error && (
        <div className="alert alert-error" style={{ marginBottom: 16 }}>
          <span>⚠️</span>
          <span>{error}</span>
        </div>
      )}
      {success && (
        <div className="alert alert-success" style={{ marginBottom: 16 }}>
          <span>✅</span>
          <span>Kulüp ayarları kaydedildi.</span>
        </div>
      )}

      <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
        <button
          type="submit"
          className="btn btn-primary"
          disabled={saving}
        >
          {saving ? 'Kaydediliyor…' : 'Kaydet'}
        </button>
      </div>
    </form>
  )
}

// ── Spor Branşları ────────────────────────────────────────────────────────────

interface BranchRowProps {
  branch: Branch
  onToggle: (id: string, active: boolean) => void
  onRename: (branch: Branch) => void
}

function BranchRow({ branch, onToggle, onRename }: BranchRowProps) {
  const [toggling, setToggling] = useState(false)

  const handleToggle = async () => {
    setToggling(true)
    await onToggle(branch.id, !branch.is_active)
    setToggling(false)
  }

  return (
    <tr>
      <td>
        <strong style={{ color: branch.is_active ? undefined : 'var(--color-text-muted)' }}>
          {branch.name}
        </strong>
      </td>
      <td style={{ textAlign: 'center' }}>{branch.sort_order}</td>
      <td>
        <span className={`badge ${branch.is_active ? 'badge-aktif' : 'badge-pasif'}`}>
          {branch.is_active ? 'Aktif' : 'Pasif'}
        </span>
      </td>
      <td>
        <div style={{ display: 'flex', gap: 8 }}>
          <button
            className="btn btn-ghost btn-sm"
            onClick={() => onRename(branch)}
          >
            Düzenle
          </button>
          <button
            className="btn btn-ghost btn-sm"
            onClick={handleToggle}
            disabled={toggling}
          >
            {branch.is_active ? 'Pasife Al' : 'Aktife Al'}
          </button>
        </div>
      </td>
    </tr>
  )
}

interface BranchesTabProps {
  branches: Branch[]
  onRefresh: () => void
}

function BranchesTab({ branches, onRefresh }: BranchesTabProps) {
  const [addMode, setAddMode] = useState(false)
  const [newName, setNewName] = useState('')
  const [newOrder, setNewOrder] = useState('0')
  const [addLoading, setAddLoading] = useState(false)
  const [addError, setAddError] = useState<string | null>(null)

  const [editBranch, setEditBranch] = useState<Branch | null>(null)
  const [editName, setEditName] = useState('')
  const [editOrder, setEditOrder] = useState('0')
  const [editLoading, setEditLoading] = useState(false)
  const [editError, setEditError] = useState<string | null>(null)

  const handleAdd = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!newName.trim()) return
    setAddLoading(true)
    setAddError(null)
    try {
      await settingsApi.createBranch({ name: newName.trim(), sort_order: parseInt(newOrder, 10) || 0 })
      setNewName('')
      setNewOrder('0')
      setAddMode(false)
      onRefresh()
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
        'Branş oluşturulamadı.'
      setAddError(msg)
    } finally {
      setAddLoading(false)
    }
  }

  const handleToggle = async (id: string, active: boolean) => {
    try {
      await settingsApi.updateBranch(id, { is_active: active })
      onRefresh()
    } catch {
      // sessiz hata; kullanıcı tekrar deneyebilir
    }
  }

  const openEdit = (branch: Branch) => {
    setEditBranch(branch)
    setEditName(branch.name)
    setEditOrder(String(branch.sort_order))
    setEditError(null)
  }

  const handleEdit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!editBranch) return
    setEditLoading(true)
    setEditError(null)
    try {
      await settingsApi.updateBranch(editBranch.id, {
        name: editName.trim(),
        sort_order: parseInt(editOrder, 10) || 0,
      })
      setEditBranch(null)
      onRefresh()
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
        'Branş güncellenemedi.'
      setEditError(msg)
    } finally {
      setEditLoading(false)
    }
  }

  return (
    <>
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginBottom: 16,
        }}
      >
        <span style={{ color: 'var(--color-text-muted)', fontSize: 14 }}>
          {branches.length} branş kayıtlı
        </span>
        <button
          className="btn btn-primary btn-sm"
          onClick={() => { setAddMode(true); setAddError(null) }}
        >
          + Yeni Branş
        </button>
      </div>

      {/* Yeni branş formu */}
      {addMode && (
        <div className="card" style={{ marginBottom: 16, border: '2px solid var(--color-primary)' }}>
          <div className="card-header">Yeni Spor Branşı</div>
          <div className="card-body">
            <form onSubmit={handleAdd}>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr auto', gap: 12, alignItems: 'flex-end' }}>
                <div className="form-group" style={{ margin: 0 }}>
                  <label className="form-label">Branş Adı *</label>
                  <input
                    className="form-input"
                    value={newName}
                    onChange={(e) => setNewName(e.target.value)}
                    placeholder="örn. Yelken, Kürek, Yüzme"
                    autoFocus
                    maxLength={100}
                    required
                  />
                </div>
                <div className="form-group" style={{ margin: 0, width: 100 }}>
                  <label className="form-label">Sıra</label>
                  <input
                    className="form-input"
                    type="number"
                    value={newOrder}
                    onChange={(e) => setNewOrder(e.target.value)}
                    min={0}
                    max={9999}
                  />
                </div>
              </div>
              {addError && (
                <div className="alert alert-error" style={{ marginTop: 12 }}>
                  <span>⚠️</span>
                  <span>{addError}</span>
                </div>
              )}
              <div style={{ display: 'flex', gap: 8, marginTop: 12, justifyContent: 'flex-end' }}>
                <button
                  type="button"
                  className="btn btn-ghost btn-sm"
                  onClick={() => { setAddMode(false); setNewName(''); setAddError(null) }}
                >
                  İptal
                </button>
                <button
                  type="submit"
                  className="btn btn-primary btn-sm"
                  disabled={addLoading || !newName.trim()}
                >
                  {addLoading ? 'Ekleniyor…' : 'Ekle'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Düzenleme modalı */}
      {editBranch && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            background: 'rgba(0,0,0,0.4)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 1000,
          }}
        >
          <div
            style={{
              background: 'var(--color-surface)',
              borderRadius: 12,
              padding: 24,
              width: 400,
              maxWidth: '90vw',
            }}
          >
            <h3 style={{ margin: '0 0 20px', fontSize: 16, fontWeight: 600 }}>
              Branş Düzenle
            </h3>
            <form onSubmit={handleEdit}>
              <div className="form-group">
                <label className="form-label">Branş Adı *</label>
                <input
                  className="form-input"
                  value={editName}
                  onChange={(e) => setEditName(e.target.value)}
                  maxLength={100}
                  required
                  autoFocus
                />
              </div>
              <div className="form-group">
                <label className="form-label">Sıra</label>
                <input
                  className="form-input"
                  type="number"
                  value={editOrder}
                  onChange={(e) => setEditOrder(e.target.value)}
                  min={0}
                  max={9999}
                />
              </div>
              {editError && (
                <div className="alert alert-error" style={{ marginBottom: 12 }}>
                  <span>⚠️</span>
                  <span>{editError}</span>
                </div>
              )}
              <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
                <button
                  type="button"
                  className="btn btn-ghost btn-sm"
                  onClick={() => { setEditBranch(null); setEditError(null) }}
                >
                  İptal
                </button>
                <button
                  type="submit"
                  className="btn btn-primary btn-sm"
                  disabled={editLoading || !editName.trim()}
                >
                  {editLoading ? 'Kaydediliyor…' : 'Kaydet'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Branş tablosu */}
      <div className="table-container">
        {branches.length === 0 ? (
          <div className="empty-state">
            <div className="empty-state-icon">⛵</div>
            <div className="empty-state-title">Henüz branş yok</div>
            <div className="empty-state-desc">
              Spor branşı eklemek için &ldquo;+ Yeni Branş&rdquo; butonunu kullanın.
            </div>
          </div>
        ) : (
          <table className="data-table">
            <thead>
              <tr>
                <th>Branş Adı</th>
                <th style={{ textAlign: 'center', width: 80 }}>Sıra</th>
                <th style={{ width: 100 }}>Durum</th>
                <th style={{ width: 160 }}>İşlemler</th>
              </tr>
            </thead>
            <tbody>
              {branches.map((b) => (
                <BranchRow
                  key={b.id}
                  branch={b}
                  onToggle={handleToggle}
                  onRename={openEdit}
                />
              ))}
            </tbody>
          </table>
        )}
      </div>
    </>
  )
}

// ── Ana sayfa ─────────────────────────────────────────────────────────────────

export default function SettingsPage() {
  const [activeTab, setActiveTab] = useState<Tab>('club')

  const [club, setClub] = useState<ClubSettings | null>(null)
  const [branches, setBranches] = useState<Branch[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const fetchAll = async () => {
    setLoading(true)
    setError(null)
    try {
      const [clubResp, branchResp] = await Promise.all([
        settingsApi.getClub(),
        settingsApi.getBranches(),
      ])
      setClub(clubResp.data)
      setBranches(branchResp.data)
    } catch {
      setError('Ayarlar yüklenemedi. Yeterli yetkiniz olmayabilir.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchAll()
  }, [])

  const refreshBranches = async () => {
    try {
      const resp = await settingsApi.getBranches()
      setBranches(resp.data)
    } catch {
      // sessiz
    }
  }

  return (
    <AppShell title="Ayarlar">
      <div className="page-header">
        <h1 className="page-title">Kulüp Ayarları</h1>
      </div>

      {/* Sekmeler */}
      <div
        style={{
          display: 'flex',
          gap: 0,
          borderBottom: '2px solid var(--color-border)',
          marginBottom: 24,
        }}
      >
        {(
          [
            { key: 'club', label: '🏢 Kulüp Bilgileri' },
            { key: 'branches', label: '⛵ Spor Branşları' },
          ] as { key: Tab; label: string }[]
        ).map(({ key, label }) => (
          <button
            key={key}
            onClick={() => setActiveTab(key)}
            style={{
              background: 'none',
              border: 'none',
              padding: '10px 20px',
              cursor: 'pointer',
              fontSize: 14,
              fontWeight: activeTab === key ? 700 : 400,
              color: activeTab === key ? 'var(--color-primary)' : 'var(--color-text-muted)',
              borderBottom: activeTab === key
                ? '2px solid var(--color-primary)'
                : '2px solid transparent',
              marginBottom: -2,
            }}
          >
            {label}
          </button>
        ))}
      </div>

      {loading && (
        <div className="loading-center">
          <span className="loading-spinner lg" />
        </div>
      )}

      {error && !loading && (
        <div className="alert alert-error">
          <span>⚠️</span>
          <span>{error}</span>
        </div>
      )}

      {!loading && !error && club && (
        <>
          {activeTab === 'club' && (
            <ClubTab
              club={club}
              onSaved={(updated) => setClub(updated)}
            />
          )}
          {activeTab === 'branches' && (
            <BranchesTab
              branches={branches}
              onRefresh={refreshBranches}
            />
          )}
        </>
      )}
    </AppShell>
  )
}
