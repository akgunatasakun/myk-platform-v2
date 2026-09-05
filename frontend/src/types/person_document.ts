/**
 * Kişisel evrak tip tanımları — backend PersonDocumentOut ve
 * HealthDocumentSummaryOut şemalarıyla senkron.
 */

export type PersonDocumentType =
  | 'profile_photo'
  | 'identity_copy'
  | 'health_report'
  | 'parental_permission'
  | 'undertaking'
  | 'waiver'
  | 'other'

export type ReviewStatus =
  | 'pending'
  | 'approved'
  | 'rejected'
  | 'expired'
  | 'superseded'

export type ScanStatus =
  | 'pending'
  | 'clean'
  | 'infected'
  | 'failed'
  | 'skipped_dev'

export type DeleteRequestStatus = 'pending' | 'approved' | 'rejected'

export interface DeleteRequest {
  reason: string
  requested_by_user_id: string
  status: DeleteRequestStatus
  created_at: string // ISO8601 datetime
}

export interface PersonDocumentOut {
  id: string
  club_id: string
  subject_person_id: string
  guardian_link_id: string | null
  document_type: PersonDocumentType
  original_filename: string
  mime_type: string
  size_bytes: number
  uploaded_at: string // ISO8601 datetime
  valid_until: string | null // ISO8601 date
  retain_until: string | null // ISO8601 date
  review_status: ReviewStatus
  scan_status: ScanStatus
  is_sensitive: boolean
  is_deleted: boolean
  supersedes_id: string | null
  rejection_reason: string | null
  reviewed_at: string | null // ISO8601 datetime
  processing_basis: string | null
  delete_request: DeleteRequest | null
}

export interface HealthDocumentSummaryOut {
  subject_person_id: string
  exists: boolean
  valid_until: string | null // ISO8601 date
}

export interface DeleteRequestOut {
  id: string
  document_id: string
  requested_by_user_id: string
  reason: string
  created_at: string // ISO8601 datetime
  status: DeleteRequestStatus
}
