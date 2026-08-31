/**
 * Public kurs başvuru formu — /basvuru
 *
 * Kimlik doğrulama gerektirmez. AppShell kullanılmaz.
 * POST /api/v1/public/membership-applications
 */
import { useEffect, useMemo, useState } from 'react'
import { publicApi } from '@/api/public'
import type { PublicApplicationData, PublicTrainingCourse } from '@/api/public'
import { calcAgeInYears, getProgramAgeHint, parseProgramParam, VALID_PROGRAMS } from '@/utils/programAge'

// ─── Sabitler ────────────────────────────────────────────────────────────────

const CLUB_SLUG = 'mersin-yelken'

const GENDER_OPTIONS = [
  { value: '', label: 'Seçiniz' },
  { value: 'erkek', label: 'Erkek' },
  { value: 'kadin', label: 'Kadın' },
  { value: 'belirtilmedi', label: 'Belirtilmedi' },
]

const PROGRAM_OPTIONS = [
  { value: '', label: 'Seçiniz (opsiyonel)' },
  { value: 'optimist', label: 'Optimist' },
  { value: 'ilca', label: 'ILCA (Laser)' },
  { value: '420', label: '420' },
  { value: 'wing_foil', label: 'Wing Foil' },
  { value: 'para_yelken', label: 'Para Yelken' },
]

// VALID_PROGRAMS programAge.ts'den import edildi — çift tanım yok

// Yaş–program uyumluluk için programAge.ts util kullanılıyor

const BLOOD_TYPE_OPTIONS = [
  { value: '', label: 'Seçiniz' },
  { value: 'A+', label: 'A Rh+' },
  { value: 'A-', label: 'A Rh-' },
  { value: 'B+', label: 'B Rh+' },
  { value: 'B-', label: 'B Rh-' },
  { value: 'AB+', label: 'AB Rh+' },
  { value: 'AB-', label: 'AB Rh-' },
  { value: '0+', label: '0 Rh+' },
  { value: '0-', label: '0 Rh-' },
]

// ─── Form state arayüzü ───────────────────────────────────────────────────────

interface FormFields {
  first_name: string
  last_name: string
  national_id: string
  birth_date: string
  gender: string
  blood_type: string
  phone: string
  email: string
  address: string
  emergency_contact_name: string
  emergency_contact_phone: string
  guardian_name: string
  guardian_phone: string
  program_preference: string
  preferred_course_id: string
  consent_accepted: boolean
}

type FieldErrors = Partial<Record<keyof FormFields, string>>

const INITIAL: FormFields = {
  first_name: '',
  last_name: '',
  national_id: '',
  birth_date: '',
  gender: '',
  blood_type: '',
  phone: '',
  email: '',
  address: '',
  emergency_contact_name: '',
  emergency_contact_phone: '',
  guardian_name: '',
  guardian_phone: '',
  program_preference: '',
  preferred_course_id: '',
  consent_accepted: false,
}

// ─── Doğrulama ────────────────────────────────────────────────────────────────

function validate(fields: FormFields): FieldErrors {
  const errors: FieldErrors = {}

  if (!fields.first_name.trim()) errors.first_name = 'Ad zorunludur.'
  if (!fields.last_name.trim()) errors.last_name = 'Soyad zorunludur.'

  if (!fields.email.trim()) {
    errors.email = 'E-posta zorunludur.'
  } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(fields.email.trim())) {
    errors.email = 'Geçerli bir e-posta adresi giriniz.'
  }

  if (!fields.phone.trim()) {
    errors.phone = 'Telefon zorunludur.'
  }

  if (fields.national_id.trim() && !/^\d{11}$/.test(fields.national_id.trim())) {
    errors.national_id = 'T.C. kimlik no 11 haneli rakam olmalıdır.'
  }

  if (!fields.consent_accepted) {
    errors.consent_accepted = 'KVKK aydınlatma metnini onaylamanız zorunludur.'
  }

  return errors
}

