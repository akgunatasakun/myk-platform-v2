export type ApplicationStatus =
  | 'draft'
  | 'submitted'
  | 'approved'
  | 'rejected'
  | 'cancelled';

export interface MembershipApplication {
  id: string;
  club_id: string;
  person_id: string | null;
  application_number: string | null;
  status: ApplicationStatus;

  // Başvuru sahibi
  first_name: string | null;
  last_name: string | null;
  national_id?: string | null;
  birth_date?: string | null;
  gender?: string | null;
  phone?: string | null;
  email?: string | null;
  address?: string | null;
  emergency_contact_name?: string | null;
  emergency_contact_phone?: string | null;
  blood_type?: string | null;
  guardian_name?: string | null;
  guardian_phone?: string | null;
  program_preference?: string | null;

  // PDF / imza
  has_pdf: boolean;
  pdf_url?: string | null;
  pdf_generated_at?: string | null;
  has_signature: boolean;
  signature_url?: string | null;
  signed_at?: string | null;

  // Onay / ret / iptal
  approved_at?: string | null;
  rejected_at?: string | null;
  rejection_reason?: string | null;
  cancelled_at?: string | null;
  cancellation_reason?: string | null;
  submitted_at?: string | null;

  is_deleted: boolean;
  created_at: string;
  updated_at: string;
}

export interface ApplicationListResponse {
  items: MembershipApplication[];
  total: number;
  skip: number;
  limit: number;
}
