/**
 * Veliler / Vasiler bölümü — PersonDetailPage içinde kullanılır.
 *
 * Özellikler:
 * - Mevcut velileri listeler (is_primary önce, sonra oluşturma tarihi)
 * - "Veli Ekle": kişi arama + alan doldurma modal'ı
 * - "Düzenle": relationship_type, is_primary, can_pickup, can_receive_notifications PATCH
 * - "Sil": onay → DELETE
 * - is_primary atandığında backend mevcut primary'yi kaldırır → liste yenilenir
 * - 409 (duplicate) ve 422 (self-ref) API hataları kullanıcıya anlaşılır gösterilir
 * - loading / empty / error durumları
 */
import { useCallback, useEffect, useRef, useState } from 'react'
import { personsApi } from '@/api/persons'
import type { Person } from '@/types/person'
import type { PersonGuardian, PersonGuardianCreate, PersonGuardianUpdate } from '@/types/guardian'

// ─── Sabitler ────────────────────────────────────────────────────────────────

const RELATIONSHIP_OPTIONS = [
  { value: '', label: '— Seçiniz —' },
  { value: 'anne', label: 'Anne' },
  { value: 'baba', label: 'Baba' },
  { value: 'vasi', label: 'Vasi' },
  { value: 'dede', label: 'Dede' },
  { value: 'nine', label: 'Nine' },
  { value: 'abla', label: 'Abla' },
  { value: 'agabey', label: 'Ağabey' },
  { value: 'diger', label: 'Diğer' },
]

// ─── Yardımcılar ──────────────────────────────────────────────────────────────

function extractDetail(err: unknown): string {
  const data = (err as { response?: { data?: { detail?: unknown } } })?.response?.data
  const status = (err as { response?: { status?: number } })?.response?.status
  const detail = (data as { detail?: unknown })?.detail

  if (status === 409) return 'Bu kişi zaten bu sporcunun velisi olarak kayıtlı.'
  if (status === 422) {
    if (Array.isArray(detail)) {
      return detail.map((d: { msg?: string }) => d.msg ?? '').join(' ')
    }
    if (typeof detail === 'string') return detail
    return 'Geçersiz istek. Bilgileri kontrol edip tekrar deneyin.'
  }
  if (typeof detail === 'string') return detail
  return 'İşlem sırasında hata oluştu. Lütfen tekrar deneyin.'
}

function relLabel(val: string | null | undefined): string {
  if (!val) return '—'
  return RELATIONSHIP_OPTIONS.find((o) => o.value === val)?.label ?? val
}

// ─── "Veli Ekle" modal'ı ─────────────────────────────────────────────────────

interface AddGuardianModalProps {
  athleteId: string
  onClose: () => void
  onAdded: () => void
}

