import client from './client'
import type { Study, ProgressStatus, DisplayEEGData, ExtractedReportText } from '../types'

export const studiesApi = {
  listForPatient: (patientId: number) =>
    client.get<Study[]>(`/studies/by-patient/${patientId}`).then((r) => r.data),

  get: (id: number) => client.get<Study>(`/studies/${id}`).then((r) => r.data),

  uploadFile: (patientId: number, file: File, onProgress?: (pct: number) => void) => {
    const form = new FormData()
    form.append('patient_id', String(patientId))
    form.append('file', file)
    return client
      .post<Study>('/studies/upload', form, {
        headers: { 'Content-Type': 'multipart/form-data' },
        onUploadProgress: (e) => {
          if (onProgress && e.total) onProgress(Math.round((e.loaded / e.total) * 100))
        },
      })
      .then((r) => r.data)
  },

  createDemo: (patientId: number, includeSeizure = true) =>
    client
      .post<Study>('/studies/demo', null, {
        params: { patient_id: patientId, include_seizure: includeSeizure },
      })
      .then((r) => r.data),

  getProgress: (id: number) =>
    client.get<ProgressStatus>(`/studies/${id}/progress`).then((r) => r.data),

  getDisplayData: (id: number, startSec: number, endSec: number) =>
    client
      .get<DisplayEEGData>(`/studies/${id}/display-data`, {
        params: { start_sec: startSec, end_sec: endSec },
      })
      .then((r) => r.data),

  uploadPdf: (patientId: number, file: File, onProgress?: (pct: number) => void) => {
    const form = new FormData()
    form.append('patient_id', String(patientId))
    form.append('file', file)
    return client
      .post<Study>('/studies/pdf/upload', form, {
        headers: { 'Content-Type': 'multipart/form-data' },
        onUploadProgress: (e) => {
          if (onProgress && e.total) onProgress(Math.round((e.loaded / e.total) * 100))
        },
      })
      .then((r) => r.data)
  },

  getExtractedText: (id: number) =>
    client.get<ExtractedReportText>(`/analysis/${id}/extracted-text`).then((r) => r.data),
}
