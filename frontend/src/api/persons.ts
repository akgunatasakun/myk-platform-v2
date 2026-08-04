import apiClient from './client';
import type { Person, PersonCreate, PersonListResponse, PersonUpdate } from '@/types/person';

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
};