function AddGuardianModal({ athleteId, onClose, onAdded }: AddGuardianModalProps) {
  const [search, setSearch] = useState('')
  const [searchResults, setSearchResults] = useState<Person[]>([])
  const [searchLoading, setSearchLoading] = useState(false)
  const [selectedPerson, setSelectedPerson] = useState<Person | null>(null)
  const [showResults, setShowResults] = useState(false)

  const [relationshipType, setRelationshipType] = useState('')
  const [isPrimary, setIsPrimary] = useState(false)
  const [canPickup, setCanPickup] = useState(true)
  const [canReceiveNotifications, setCanReceiveNotifications] = useState(true)

  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const searchTimer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const overlayRef = useRef<HTMLDivElement>(null)

  const runSearch = useCallback(async (q: string) => {
    if (!q.trim()) { setSearchResults([]); setShowResults(false); return }
    setSearchLoading(true)
    try {
      const resp = await personsApi.list({ search: q.trim(), limit: 10 })
      setSearchResults(resp.data.items)
      setShowResults(true)
    } catch {
      setSearchResults([])
    } finally {
      setSearchLoading(false)
    }
  }, [])

  const handleSearchChange = (val: string) => {
    setSearch(val)
    if (selectedPerson) { setSelectedPerson(null) }
    if (searchTimer.current) clearTimeout(searchTimer.current)
    searchTimer.current = setTimeout(() => runSearch(val), 350)
  }

  const handleSelectPerson = (p: Person) => {
    setSelectedPerson(p)
    setSearch(`${p.first_name} ${p.last_name}`)
    setShowResults(false)
    setSearchResults([])
  }

  const handleSubmit = async () => {
    if (!selectedPerson) { setError('Lütfen bir kişi seçin.'); return }
    if (selectedPerson.id === athleteId) { setError('Sporcu kendi velisi olamaz.'); return }

    setSubmitting(true)
    setError(null)
    try {
      const payload: PersonGuardianCreate = {
        guardian_person_id: selectedPerson.id,
        relationship_type: relationshipType || null,
        is_primary: isPrimary,
        can_pickup: canPickup,
        can_receive_notifications: canReceiveNotifications,
      }
      await personsApi.addGuardian(athleteId, payload)
      onAdded()
    } catch (err) {
      setError(extractDetail(err))
    } finally {
      setSubmitting(false)
    }
  }

  // Overlay tıklamasında kapat
  const handleOverlayClick = (e: React.MouseEvent) => {
    if (e.target === overlayRef.current) onClose()
  }

  return (
    <div className="modal-overlay" ref={overlayRef} onClick={handleOverlayClick}>
      <div className="modal-box" style={{ maxWidth: 520 }}>
        <div className="modal-header">
          <span className="modal-title">Veli / Vasi Ekle</span>
          <button className="modal-close" onClick={onClose} aria-label="Kapat">✕</button>
        </div>
        <div className="modal-body" style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>

          {error && (
            <div className="alert alert-error">
              <span>⚠️</span>
              <span>{error}</span>
            </div>
          )}

          {/* Kişi arama */}
          <div style={{ position: 'relative' }}>
            <label className="form-label required">Kişi Ara</label>
            <input
              type="text"
              className="form-input"
              placeholder="Ad veya soyad ile ara…"
              value={search}
              onChange={(e) => handleSearchChange(e.target.value)}
              autoFocus
              autoComplete="off"
            />
            {searchLoading && (
              <span
                className="loading-spinner"
                style={{ position: 'absolute', right: 10, top: 34 }}
              />
            )}
            {showResults && searchResults.length > 0 && (
              <div className="guardian-search-dropdown">
                {searchResults.map((p) => (
                  <button
                    key={p.id}
                    type="button"
                    className="guardian-search-item"
                    onClick={() => handleSelectPerson(p)}
                  >
                    <span className="guardian-search-name">
                      {p.first_name} {p.last_name}
                    </span>
                    <span className="guardian-search-meta">
                      {p.member_number ?? p.email ?? '—'}
                    </span>
                  </button>
                ))}
              </div>
            )}
            {showResults && searchResults.length === 0 && !searchLoading && (
              <div className="guardian-search-dropdown">
                <div style={{ padding: '10px 12px', color: 'var(--color-muted)', fontSize: 13 }}>
                  Sonuç bulunamadı.
                </div>
              </div>
            )}
            {selectedPerson && (
              <div className="guardian-selected">
                <span>✓</span>
                <span>
                  <strong>{selectedPerson.first_name} {selectedPerson.last_name}</strong>
                  {selectedPerson.member_number && (
                    <span style={{ color: 'var(--color-muted)', marginLeft: 6 }}>
                      #{selectedPerson.member_number}
                    </span>
                  )}
                </span>
              </div>
            )}
          </div>

          {/* İlişki tipi */}
          <div>
            <label className="form-label">İlişki Tipi</label>
            <select
              className="form-select"
              value={relationshipType}
              onChange={(e) => setRelationshipType(e.target.value)}
            >
              {RELATIONSHIP_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>{o.label}</option>
              ))}
            </select>
          </div>

          {/* Checkbox'lar */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            <label className="guardian-checkbox-label">
              <input
                type="checkbox"
                checked={isPrimary}
                onChange={(e) => setIsPrimary(e.target.checked)}
              />
              <span>Birincil veli <span style={{ color: 'var(--color-muted)', fontSize: 12 }}>(sporcunun tek birincil velisi olur)</span></span>
            </label>
            <label className="guardian-checkbox-label">
              <input
                type="checkbox"
                checked={canPickup}
                onChange={(e) => setCanPickup(e.target.checked)}
              />
              <span>Teslim alma yetkisi</span>
            </label>
            <label className="guardian-checkbox-label">
              <input
                type="checkbox"
                checked={canReceiveNotifications}
                onChange={(e) => setCanReceiveNotifications(e.target.checked)}
              />
              <span>Bildirim alma yetkisi</span>
            </label>
          </div>

        </div>
        <div className="modal-footer">
          <button className="btn btn-secondary" onClick={onClose} disabled={submitting}>
            İptal
          </button>
          <button
            className="btn btn-primary"
            onClick={handleSubmit}
            disabled={submitting || !selectedPerson}
          >
            {submitting ? 'Ekleniyor…' : 'Veli Ekle'}
          </button>
        </div>
      </div>
    </div>
  )
}

