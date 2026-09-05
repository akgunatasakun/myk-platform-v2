import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import AppShell from '@/components/layout/AppShell'
import PersonFormModal from './PersonFormModal'
import PersonGuardiansSection from './PersonGuardiansSection'
import PersonDocumentsTab from '@/components/persons/PersonDocumentsTab'
import type { PersonDocumentsRole } from '@/components/persons/PersonDocumentsTab'
import { personsApi } from '@/api/persons'
import type { Person, PersonRoleCode } from '@/types/person'
import { formatPersonAge } from '@/utils/personAge'
import { useAuth } from '@/hooks/useAuth'

const ROLE_LABELS: Record<PersonRoleCode, string> = {
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

function DetailItem({ label, value }: { label: string; value?: string | null }) {
  return (
    <div className="detail-item">
      <span className="detail-label">{label}</span>
      <span className="detail-value">{value || '—'}</span>
    </div>
  )
}

function resolveDocsRole(userRole: string | undefined): PersonDocumentsRole {
  if (userRole === 'antrenor') return 'antrenor'
  if (userRole === 'basantrenor') return 'basantrenor'
  if (userRole === 'veli') return 'veli'
  return 'admin'
}

export default function PersonDetailPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const { user: authUser } = useAuth()
  const [person, setPerson] = useState<Person | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [editOpen, setEditOpen] = useState(false)
  const [deleting, setDeleting] = useState(false)
  const [creatingAccount, setCreatingAccount] = useState(false)
  const [accountTempPassword, setAccountTempPassword] = useState<string | null>(null)
  const [selectedRoleCode, setSelectedRoleCode] = useState<string>('')

  const handleCreateAccount = async () => {
    if (!person) return
    const roleCode = person.role_codes.length === 1
      ? person.role_codes[0]
      : selectedRoleCode
    if (!roleCode) {
      alert('Lütfen bir rol seçin.')
      return
    }
    setCreatingAccount(true)
    try {
      const res = await personsApi.createAccount(person.id, roleCode)
      setAccountTempPassword(res.data.temp_password)
      // Reload person to get linked_user_id
      const updated = await personsApi.get(person.id)
      setPerson(updated.data)
    } catch (err: unknown) {
      const detail =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      alert(detail || 'Hesap oluşturulurken hata oluştu.')
    } finally {
      setCreatingAccount(false)
    }
  }

  useEffect(() => {
    if (!id) return
    setLoading(true)
    personsApi
      .get(id)
      .then((r) => setPerson(r.data))
      .catch(() => setError('Kişi bulunamadı.'))
      .finally(() => setLoading(false))
  }, [id])

  const handleSaved = (updated: Person) => {
    setPerson(updated)
  }

  const handleDelete = async () => {
    if (!person) return
    if (
      !window.confirm(
        `${person.first_name} ${person.last_name} kişisini silmek istiyor musunuz? Bu işlem geri alınamaz.`
      )
    )
      return
    setDeleting(true)
    try {
      await personsApi.delete(person.id)
      navigate('/persons')
    } catch {
      alert('Silme işlemi sırasında hata oluştu.')
      setDeleting(false)
    }
  }

  const title = person
    ? `${person.first_name} ${person.last_name}`
    : 'Kişi Detayı'

  return (
    <AppShell title={title}>
      <div style={{ marginBottom: 16 }}>
        <button className="btn btn-ghost btn-sm" onClick={() => navigate('/persons')}>
          ← Kişiler Listesine Dön
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

      {person && !loading && (
        <>
          {/* Header card */}
          <div className="card" style={{ marginBottom: 20 }}>
            <div className="card-header">
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
                  <div
                    style={{
                      width: 56,
                      height: 56,
                      borderRadius: '50%',
                      background: 'var(--color-ocean)',
                      color: '#fff',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      fontSize: 22,
                      fontWeight: 700,
                      flexShrink: 0,
                    }}
                  >
                    {person.first_name[0]}{person.last_name[0]}
                  </div>
                  <div>
                    <div style={{ fontSize: 20, fontWeight: 700, color: 'var(--color-navy)' }}>
                      {person.first_name} {person.last_name}
                    </div>
                    <div
                      style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginTop: 6 }}
                    >
                      {person.role_codes.map((code) => (
                        <span key={code} className={`badge badge-${code}`}>
                          {ROLE_LABELS[code] ?? code}
                        </span>
                      ))}
                      <span
                        className={`badge ${
                          person.is_active ? 'badge-aktif' : 'badge-pasif'
                        }`}
                      >
                        {person.is_active ? 'Aktif' : 'Pasif'}
                      </span>
                    </div>
                  </div>
                </div>
                <div style={{ display: 'flex', gap: 10 }}>
                  <button
                    className="btn btn-secondary"
                    onClick={() => setEditOpen(true)}
                  >
                    Düzenle
                  </button>
                  <button
                    className="btn btn-danger"
                    onClick={handleDelete}
                    disabled={deleting}
                  >
                    {deleting ? 'Siliniyor...' : 'Sil'}
                  </button>
                </div>
              </div>
            </div>
          </div>

          {/* Details */}
          <div className="card" style={{ marginBottom: 20 }}>
            <div className="card-header">Kişisel Bilgiler</div>
            <div className="card-body">
              <div className="detail-grid">
                <DetailItem label="TC / Pasaport No" value={person.national_id} />
                <DetailItem
                  label="Doğum Tarihi"
                  value={
                    person.birth_date
                      ? new Date(person.birth_date).toLocaleDateString('tr-TR')
                      : undefined
                  }
                />
                <DetailItem label="Güncel Yaş" value={formatPersonAge(person.birth_date)} />
                <DetailItem
                  label="Cinsiyet"
                  value={person.gender ? GENDER_LABELS[person.gender] : undefined}
                />
                <DetailItem label="Kan Grubu" value={person.blood_type} />
              </div>
            </div>
          </div>

          <div className="card" style={{ marginBottom: 20 }}>
            <div className="card-header">İletişim Bilgileri</div>
            <div className="card-body">
              <div className="detail-grid">
                <DetailItem label="Telefon" value={person.phone} />
                <DetailItem label="E-posta" value={person.email} />
                <DetailItem label="Adres" value={person.address} />
              </div>
            </div>
          </div>

          <div className="card" style={{ marginBottom: 20 }}>
            <div className="card-header">Acil Durum</div>
            <div className="card-body">
              <div className="detail-grid">
                <DetailItem
                  label="Acil Kişi"
                  value={person.emergency_contact_name}
                />
                <DetailItem
                  label="Acil Telefon"
                  value={person.emergency_contact_phone}
                />
              </div>
            </div>
          </div>

          {person.notes && (
            <div className="card" style={{ marginBottom: 20 }}>
              <div className="card-header">Notlar</div>
              <div className="card-body">
                <p style={{ fontSize: 14, lineHeight: 1.6, whiteSpace: 'pre-wrap' }}>
                  {person.notes}
                </p>
              </div>
            </div>
          )}

          {/* Hesap Durumu */}
          <div className="card" style={{ marginBottom: 20 }}>
            <div className="card-header">Hesap Durumu</div>
            <div className="card-body">
              {person.linked_user_id ? (
                <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                  <span
                    style={{
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: 6,
                      padding: '4px 12px',
                      borderRadius: 20,
                      background: '#d1fae5',
                      color: '#065f46',
                      fontWeight: 600,
                      fontSize: 14,
                    }}
                  >
                    ✓ Hesap Mevcut
                  </span>
                  {person.linked_user_email && (
                    <span style={{ fontSize: 14, color: 'var(--color-text-secondary)' }}>
                      {person.linked_user_email}
                    </span>
                  )}
                </div>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
                    <span
                      style={{
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: 6,
                        padding: '4px 12px',
                        borderRadius: 20,
                        background: '#fee2e2',
                        color: '#991b1b',
                        fontWeight: 600,
                        fontSize: 14,
                      }}
                    >
                      Hesap Yok
                    </span>
                    {!person.email && (
                      <span style={{ fontSize: 13, color: 'var(--color-text-secondary)' }}>
                        (Hesap oluşturmak için önce e-posta ekleyin)
                      </span>
                    )}
                  </div>

                  {person.email && (
                    <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
                      {person.role_codes.length > 1 && (
                        <select
                          className="form-select"
                          style={{ maxWidth: 200 }}
                          value={selectedRoleCode}
                          onChange={(e) => setSelectedRoleCode(e.target.value)}
                        >
                          <option value="">Rol seçin…</option>
                          {person.role_codes.map((code) => (
                            <option key={code} value={code}>
                              {ROLE_LABELS[code] ?? code}
                            </option>
                          ))}
                        </select>
                      )}
                      <button
                        className="btn btn-primary"
                        onClick={handleCreateAccount}
                        disabled={creatingAccount}
                      >
                        {creatingAccount ? 'Oluşturuluyor…' : 'Hesap Oluştur'}
                      </button>
                    </div>
                  )}
                </div>
              )}

              {/* Geçici parola — tek seferlik gösterim (G5) */}
              {accountTempPassword && (
                <div
                  style={{
                    marginTop: 16,
                    padding: 12,
                    background: '#fffbeb',
                    border: '1px solid #fcd34d',
                    borderRadius: 8,
                  }}
                >
                  <div style={{ fontWeight: 600, marginBottom: 4, fontSize: 14 }}>
                    ⚠️ Geçici Parola — Yalnızca Bir Kez Görüntülenir
                  </div>
                  <code
                    style={{
                      fontFamily: 'monospace',
                      fontSize: 16,
                      letterSpacing: 1,
                      color: '#92400e',
                    }}
                  >
                    {accountTempPassword}
                  </code>
                  <div style={{ marginTop: 8, fontSize: 13, color: '#78350f' }}>
                    Bu parolayı kullanıcıya güvenli kanaldan iletin. Sayfa kapatıldıktan sonra tekrar görüntülenemez.
                  </div>
                  <button
                    className="btn btn-sm btn-ghost"
                    style={{ marginTop: 8 }}
                    onClick={() => setAccountTempPassword(null)}
                  >
                    Kapat
                  </button>
                </div>
              )}
            </div>
          </div>

          {/* Veliler / Vasiler bölümü */}
          <PersonGuardiansSection personId={person.id} />

          {/* Evraklar bölümü */}
          <div className="card" style={{ marginTop: 20 }}>
            <div className="card-header">Evraklar</div>
            <div className="card-body">
              <PersonDocumentsTab
                subjectPersonId={person.id}
                role={resolveDocsRole(authUser?.role)}
              />
            </div>
          </div>
        </>
      )}

      {person && (
        <PersonFormModal
          isOpen={editOpen}
          onClose={() => setEditOpen(false)}
          person={person}
          onSaved={handleSaved}
        />
      )}
    </AppShell>
  )
}
