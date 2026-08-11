export interface ClubSettings {
  id: string
  name: string
  slug: string
  plan: string
  is_active: boolean
  phone?: string | null
  email?: string | null
  website?: string | null
  address?: string | null
  timezone: string
  currency: string
  created_at: string
  updated_at: string
}

export interface ClubSettingsUpdate {
  name?: string
  phone?: string
  email?: string
  website?: string
  address?: string
  timezone?: string
  currency?: 'TRY' | 'EUR' | 'USD'
}

export interface Branch {
  id: string
  club_id: string
  name: string
  is_active: boolean
  sort_order: number
  created_at: string
}

export interface BranchCreate {
  name: string
  sort_order?: number
}

export interface BranchUpdate {
  name?: string
  is_active?: boolean
  sort_order?: number
}
