/**
 * Public API istemcisi — kimlik doğrulama gerektirmeyen endpointler.
 * Ayrı bir axios instance kullanılır; token interceptor'ı yoktur.
 */
import axios from 'axios'

const publicClient = axios.create({
  baseURL: '/api/v1/public',
  headers: { 'Content-Type': 'application/json' },
})

export interface PublicApplicationData {
  club_slug: string
  first_name: string
  last_name: string
  email: string
  phone: string
  consent_accepted: boolean
  birth_date?: string
  gender?: string
  national_id?: string
  address?: string
  blood_type?: string
  emergency_contact_name?: string
  emergency_contact_phone?: string
  guardian_name?: string
  guardian_phone?: string
  program_preference?: string
}

export interface PublicApplicationResponse {
  id: string
  application_number: string | null
  status: string
  first_name: string | null
  last_name: string | null
}

export const publicApi = {
  submitApplication: (data: PublicApplicationData) =>
    publicClient.post<PublicApplicationResponse>('/membership-applications', data),
}
