import apiClient from './client';
import type { Person, PersonCreate, PersonListResponse, PersonUpdate } from '@/types/person';
import type {
  GuardianAthlete,
  PersonGuardian,
  PersonGuardianCreate,
  PersonGuardianUpdate,
} from '@/types/guardian';

export interface PersonListParams {
  skip?: number;
  limit?: number;
  search?: string;
  role_code?: string;
  is_active?: boolean;
}

export const personsApi = {
  list: (params?: PersonListParams) =>
    apiClient.get<PersonListResponse>('/persons', { params }),
  get: (id: string) =>
    apiClient.get<Person>(`/persons/${id}`),
  create: (data: PersonCreate) =>
    apiClient.post<Person>('/persons', data),
  update: (id: string, data: PersonUpdate) =>
    apiClient.patch<Person>(`/persons/${id}`, data),
  delete: (id: string) =>
    apiClient.delete(`/persons/${id}`),

  // ── Guardian reverse lookup ───────────────────────────────────────────────
  getAthletes: (guardianPersonId: string) =>
    apiClient.get<GuardianAthlete[]>(`/persons/${guardianPersonId}/athletes`),

  // ── Guardian CRUD ─────────────────────────────────────────────────────────
  getGuardians: (personId: string) =>
    apiClient.get<PersonGuardian[]>(`/persons/${personId}/guardians`),
  addGuardian: (personId: string, data: PersonGuardianCreate) =>
    apiClient.post<PersonGuardian>(`/persons/${personId}/guardians`, data),
  updateGuardian: (personId: string, guardianId: string, data: PersonGuardianUpdate) =>
    apiClient.patch<PersonGuardian>(`/persons/${personId}/guardians/${guardianId}`, data),
  deleteGuardian: (personId: string, guardianId: string) =>
    apiClient.delete(`/persons/${personId}/guardians/${guardianId}`),
};