// ─── "Düzenle" modal'ı ────────────────────────────────────────────────────────

interface EditGuardianModalProps {
  athleteId: string
  link: PersonGuardian
  onClose: () => void
  onUpdated: () => void
}

function EditGuardianModal({ athleteId, link, onClose, onUpdated }: EditGuardianModalProps) {
  const [relationshipType, setRelationshipType] = useState(link.relationship_type ?? '')
  const [isPrimary, setIsPrimary] = useState(link.is_primary)
  const [canPickup, setCanPickup] = useState(link.can_pickup)
  const [canReceiveNotifications, setCanReceiveNotifications] = useState(link.can_receive_notifications)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const overlayRef = useRef<HTMLDivElement>(null)
  const handleOverlayClick = (e: React.MouseEvent) => {
    if (e.target === overlayRef.current) onClose()
  }

  const handleSubmit = async () => {
    setSubmitting(true)
    setError(null)
    try {
      const payload: PersonGuardianUpdate = {
        relationship_type: relationshipType || null,
        is_primary: isPrimary,
        can_pickup: canPickup,
        can_receive_notifications: canReceiveNotifications,
      }
      await personsApi.updateGuardian(athleteId, link.id, payload)
      onUpdated()
    } catch (err) {
      setError(extractDetail(err))
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="modal-overlay" ref={overlayRef} onClick={handleOverlayClick}>
      <div className="modal-box" style={{ maxWidth: 460 }}>
        <div className="modal-header">
          <span className="modal-title">
            Veli Düzenle — {link.guardian.first_name} {link.guardian.last_name}
          </span>
          <button className="modal-close" onClick={onClose} aria-label="Kapat">✕</button>
        </div>
        <div className="modal-body" style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>

          {error && (
            <div className="alert alert-error">
              <span>⚠️</span>
              <span>{error}</span>
            </div>
          )}

          <div>
            <label className="form-label">İlişki Tipi</label>
            <select
              className="form-select"
              value={relationshipType}
              onChange={(e) => setRelationshipType(e.target.value)}
            >
              {RELATIONSHIP_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>{o.label}</option>
              ))}
            </select>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            <label className="guardian-checkbox-label">
              <input
                type="checkbox"
                checked={isPrimary}
                onChange={(e) => setIsPrimary(e.target.checked)}
              />
              <span>Birincil veli</span>
            </label>
            <label className="guardian-checkbox-label">
              <input
                type="checkbox"
                checked={canPickup}
                onChange={(e) => setCanPickup(e.target.checked)}
              />
              <span>Teslim alma yetkisi</span>
            </label>
            <label className="guardian-checkbox-label">
              <input
                type="checkbox"
                checked={canReceiveNotifications}
                onChange={(e) => setCanReceiveNotifications(e.target.checked)}
              />
              <span>Bildirim alma yetkisi</span>
            </label>
          </div>

        </div>
        <div className="modal-footer">
          <button className="btn btn-secondary" onClick={onClose} disabled={submitting}>
            İptal
          </button>
          <button className="btn btn-primary" onClick={handleSubmit} disabled={submitting}>
            {submitting ? 'Kaydediliyor…' : 'Kaydet'}
          </button>
        </div>
      </div>
    </div>
  )
}

// ─── Ana bileşen ──────────────────────────────────────────────────────────────

interface PersonGuardiansSectionProps {
  /** Sporcunun Person ID'si */
  personId: string
}

