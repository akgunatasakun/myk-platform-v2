/**
 * Kullanıcı hesabı tip tanımları — Sprint 18.
 * backend/app/schemas/user.py ile senkron tutulmalı.
 */
import type { Role } from './auth';

export interface UserOut {
  id: string;
  club_id: string;
  email: string;
  full_name: string;
  role: Role;
  is_active: boolean;
  is_deleted: boolean;
  person_id: string | null;
  must_change_password: boolean;
  last_login_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface UserListItem {
  id: string;
  email: string;
  full_name: string;
  role: Role;
  is_active: boolean;
  person_id: string | null;
  last_login_at: string | null;
  created_at: string;
}

export interface UserListOut {
  items: UserListItem[];
  total: number;
  skip: number;
  limit: number;
}

export interface UserCreate {
  email: string;
  full_name: string;
  role: Role;
  person_id?: string | null;
}

export interface UserUpdate {
  role?: Role;
  is_active?: boolean;
  full_name?: string;
}

/** Oluşturma yanıtı — temp_password yalnızca bir kez döner. */
export interface UserCreateResponse extends UserOut {
  temp_password: string;
}

/** Parola sıfırlama yanıtı — temp_password yalnızca bir kez döner. */
export interface PasswordResetResponse {
  user_id: string;
  temp_password: string;
}
