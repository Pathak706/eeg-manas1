import client from './client'
import type { AnalysisResult } from '../types'

export const analysisApi = {
  get: (studyId: number) =>
    client.get<AnalysisResult>(`/analysis/${studyId}`).then((r) => r.data),

  getReportUrl: (studyId: number) => {
    const base = (import.meta.env.VITE_API_URL || '/api').replace(/\/$/, '')
    return `${base}/analysis/${studyId}/report/html`
  },
}
