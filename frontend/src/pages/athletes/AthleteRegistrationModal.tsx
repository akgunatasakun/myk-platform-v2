import { useEffect, useRef, useState } from 'react'
import PersonFormModal from '@/pages/persons/PersonFormModal'
import { personsApi } from '@/api/persons'
import type { Person } from '@/types/person'

type Option = Pick<Person, 'id' | 'first_name' | 'last_name' | 'phone'>
type Mode = 'none' | 'existing' | 'new'
interface Props { isOpen: boolean; onClose: () => void; onSaved: (person: Person) => void }

export default function AthleteRegistrationModal({ isOpen, onClose, onSaved }: Props) {
  const [mode, setMode] = useState<Mode>('none')
  const [search, setSearch] = useState('')
  const [options, setOptions] = useState<Option[]>([])
  const [selected, setSelected] = useState<Option | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [first, setFirst] = useState('')
  const [last, setLast] = useState('')
  const [phone, setPhone] = useState('')
  const [email, setEmail] = useState('')
  const [relationship, setRelationship] = useState('')
  const [primary, setPrimary] = useState(true)
  const [pickup, setPickup] = useState(true)
  const [notifications, setNotifications] = useState(true)
  const version = useRef(0)

  useEffect(() => {
    version.current++
    if (isOpen) {
      setMode('none'); setSearch(''); setOptions([]); setSelected(null); setError(''); setBusy(false)
      setFirst(''); setLast(''); setPhone(''); setEmail(''); setRelationship('')
      setPrimary(true); setPickup(true); setNotifications(true)
    }
  }, [isOpen])

  const find = async () => {
    const ticket = ++version.current
    setBusy(true); setError(''); setSelected(null)
    try {
      const result = await personsApi.registrationGuardianOptions(search.trim())
      if (ticket === version.current) setOptions(result.data)
    } catch {
      if (ticket === version.current) { setOptions([]); setError('Veli araması tamamlanamadı. Tekrar deneyin.') }
    } finally { if (ticket === version.current) setBusy(false) }
  }

  const validateGuardian = () => {
    if (mode === 'existing' && !selected) return 'Mevcut veli listesinden bir kişi seçin.'
    if (mode === 'new' && (!first.trim() || !last.trim())) return 'Yeni velinin adını ve soyadını girin.'
    if (mode === 'new' && email && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) return 'Veli e-postasını kontrol edin.'
    return null
  }

  return <PersonFormModal isOpen={isOpen} onClose={onClose} onSaved={onSaved} title="Yeni Sporcu" forcedRole="sporcu" athleteOnly
    extraDirty={mode !== 'none'} validateExtra={validateGuardian}
    onCreate={async athlete => (await personsApi.registerAthlete({
      athlete,
      ...(mode === 'existing' && selected ? { guardian_person_id: selected.id } : {}),
      ...(mode === 'new' ? { new_guardian: { first_name: first.trim(), last_name: last.trim(), role_codes: ['veli'], ...(phone ? { phone } : {}), ...(email ? { email: email.trim() } : {}) } } : {}),
      ...(mode !== 'none' ? { relationship_type: relationship || null, is_primary: primary, can_pickup: pickup, can_receive_notifications: notifications } : {}),
    })).data}
    extraFields={<fieldset className="form-group" style={{ border: '1px solid var(--color-border)', borderRadius: 8, padding: 16 }}>
      <legend>Veli Bilgileri (isteğe bağlı)</legend>
      <label className="form-label" htmlFor="guardian-mode">Veli seçimi</label>
      <select id="guardian-mode" className="form-select" value={mode} onChange={e => { version.current++; setMode(e.target.value as Mode); setError(''); setBusy(false) }}>
        <option value="none">Şimdilik veli ekleme</option><option value="existing">Mevcut veliyi seç</option><option value="new">Yeni veli oluştur</option>
      </select>
      {mode === 'none' && <p>Veliyi daha sonra sporcu ayrıntısından ekleyebilirsiniz.</p>}
      {mode === 'existing' && <div>
        <label className="form-label" htmlFor="registration-guardian-search">Veli ara</label>
        <input id="registration-guardian-search" className="form-input" value={search} placeholder="En az 3 karakter: ad, e-posta veya telefon" onChange={e => { version.current++; setSearch(e.target.value); setOptions([]); setSelected(null); setBusy(false) }} />
        <button type="button" className="btn btn-secondary" onClick={find} disabled={busy || search.trim().length < 3}>{busy ? 'Aranıyor…' : 'Veli Ara'}</button>
        {options.map(option => <button type="button" key={option.id} className="btn btn-ghost" onClick={() => setSelected(option)}>{option.first_name} {option.last_name} {option.phone || ''}</button>)}
        {selected && <p>Seçilen veli: <strong>{selected.first_name} {selected.last_name}</strong></p>}
        {error && <p role="alert">{error}</p>}
      </div>}
      {mode === 'new' && <div className="form-row" style={{ marginTop: 12 }}>
        <div className="form-group"><label className="form-label" htmlFor="guardian-first">Veli Adı *</label><input id="guardian-first" className="form-input" maxLength={100} value={first} onChange={e => setFirst(e.target.value)} /></div>
        <div className="form-group"><label className="form-label" htmlFor="guardian-last">Veli Soyadı *</label><input id="guardian-last" className="form-input" maxLength={100} value={last} onChange={e => setLast(e.target.value)} /></div>
        <div className="form-group"><label className="form-label" htmlFor="guardian-phone">Veli Telefonu</label><input id="guardian-phone" className="form-input" type="tel" maxLength={20} value={phone} onChange={e => setPhone(e.target.value)} /></div>
        <div className="form-group"><label className="form-label" htmlFor="guardian-email">Veli E-postası</label><input id="guardian-email" className="form-input" type="email" value={email} onChange={e => setEmail(e.target.value)} /></div>
      </div>}
      {mode !== 'none' && <div style={{ display: 'grid', gap: 10, marginTop: 12 }}>
        <label htmlFor="guardian-relationship">Yakınlık</label><select id="guardian-relationship" className="form-select" value={relationship} onChange={e => setRelationship(e.target.value)}><option value="">Seçiniz</option><option value="anne">Anne</option><option value="baba">Baba</option><option value="vasi">Vasi</option><option value="diger">Diğer</option></select>
        <label><input type="checkbox" checked={primary} onChange={e => setPrimary(e.target.checked)} /> Birincil veli</label>
        <label><input type="checkbox" checked={pickup} onChange={e => setPickup(e.target.checked)} /> Teslim alma yetkisi</label>
        <label><input type="checkbox" checked={notifications} onChange={e => setNotifications(e.target.checked)} /> Bildirim alma yetkisi</label>
        <p>Sporcu ve veli bağlantısı birlikte kaydedilir. Sistem hesabı açılmaz.</p>
      </div>}
    </fieldset>}
  />
}
