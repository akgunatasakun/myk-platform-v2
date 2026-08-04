export type PersonRoleCode = 'sporcu' | 'uye' | 'veli' | 'antrenor' | 'personel' | 'misafir';
export type Gender = 'erkek' | 'kadin' | 'belirtilmedi';
export type BloodType = 'A+' | 'A-' | 'B+' | 'B-' | 'AB+' | 'AB-' | '0+' | '0-';

export interface PersonRole {
  role_code: PersonRoleCode;
  assigned_at: string;
}

export interface Person {
  id: string;
  club_id: string;
  first_name: string;
  last_name: string;
  national_id?: string;
  birth_date?: string;
  gender?: Gender;
  phone?: string;
  email?: string;
  address?: string;
  emergency_contact_name?: string;
  emergency_contact_phone?: string;
  blood_type?: BloodType;
  notes?: string;
  avatar_url?: string;
  is_active: boolean;
  is_deleted: boolean;
  created_at: string;
  updated_at: string;
  roles: PersonRole[];
  role_codes: PersonRoleCode[];
}

export interface PersonListResponse {
  items: Person[];
  total: number;
  skip: number;
  limit: number;
}

export interface PersonCreate {
  first_name: string;
  last_name: string;
  national_id?: string;
  birth_date?: string;
  gender?: Gender;
  phone?: string;
  email?: string;
  address?: string;
  emergency_contact_name?: string;
  emergency_contact_phone?: string;
  blood_type?: BloodType;
  notes?: string;
  avatar_url?: string;
  role_codes?: PersonRoleCode[];
}

export interface PersonUpdate extends Partial<PersonCreate> {
  is_active?: boolean;
}