// ─── Telefon normalizasyonu ───────────────────────────────────────────────────

function normalizePhone(raw: string): string {
  // boşluk, tire, parantez kaldır; + işaretini koru
  return raw.replace(/[\s\-()]/g, '')
}

// ─── 422 hata ayrıştırıcı ────────────────────────────────────────────────────

function extractApiError(err: unknown): string {
  const data = (err as { response?: { data?: unknown } })?.response?.data
  if (!data) return 'Sunucuya bağlanılamadı. Lütfen tekrar deneyin.'

  // Pydantic 422 — detail bir dizi olabilir
  const detail = (data as { detail?: unknown })?.detail
  if (Array.isArray(detail)) {
    return detail
      .map((d: unknown) => {
        const item = d as { msg?: string; loc?: string[] }
        return item.msg ?? JSON.stringify(d)
      })
      .join(' ')
  }
  if (typeof detail === 'string') return detail

  // Genel mesaj
  return 'Başvuru gönderilemedi. Lütfen bilgilerinizi kontrol edip tekrar deneyin.'
}

// ─── Yardımcı bileşenler ──────────────────────────────────────────────────────

function FormField({
  label,
  required,
  error,
  children,
}: {
  label: string
  required?: boolean
  error?: string
  children: React.ReactNode
}) {
  return (
    <div className="public-field">
      <label className={`form-label${required ? ' required' : ''}`}>{label}</label>
      {children}
      {error && <span className="form-error">{error}</span>}
    </div>
  )
}

// ─── Başarı ekranı ─────────────────────────────────────────────────────────────

function SuccessScreen({ applicationNumber }: { applicationNumber: string | null }) {
  return (
    <div className="public-success">
      <h2 className="public-success-title">Kurs Başvurunuz Alındı</h2>
      <p className="public-success-desc">
        Kurs başvurunuz başarıyla iletildi. Yetkili tarafından incelendikten sonra
        e-posta adresinize bilgilendirme yapılacaktır.
      </p>
      {applicationNumber && (
        <div className="public-success-number">
          <span className="public-success-number-label">Başvuru Numaranız</span>
          <span className="public-success-number-value">{applicationNumber}</span>
        </div>
      )}
      <p className="public-success-note">
        Bu numarayı not alarak başvurunuzun durumunu kulüple iletişime geçerek
        öğrenebilirsiniz.
      </p>
    </div>
  )
}

// ─── Ana bileşen ──────────────────────────────────────────────────────────────

