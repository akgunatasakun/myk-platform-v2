import apiClient from './client';
import type { Person, PersonCreate, PersonCreateOut, PersonListResponse, PersonUpdate } from '@/types/person';
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

export interface AthleteRegistration {
  athlete: PersonCreate
  guardian_person_id?: string
  new_guardian?: PersonCreate
  relationship_type?: string | null
  is_primary?: boolean
  can_pickup?: boolean
  can_receive_notifications?: boolean
}

export const personsApi = {
  registerAthlete: (body: AthleteRegistration) => apiClient.post<PersonCreateOut>('/persons/athlete-registration', body),
  registrationGuardianOptions: (search: string) => apiClient.get<Pick<Person, 'id' | 'first_name' | 'last_name' | 'phone'>[]>('/persons/guardian-options', { params: { search } }),
  list: (params?: PersonListParams) =>
    apiClient.get<PersonListResponse>('/persons', { params }),
  listActiveCoaches: async (): Promise<Person[]> => {
    const coaches: Person[] = [];
    let total: number;
    do {
      const { data } = await personsApi.list({
        skip: coaches.length,
        limit: 100,
        is_active: true,
        role_code: 'antrenor',
      });
      total = data.total;
      if (data.items.length === 0 && coaches.length < total) {
        throw new Error('Antrenör listesi tamamlanamadı.');
      }
      coaches.push(...data.items);
    } while (coaches.length < total);
    return coaches;
  },
  get: (id: string) =>
    apiClient.get<Person>(`/persons/${id}`),
  create: (data: PersonCreate) =>
    apiClient.post<PersonCreateOut>('/persons', data),
  update: (id: string, data: PersonUpdate) =>
    apiClient.patch<Person>(`/persons/${id}`, data),
  delete: (id: string) =>
    apiClient.delete(`/persons/${id}`),

  // ── Hesap oluşturma ───────────────────────────────────────────────────────
  createAccount: (personId: string, roleCode: string) =>
    apiClient.post<{ user_id: string; email: string; role: string; temp_password: string }>(
      `/persons/${personId}/create-account`,
      { role_code: roleCode }
    ),

  // ── Guardian reverse lookup ───────────────────────────────────────────────
  getAthletes: (guardianPersonId: string) =>
    apiClient.get<GuardianAthlete[]>(`/persons/${guardianPersonId}/athletes`),

  guardianOptions: (athleteId: string, search: string) =>
    apiClient.get<Pick<Person, 'id' | 'first_name' | 'last_name' | 'phone'>[]>(`/persons/${athleteId}/guardian-options`, { params: { search } }),
  createGuardianForAthlete: (athleteId: string, person: PersonCreate, link: Omit<PersonGuardianCreate, 'guardian_person_id'>) =>
    apiClient.post<PersonCreateOut>(`/persons/${athleteId}/guardians/new`, { person, ...link }),

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
