import client from './client'
import type { Patient, PatientCreate } from '../types'

export const patientsApi = {
  list: (search = '') =>
    client.get<Patient[]>('/patients', { params: { search, limit: 100 } }).then((r) => r.data),

  get: (id: number) => client.get<Patient>(`/patients/${id}`).then((r) => r.data),

  create: (data: PatientCreate) => client.post<Patient>('/patients', data).then((r) => r.data),

  delete: (id: number) => client.delete(`/patients/${id}`),
}
