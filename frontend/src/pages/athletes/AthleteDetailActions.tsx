import { canManageAthleteProfiles, canReadPersonCards } from '@/config/operationAccess'

interface Props {
  role?: string
  hasProfile: boolean
  onEdit: () => void
  onPerson: () => void
}

export default function AthleteDetailActions({ role, hasProfile, onEdit, onPerson }: Props) {
  return <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
    {canManageAthleteProfiles(role) && <button className="btn btn-secondary" onClick={onEdit}>
      {hasProfile ? 'Profil Düzenle' : 'Profil Oluştur'}
    </button>}
    {canReadPersonCards(role) && <button className="btn btn-ghost btn-sm" onClick={onPerson} title="Kişi profiline git">
      Kişi Kartı →
    </button>}
  </div>
}
