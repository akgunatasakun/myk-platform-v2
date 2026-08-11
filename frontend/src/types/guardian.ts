/**
 * Veli-sporcu bağlantısı tipleri — backend PersonGuardian şemalarıyla senkron.
 */

export interface PersonMiniOut {
  id: string
  first_name: string
  last_name: string
  member_number: string | null
  phone: string | null
}

export interface PersonGuardian {
  id: string
  club_id: string
  athlete_person_id: string
  guardian_person_id: string
  relationship_type: string | null
  is_primary: boolean
  can_pickup: boolean
  can_receive_notifications: boolean
  created_at: string
  updated_at: string
  guardian: PersonMiniOut
}

export interface PersonGuardianCreate {
  guardian_person_id: string
  relationship_type?: string | null
  is_primary?: boolean
  can_pickup?: boolean
  can_receive_notifications?: boolean
}

export interface PersonGuardianUpdate {
  relationship_type?: string | null
  is_primary?: boolean | null
  can_pickup?: boolean | null
  can_receive_notifications?: boolean | null
}

export interface GuardianAthlete {
  id: string
  club_id: string
  athlete_person_id: string
  guardian_person_id: string
  relationship_type?: string | null
  is_primary: boolean
  can_pickup: boolean
  can_receive_notifications: boolean
  created_at: string
  updated_at: string
  athlete: {
    id: string
    first_name: string
    last_name: string
    member_number?: string | null
    phone?: string | null
  }
}
