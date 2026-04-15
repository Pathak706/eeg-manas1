import client from './client'
import type { AnalysisResult } from '../types'

export const analysisApi = {
  get: (studyId: number) =>
    client.get<AnalysisResult>(`/analysis/${studyId}`).then((r) => r.data),

  getReportUrl: (studyId: number) => `/api/analysis/${studyId}/report/html`,
}
