/**
 * Auth tip tanımları — backend şemalarıyla senkron tutulmalı.
 */

export interface LoginRequest {
  club_slug: string;
  email: string;
  password: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  expires_in: number; // saniye
}

export interface UserResponse {
  id: string;
  club_id: string;
  email: string;
  full_name: string;
  role: Role;
  is_active: boolean;
  created_at: string; // ISO8601
}

export type Role =
  | 'super_admin'
  | 'kulup_yonetici'
  | 'baskan'
  | 'yk_uyesi'
  | 'genel_sekreter'
  | 'muhasebe'
  | 'sportif_direktor'
  | 'basantrenor'
  | 'antrenor'
  | 'personel'
  | 'saglik_sorumlusu'
  | 'guvenlik_operasyon'
  | 'veli'
  | 'sporcu'
  | 'uye'
  | 'misafir';

export interface AuthState {
  user: UserResponse | null;
  accessToken: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
}
