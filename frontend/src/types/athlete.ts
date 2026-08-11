export type DocumentStatus = 'gecerli' | 'yaklasan' | 'dolmus' | 'eksik'
export type AthleteLevel = 'baslangic' | 'orta' | 'ileri' | 'elit'

export interface AthleteProfileOut {
  sports_branch_id?: string | null
  sports_branch_name?: string | null
  class_name?: string | null
  level?: AthleteLevel | null

  license_no?: string | null
  license_expiry_date?: string | null
  license_status: DocumentStatus

  visa_expiry_date?: string | null
  visa_status: DocumentStatus

  health_report_expiry_date?: string | null
  health_status: DocumentStatus
  swimming_qualified: boolean

  allergies?: string | null
  special_conditions?: string | null

  kvkk_consent: boolean
  kvkk_consent_at?: string | null
  kvkk_text_version?: string | null
  photo_video_consent: boolean

  created_at: string
  updated_at: string
}

export interface AthleteListItem {
  person_id: string
  first_name: string
  last_name: string
  birth_date?: string | null
  gender?: string | null
  member_number?: string | null
  is_active: boolean

  sports_branch_name?: string | null
  class_name?: string | null
  level?: AthleteLevel | null

  license_no?: string | null
  license_expiry_date?: string | null
  license_status: DocumentStatus

  visa_expiry_date?: string | null
  visa_status: DocumentStatus

  health_report_expiry_date?: string | null
  health_status: DocumentStatus

  swimming_qualified: boolean
  kvkk_consent: boolean
  photo_video_consent: boolean

  has_profile: boolean
}

export interface AthleteListOut {
  items: AthleteListItem[]
  total: number
  skip: number
  limit: number
}

export interface AthleteDetailOut extends AthleteListItem {
  athlete_profile?: AthleteProfileOut | null
}

export interface AthleteAlertItem {
  person_id: string
  first_name: string
  last_name: string
  class_name?: string | null

  license_expiry_date?: string | null
  license_status: DocumentStatus

  visa_expiry_date?: string | null
  visa_status: DocumentStatus

  health_report_expiry_date?: string | null
  health_status: DocumentStatus

  kvkk_consent: boolean
  alerts: string[]
}

export interface AthleteProfileUpdate {
  sports_branch_id?: string | null
  class_name?: string | null
  level?: AthleteLevel | null

  license_no?: string | null
  license_expiry_date?: string | null
  visa_expiry_date?: string | null

  health_report_expiry_date?: string | null
  swimming_qualified?: boolean

  allergies?: string | null
  special_conditions?: string | null

  kvkk_consent?: boolean
  kvkk_text_version?: string | null
  photo_video_consent?: boolean
}
