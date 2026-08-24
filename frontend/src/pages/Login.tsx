import { FormEvent, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { useAuth } from '@/hooks/useAuth'

export default function Login() {
  const navigate = useNavigate()
  const { login, isLoading } = useAuth()
  const [searchParams] = useSearchParams()

  const [clubSlug, setClubSlug] = useState(searchParams.get('club') ?? '')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    setError(null)
    try {
      await login({ club_slug: clubSlug, email, password })
      navigate('/dashboard')
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { detail?: string } } })?.response?.data
          ?.detail ?? 'Giriş başarısız. Lütfen bilgilerinizi kontrol edin.'
      setError(msg)
    }
  }

  return (
    <div style={styles.container}>
      <div style={styles.card}>
        <div style={styles.logoWrap}>
          <img src="/logo.png" alt="Mersin Yelken Yat ve Su Sporları Kulübü" style={styles.logo} />
        </div>
        <p style={styles.subtitle}>Yönetim Sistemi</p>

        <form onSubmit={handleSubmit} style={styles.form} noValidate>
          <div style={styles.field}>
            <label htmlFor="club_slug" style={styles.label}>
              Kulüp Kodu
            </label>
            <input
              id="club_slug"
              type="text"
              value={clubSlug}
              onChange={(e) => setClubSlug(e.target.value.toLowerCase())}
              placeholder="mersin-yelken"
              required
              autoComplete="organization"
              style={styles.input}
            />
          </div>

          <div style={styles.field}>
            <label htmlFor="email" style={styles.label}>
              E-posta
            </label>
            <input
              id="email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="ad@kulup.com"
              required
              autoComplete="email"
              style={styles.input}
            />
          </div>

          <div style={styles.field}>
            <label htmlFor="password" style={styles.label}>
              Parola
            </label>
            <input
              id="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              autoComplete="current-password"
              style={styles.input}
            />
          </div>

          {error && <p style={styles.error}>{error}</p>}

          <button type="submit" disabled={isLoading} style={styles.button}>
            {isLoading ? 'Giriş yapılıyor…' : 'Giriş Yap'}
          </button>
        </form>
      </div>
    </div>
  )
}

const styles: Record<string, React.CSSProperties> = {
  container: {
    minHeight: '100vh',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    background: 'linear-gradient(160deg, #001f4d 0%, #003580 55%, #0052cc 100%)',
    fontFamily: 'system-ui, sans-serif',
  },
  card: {
    background: '#fff',
    borderRadius: 16,
    padding: '2.5rem',
    width: '100%',
    maxWidth: 420,
    boxShadow: '0 8px 40px rgba(0,0,0,0.25)',
    textAlign: 'center' as const,
  },
  logoWrap: {
    display: 'flex',
    justifyContent: 'center',
    marginBottom: '1rem',
  },
  logo: {
    width: 220,
    height: 'auto',
  },
  subtitle: { marginTop: 4, color: '#6b7280', fontSize: '0.9rem' },
  form: { display: 'flex', flexDirection: 'column', gap: '1rem', marginTop: '1.5rem', textAlign: 'left' as const },
  field: { display: 'flex', flexDirection: 'column', gap: 4 },
  label: { fontSize: '0.875rem', fontWeight: 500, color: '#374151' },
  input: {
    padding: '0.625rem 0.875rem',
    border: '1px solid #d1d5db',
    borderRadius: 8,
    fontSize: '1rem',
    outline: 'none',
  },
  error: { color: '#dc2626', fontSize: '0.875rem', margin: 0 },
  button: {
    padding: '0.75rem',
    background: '#0052cc',
    color: '#fff',
    border: 'none',
    borderRadius: 8,
    fontSize: '1rem',
    fontWeight: 600,
    cursor: 'pointer',
    marginTop: 8,
  },
}
