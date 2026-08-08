/**
 * İlk girişte zorunlu parola değiştirme sayfası.
 *
 * - Yalnızca kimlik doğrulanmış kullanıcılar erişir (ProtectedRoute sağlar).
 * - must_change_password=true iken diğer route'lara erişim engellidir (App.tsx guard).
 * - Parola değiştikten sonra must_change_password store'da false yapılır → /dashboard yönlendirme.
 * - AppShell kullanılmaz; yalın, güvenli bir ekran.
 */
import { FormEvent, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { authApi } from '@/api/auth'
import { useAuth } from '@/hooks/useAuth'

// ─── Client-side parola politikası ───────────────────────────────────────────

function validatePassword(pw: string): string | null {
  if (pw.length < 8) return 'Parola en az 8 karakter olmalıdır.'
  if (!/[A-Z]/.test(pw)) return 'Parola en az bir büyük harf içermelidir.'
  if (!/[0-9]/.test(pw)) return 'Parola en az bir rakam içermelidir.'
  return null
}

// ─── Ana bileşen ──────────────────────────────────────────────────────────────

export default function ChangePasswordPage() {
  const navigate = useNavigate()
  const { user, fetchMe } = useAuth()

  const [currentPassword, setCurrentPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [fieldErrors, setFieldErrors] = useState<{
    currentPassword?: string
    newPassword?: string
    confirmPassword?: string
  }>({})

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    if (submitting) return

    // Client-side doğrulama
    const errs: typeof fieldErrors = {}
    if (!currentPassword) errs.currentPassword = 'Mevcut parola zorunludur.'
    const pwErr = validatePassword(newPassword)
    if (pwErr) errs.newPassword = pwErr
    if (newPassword !== confirmPassword) errs.confirmPassword = 'Parolalar eşleşmiyor.'
    if (Object.keys(errs).length > 0) {
      setFieldErrors(errs)
      return
    }
    setFieldErrors({})

    setSubmitting(true)
    setError(null)
    try {
      await authApi.changePassword({
        current_password: currentPassword,
        new_password: newPassword,
        confirm_password: confirmPassword,
      })
      // Başarı: must_change_password artık false — state'i yenile
      await fetchMe()
      navigate('/dashboard', { replace: true })
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: unknown } } })
        ?.response?.data?.detail
      if (Array.isArray(detail)) {
        setError(detail.map((d: { msg?: string }) => d.msg ?? '').join(' '))
      } else if (typeof detail === 'string') {
        setError(detail)
      } else {
        setError('Parola değiştirilemedi. Lütfen tekrar deneyin.')
      }
    } finally {
      setSubmitting(false)
    }
  }

  const clearFieldError = (field: keyof typeof fieldErrors) =>
    setFieldErrors((prev) => ({ ...prev, [field]: undefined }))

  return (
    <div className="public-page">
      {/* Header */}
      <header className="public-header">
        <div className="public-header-inner">
          <div className="public-header-logo">
            <span className="public-header-logo-icon">⛵</span>
            <div>
              <div className="public-header-club">Mersin Yelken Kulübü</div>
              <div className="public-header-sub">Yönetim Sistemi</div>
            </div>
          </div>
        </div>
      </header>

      <main className="public-main" style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'center' }}>
        <div className="public-card" style={{ maxWidth: 480 }}>
          <div className="public-card-title">
            <h1 style={{ fontSize: 18 }}>Parola Değiştirme Zorunlu</h1>
            <p className="public-card-desc">
              {user?.full_name ? `Merhaba ${user.full_name},` : 'Merhaba,'}{' '}
              hesabınız geçici bir parola ile oluşturuldu. Devam etmek için lütfen
              yeni bir parola belirleyin.
            </p>
          </div>

          {error && (
            <div className="alert alert-error" style={{ margin: '0 32px 4px' }}>
              <span>⚠️</span>
              <span>{error}</span>
            </div>
          )}

          <form onSubmit={handleSubmit} noValidate>
            <section className="public-section">
              <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>

                {/* Mevcut parola */}
                <div className="public-field">
                  <label className="form-label required" htmlFor="current-pw">
                    Mevcut / Geçici Parola
                  </label>
                  <input
                    id="current-pw"
                    type="password"
                    className={`form-input${fieldErrors.currentPassword ? ' error' : ''}`}
                    value={currentPassword}
                    onChange={(e) => {
                      setCurrentPassword(e.target.value)
                      clearFieldError('currentPassword')
                    }}
                    autoComplete="current-password"
                    autoFocus
                    maxLength={128}
                  />
                  {fieldErrors.currentPassword && (
                    <span className="form-error">{fieldErrors.currentPassword}</span>
                  )}
                </div>

                {/* Yeni parola */}
                <div className="public-field">
                  <label className="form-label required" htmlFor="new-pw">
                    Yeni Parola
                  </label>
                  <input
                    id="new-pw"
                    type="password"
                    className={`form-input${fieldErrors.newPassword ? ' error' : ''}`}
                    value={newPassword}
                    onChange={(e) => {
                      setNewPassword(e.target.value)
                      clearFieldError('newPassword')
                    }}
                    autoComplete="new-password"
                    maxLength={128}
                  />
                  {fieldErrors.newPassword && (
                    <span className="form-error">{fieldErrors.newPassword}</span>
                  )}
                  <span style={{ fontSize: 12, color: 'var(--color-muted)', marginTop: 2 }}>
                    En az 8 karakter, 1 büyük harf ve 1 rakam içermelidir.
                  </span>
                </div>

                {/* Parola tekrar */}
                <div className="public-field">
                  <label className="form-label required" htmlFor="confirm-pw">
                    Yeni Parola (Tekrar)
                  </label>
                  <input
                    id="confirm-pw"
                    type="password"
                    className={`form-input${fieldErrors.confirmPassword ? ' error' : ''}`}
                    value={confirmPassword}
                    onChange={(e) => {
                      setConfirmPassword(e.target.value)
                      clearFieldError('confirmPassword')
                    }}
                    autoComplete="new-password"
                    maxLength={128}
                  />
                  {fieldErrors.confirmPassword && (
                    <span className="form-error">{fieldErrors.confirmPassword}</span>
                  )}
                </div>

              </div>
            </section>

            <div className="public-submit-row">
              <button
                type="submit"
                className="btn btn-primary public-submit-btn"
                disabled={submitting}
              >
                {submitting ? (
                  <>
                    <span className="loading-spinner" style={{ borderTopColor: '#fff' }} />
                    Kaydediliyor…
                  </>
                ) : (
                  'Parolayı Değiştir'
                )}
              </button>
            </div>
          </form>
        </div>
      </main>
    </div>
  )
}