export default function PersonGuardiansSection({ personId }: PersonGuardiansSectionProps) {
  const [guardians, setGuardians] = useState<PersonGuardian[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [addOpen, setAddOpen] = useState(false)
  const [editTarget, setEditTarget] = useState<PersonGuardian | null>(null)
  const [deletingId, setDeletingId] = useState<string | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const resp = await personsApi.getGuardians(personId)
      setGuardians(resp.data)
    } catch {
      setError('Veli listesi yüklenemedi.')
    } finally {
      setLoading(false)
    }
  }, [personId])

  useEffect(() => { void load() }, [load])

  const handleDelete = async (link: PersonGuardian) => {
    const name = `${link.guardian.first_name} ${link.guardian.last_name}`
    if (!window.confirm(`${name} adlı kişiyi veli listesinden çıkarmak istiyor musunuz?`)) return
    setDeletingId(link.id)
    try {
      await personsApi.deleteGuardian(personId, link.id)
      setGuardians((prev) => prev.filter((g) => g.id !== link.id))
    } catch {
      alert('Silme işlemi sırasında hata oluştu.')
    } finally {
      setDeletingId(null)
    }
  }

  return (
    <>
      <div className="card" style={{ marginBottom: 20 }}>
        <div className="card-header" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <span>Veliler / Vasiler</span>
          <button
            className="btn btn-primary btn-sm"
            onClick={() => setAddOpen(true)}
          >
            + Veli Ekle
          </button>
        </div>

        <div className="card-body" style={{ padding: 0 }}>
          {/* Loading */}
          {loading && (
            <div className="loading-center" style={{ padding: 32 }}>
              <span className="loading-spinner lg" />
            </div>
          )}

          {/* Hata */}
          {!loading && error && (
            <div style={{ padding: 20 }}>
              <div className="alert alert-error">
                <span>⚠️</span>
                <span>{error}</span>
                <button
                  className="btn btn-ghost btn-sm"
                  onClick={load}
                  style={{ marginLeft: 'auto' }}
                >
                  Tekrar Dene
                </button>
              </div>
            </div>
          )}

          {/* Boş durum */}
          {!loading && !error && guardians.length === 0 && (
            <div className="empty-state" style={{ padding: '32px 20px' }}>
              <div className="empty-state-icon">👨‍👩‍👧</div>
              <div className="empty-state-title">Kayıtlı veli yok</div>
              <div className="empty-state-desc">
                Bu sporcu için henüz veli / vasi kaydı oluşturulmamış.
              </div>
            </div>
          )}

          {/* Liste */}
          {!loading && !error && guardians.length > 0 && (
            <table className="data-table" style={{ width: '100%' }}>
              <thead>
                <tr>
                  <th>Ad Soyad</th>
                  <th>İlişki</th>
                  <th style={{ textAlign: 'center' }}>Durum</th>
                  <th style={{ textAlign: 'center' }}>Teslim</th>
                  <th style={{ textAlign: 'center' }}>Bildirim</th>
                  <th style={{ textAlign: 'right' }}>İşlem</th>
                </tr>
              </thead>
              <tbody>
                {guardians.map((g) => (
                  <tr key={g.id}>
                    <td>
                      <div style={{ fontWeight: 500 }}>
                        {g.guardian.first_name} {g.guardian.last_name}
                      </div>
                      {g.guardian.phone && (
                        <div style={{ fontSize: 12, color: 'var(--color-muted)' }}>
                          {g.guardian.phone}
                        </div>
                      )}
                      {g.guardian.member_number && (
                        <div style={{ fontSize: 11, color: 'var(--color-muted)', fontFamily: 'monospace' }}>
                          #{g.guardian.member_number}
                        </div>
                      )}
                    </td>
                    <td style={{ color: 'var(--color-muted)', fontSize: 13 }}>
                      {relLabel(g.relationship_type)}
                    </td>
                    <td style={{ textAlign: 'center' }}>
                      {g.is_primary && (
                        <span className="badge badge-status-approved" style={{ fontSize: 10 }}>
                          Birincil
                        </span>
                      )}
                    </td>
                    <td style={{ textAlign: 'center' }}>
                      <span title={g.can_pickup ? 'Teslim alabilir' : 'Teslim alamaz'}>
                        {g.can_pickup ? '✅' : '—'}
                      </span>
                    </td>
                    <td style={{ textAlign: 'center' }}>
                      <span title={g.can_receive_notifications ? 'Bildirim alır' : 'Bildirim almaz'}>
                        {g.can_receive_notifications ? '🔔' : '—'}
                      </span>
                    </td>
                    <td style={{ textAlign: 'right', whiteSpace: 'nowrap' }}>
                      <button
                        className="btn btn-ghost btn-sm"
                        style={{ marginRight: 6 }}
                        onClick={() => setEditTarget(g)}
                        disabled={deletingId === g.id}
                      >
                        Düzenle
                      </button>
                      <button
                        className="btn btn-danger btn-sm"
                        onClick={() => handleDelete(g)}
                        disabled={deletingId === g.id}
                      >
                        {deletingId === g.id ? '…' : 'Sil'}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>

      {/* Veli Ekle Modal */}
      {addOpen && (
        <AddGuardianModal
          athleteId={personId}
          onClose={() => setAddOpen(false)}
          onAdded={() => {
            setAddOpen(false)
            void load()
          }}
        />
      )}

      {/* Düzenle Modal */}
      {editTarget && (
        <EditGuardianModal
          athleteId={personId}
          link={editTarget}
          onClose={() => setEditTarget(null)}
          onUpdated={() => {
            setEditTarget(null)
            void load()
          }}
        />
      )}
    </>
  )
}