export default function ApplicationFormPage() {
  // ?program= URL param — pre-fill program_preference if valid; flag if invalid
  const { urlProgram, urlParamInvalid } = useMemo(() => {
    const param = new URLSearchParams(window.location.search).get('program')
    const { program, invalid } = parseProgramParam(param)
    return { urlProgram: program, urlParamInvalid: invalid }
  }, [])

  const [fields, setFields] = useState<FormFields>({ ...INITIAL, program_preference: urlProgram })
  const [errors, setErrors] = useState<FieldErrors>({})
  const [submitting, setSubmitting] = useState(false)
  const [apiError, setApiError] = useState<string | null>(null)
  const [successNumber, setSuccessNumber] = useState<string | null | undefined>(undefined)
  const [courses, setCourses] = useState<PublicTrainingCourse[]>([])
  const [coursesLoading, setCoursesLoading] = useState(true)
  const [coursesError, setCoursesError] = useState<string | null>(null)

  useEffect(() => {
    let active = true
    publicApi.listTrainingCourses(CLUB_SLUG)
      .then((response) => {
        if (active) setCourses(response.data)
      })
      .catch(() => {
        if (active) setCoursesError('Tanımlı eğitimler şu anda yüklenemedi. Seçmeden devam edebilirsiniz.')
      })
      .finally(() => {
        if (active) setCoursesLoading(false)
      })
    return () => { active = false }
  }, [])

  // Tam yıl yaş — helper util
  const ageInYears = useMemo(() => calcAgeInYears(fields.birth_date), [fields.birth_date])

  // 18 yaş altı → veli bilgisi uyarısı
  const isMinor = ageInYears !== null && ageInYears < 18

  // Program–yaş uyumluluk uyarısı (soft — submit engellenmez, bucket bazlı)
  const programAgeHint = useMemo(() => {
    if (!fields.program_preference || ageInYears === null) return null
    return getProgramAgeHint(fields.program_preference, ageInYears)
  }, [fields.program_preference, ageInYears])

  const submitted = successNumber !== undefined

  const set = (key: keyof FormFields, value: string | boolean) => {
    setFields((prev) => ({ ...prev, [key]: value }))
    if (errors[key]) setErrors((prev) => ({ ...prev, [key]: undefined }))
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (submitting) return

    const fieldErrors = validate(fields)
    if (Object.keys(fieldErrors).length > 0) {
      setErrors(fieldErrors)
      // İlk hatalı alana odaklan
      const firstKey = Object.keys(fieldErrors)[0]
      const el = document.getElementById(`field-${firstKey}`)
      el?.focus()
      return
    }

    setSubmitting(true)
    setApiError(null)

    try {
      const payload: PublicApplicationData = {
        club_slug: CLUB_SLUG,
        first_name: fields.first_name.trim(),
        last_name: fields.last_name.trim(),
        email: fields.email.trim().toLowerCase(),
        phone: normalizePhone(fields.phone),
        consent_accepted: fields.consent_accepted,
      }

      // Opsiyonel alanları yalnızca doldurulmuşsa ekle
      if (fields.national_id.trim()) payload.national_id = fields.national_id.trim()
      if (fields.birth_date) payload.birth_date = fields.birth_date
      if (fields.gender) payload.gender = fields.gender
      if (fields.blood_type) payload.blood_type = fields.blood_type
      if (fields.address.trim()) payload.address = fields.address.trim()
      if (fields.emergency_contact_name.trim())
        payload.emergency_contact_name = fields.emergency_contact_name.trim()
      if (fields.emergency_contact_phone.trim())
        payload.emergency_contact_phone = normalizePhone(fields.emergency_contact_phone)
      if (fields.guardian_name.trim()) payload.guardian_name = fields.guardian_name.trim()
      if (fields.guardian_phone.trim())
        payload.guardian_phone = normalizePhone(fields.guardian_phone)
      if (fields.program_preference && VALID_PROGRAMS.has(fields.program_preference))
        payload.program_preference = fields.program_preference
      if (fields.preferred_course_id) payload.preferred_course_id = fields.preferred_course_id

      const resp = await publicApi.submitApplication(payload)
      setSuccessNumber(resp.data.application_number)
    } catch (err: unknown) {
      setApiError(extractApiError(err))
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="public-page">
      {/* Header */}
      <header className="public-header">
        <div className="public-header-inner">
          <div className="public-header-logo">
            <img
              src="/logo-icon.png"
              alt="Mersin Yelken Kulübü logosu"
              className="public-header-logo-image"
            />
            <div>
              <div className="public-header-club">Mersin Yelken Kulübü</div>
              <div className="public-header-sub">Kurs Başvurusu</div>
            </div>
          </div>
        </div>
      </header>

      {/* İçerik */}
      <main className="public-main">
        <div className="public-card">
          {submitted ? (
            <SuccessScreen applicationNumber={successNumber ?? null} />
          ) : (
            <>
              <div className="public-card-title">
                <h1>Kurs Başvuru Formu</h1>
                <p className="public-card-desc">
                  Aşağıdaki formu eksiksiz doldurun. Yıldızlı alanlar (<span className="required-star">*</span>) zorunludur.
                </p>
              </div>

              {apiError && (
                <div className="alert alert-error" style={{ margin: '0 0 20px' }}>
                  <span>⚠️</span>
                  <span>{apiError}</span>
                </div>
              )}

              <form onSubmit={handleSubmit} noValidate>

                {/* Kişisel Bilgiler */}
                <section className="public-section">
                  <h2 className="public-section-title">Kişisel Bilgiler</h2>
                  <div className="public-form-grid">
                    <FormField label="Ad" required error={errors.first_name}>
                      <input
                        id="field-first_name"
                        type="text"
                        className={`form-input${errors.first_name ? ' error' : ''}`}
                        placeholder="Adınız"
                        value={fields.first_name}
                        onChange={(e) => set('first_name', e.target.value)}
                        autoComplete="given-name"
                        maxLength={100}
                      />
                    </FormField>

                    <FormField label="Soyad" required error={errors.last_name}>
                      <input
                        id="field-last_name"
                        type="text"
                        className={`form-input${errors.last_name ? ' error' : ''}`}
                        placeholder="Soyadınız"
                        value={fields.last_name}
                        onChange={(e) => set('last_name', e.target.value)}
                        autoComplete="family-name"
                        maxLength={100}
                      />
                    </FormField>

                    <FormField label="T.C. Kimlik No" error={errors.national_id}>
                      <input
                        id="field-national_id"
                        type="text"
                        className={`form-input${errors.national_id ? ' error' : ''}`}
                        placeholder="11 haneli T.C. kimlik no"
                        value={fields.national_id}
                        onChange={(e) => set('national_id', e.target.value.replace(/\D/g, ''))}
                        inputMode="numeric"
                        maxLength={11}
                      />
                    </FormField>

                    <FormField label="Doğum Tarihi" error={errors.birth_date}>
                      <input
                        id="field-birth_date"
                        type="date"
                        className={`form-input${errors.birth_date ? ' error' : ''}`}
                        value={fields.birth_date}
                        onChange={(e) => set('birth_date', e.target.value)}
                        max={new Date().toISOString().slice(0, 10)}
                      />
                    </FormField>

                    <FormField label="Cinsiyet" error={errors.gender}>
                      <select
                        id="field-gender"
                        className={`form-select${errors.gender ? ' error' : ''}`}
                        value={fields.gender}
                        onChange={(e) => set('gender', e.target.value)}
                      >
                        {GENDER_OPTIONS.map((o) => (
                          <option key={o.value} value={o.value}>{o.label}</option>
                        ))}
                      </select>
                    </FormField>

                    <FormField label="Kan Grubu" error={errors.blood_type}>
                      <select
                        id="field-blood_type"
                        className={`form-select${errors.blood_type ? ' error' : ''}`}
                        value={fields.blood_type}
                        onChange={(e) => set('blood_type', e.target.value)}
                      >
                        {BLOOD_TYPE_OPTIONS.map((o) => (
                          <option key={o.value} value={o.value}>{o.label}</option>
                        ))}
                      </select>
                    </FormField>
                  </div>
                </section>

                {/* İletişim */}
                <section className="public-section">
                  <h2 className="public-section-title">İletişim Bilgileri</h2>
                  <div className="public-form-grid">
                    <FormField label="Telefon" required error={errors.phone}>
                      <input
                        id="field-phone"
                        type="tel"
                        className={`form-input${errors.phone ? ' error' : ''}`}
                        placeholder="+90 5XX XXX XX XX"
                        value={fields.phone}
                        onChange={(e) => set('phone', e.target.value)}
                        autoComplete="tel"
                        maxLength={20}
                      />
                    </FormField>

                    <FormField label="E-posta" required error={errors.email}>
                      <input
                        id="field-email"
                        type="email"
                        className={`form-input${errors.email ? ' error' : ''}`}
                        placeholder="ornek@eposta.com"
                        value={fields.email}
                        onChange={(e) => set('email', e.target.value)}
                        autoComplete="email"
                        maxLength={255}
                      />
                    </FormField>

                    <FormField label="Adres" error={errors.address}>
                      <textarea
                        id="field-address"
                        className={`form-textarea${errors.address ? ' error' : ''}`}
                        placeholder="Açık adresiniz"
                        value={fields.address}
                        onChange={(e) => set('address', e.target.value)}
                        rows={2}
                        maxLength={500}
                        style={{ gridColumn: '1 / -1' }}
                      />
                    </FormField>
                  </div>
                </section>

                {/* Acil Durum */}
                <section className="public-section">
                  <h2 className="public-section-title">Acil Durum Kişisi</h2>
                  <p className="public-section-desc">
                    Sizinle iletişime geçilemediğinde ulaşılabilecek kişi.
                  </p>
                  <div className="public-form-grid">
                    <FormField label="Acil Kişi Adı Soyadı" error={errors.emergency_contact_name}>
                      <input
                        id="field-emergency_contact_name"
                        type="text"
                        className={`form-input${errors.emergency_contact_name ? ' error' : ''}`}
                        placeholder="Ad Soyad"
                        value={fields.emergency_contact_name}
                        onChange={(e) => set('emergency_contact_name', e.target.value)}
                        maxLength={150}
                      />
                    </FormField>

                    <FormField label="Acil Kişi Telefonu" error={errors.emergency_contact_phone}>
                      <input
                        id="field-emergency_contact_phone"
                        type="tel"
                        className={`form-input${errors.emergency_contact_phone ? ' error' : ''}`}
                        placeholder="+90 5XX XXX XX XX"
                        value={fields.emergency_contact_phone}
                        onChange={(e) => set('emergency_contact_phone', e.target.value)}
                        maxLength={20}
                      />
                    </FormField>
                  </div>
                </section>

                {/* Veli Bilgileri */}
                <section className="public-section">
                  <h2 className="public-section-title">Veli Bilgileri</h2>
                  <p className="public-section-desc">
                    18 yaş altı sporcular için veli bilgilerini giriniz.
                  </p>
                  {isMinor && (
                    <div className="alert alert-warning" style={{ marginBottom: 12 }}>
                      <span>ℹ️</span>
                      <span>Doğum tarihinize göre 18 yaşın altındasınız. Lütfen veli bilgilerini doldurunuz.</span>
                    </div>
                  )}
                  <div className="public-form-grid">
                    <FormField label="Veli Adı Soyadı" error={errors.guardian_name}>
                      <input
                        id="field-guardian_name"
                        type="text"
                        className={`form-input${errors.guardian_name ? ' error' : ''}`}
                        placeholder="Ad Soyad"
                        value={fields.guardian_name}
                        onChange={(e) => set('guardian_name', e.target.value)}
                        maxLength={150}
                      />
                    </FormField>

                    <FormField label="Veli Telefonu" error={errors.guardian_phone}>
                      <input
                        id="field-guardian_phone"
                        type="tel"
                        className={`form-input${errors.guardian_phone ? ' error' : ''}`}
                        placeholder="+90 5XX XXX XX XX"
                        value={fields.guardian_phone}
                        onChange={(e) => set('guardian_phone', e.target.value)}
                        maxLength={20}
                      />
                    </FormField>
                  </div>
                </section>

                {/* Program Tercihi */}
                <section className="public-section">
                  <h2 className="public-section-title">Eğitim ve Program Tercihi</h2>
                  <p className="public-section-desc">
                    Katılmak istediğiniz programı seçin (opsiyonel). Yönetici kayıt sırasında yönlendirme yapacaktır.
                  </p>
                  {urlParamInvalid && (
                    <div className="alert alert-warning" style={{ marginBottom: 12 }}>
                      <span>ℹ️</span>
                      <span>Bağlantıdaki program kodu tanınmadı. Lütfen aşağıdan bir program seçin.</span>
                    </div>
                  )}
                  <div className="public-form-grid">
                    <FormField label="Program Tercihi">
                      <select
                        id="field-program_preference"
                        className="form-select"
                        value={fields.program_preference}
                        onChange={(e) => set('program_preference', e.target.value)}
                      >
                        {PROGRAM_OPTIONS.map((o) => (
                          <option key={o.value} value={o.value}>{o.label}</option>
                        ))}
                      </select>
                    </FormField>
                  </div>
                  {programAgeHint && (
                    <div className="alert alert-warning" style={{ marginTop: 8 }}>
                      <span>⚠️</span>
                      <span>{programAgeHint} Submit'e basabilirsiniz; yönetici onay sürecinde yönlendirecektir.</span>
                    </div>
                  )}
                  <div className="public-form-grid" style={{ marginTop: 16 }}>
                    <FormField label="Tanımlı Eğitim">
                      <select
                        id="field-preferred_course_id"
                        className="form-select"
                        value={fields.preferred_course_id}
                        onChange={(e) => set('preferred_course_id', e.target.value)}
                        disabled={coursesLoading}
                      >
                        <option value="">
                          {coursesLoading ? 'Eğitimler yükleniyor…' : 'Henüz karar vermedim / Sonra seçmek istiyorum'}
                        </option>
                        {courses.map((course) => (
                          <option key={course.id} value={course.id}>
                            {course.name}
                            {course.class_name ? ` · ${course.class_name}` : ''}
                            {course.schedule_text ? ` · ${course.schedule_text}` : ''}
                          </option>
                        ))}
                      </select>
                    </FormField>
                  </div>
                  {coursesError && (
                    <div className="alert alert-warning" style={{ marginTop: 8 }}>
                      <span>ℹ️</span><span>{coursesError}</span>
                    </div>
                  )}
                </section>

                {/* KVKK */}
                <section className="public-section">
                  <h2 className="public-section-title">Kişisel Verilerin Korunması</h2>
                  <div
                    className={`public-kvkk-box${errors.consent_accepted ? ' public-kvkk-box--error' : ''}`}
                  >
                    <label className="public-kvkk-label">
                      <input
                        id="field-consent_accepted"
                        type="checkbox"
                        className="public-kvkk-checkbox"
                        checked={fields.consent_accepted}
                        onChange={(e) => set('consent_accepted', e.target.checked)}
                      />
                      <span>
                        6698 sayılı KVKK kapsamında kişisel verilerimin Mersin Yelken Kulübü
                        tarafından kurs başvurusu ve kayıt işlemleri amacıyla işlenmesine ilişkin{' '}
                        <strong>Aydınlatma Metni</strong>'ni okudum ve anladım. Verilerimin
                        işlenmesini kabul ediyorum.{' '}
                        <span className="required-star">*</span>
                      </span>
                    </label>
                    {errors.consent_accepted && (
                      <p className="form-error" style={{ marginTop: 8 }}>
                        {errors.consent_accepted}
                      </p>
                    )}
                  </div>
                </section>

                {/* Gönder */}
                <div className="public-submit-row">
                  <button
                    type="submit"
                    className="btn btn-primary public-submit-btn"
                    disabled={submitting}
                  >
                    {submitting ? (
                      <>
                        <span className="loading-spinner" style={{ borderTopColor: '#fff' }} />
                        Gönderiliyor…
                      </>
                    ) : (
                      'Başvuruyu Gönder →'
                    )}
                  </button>
                  <p className="public-submit-note">
                    Başvurunuz incelendikten sonra e-posta adresinize bilgi verilecektir.
                  </p>
                </div>

              </form>
            </>
          )}
        </div>
      </main>

      {/* Footer */}
      <footer className="public-footer">
        <p>© {new Date().getFullYear()} Mersin Yelken Kulübü — Tüm hakları saklıdır.</p>
      </footer>
    </div>
  )
}
