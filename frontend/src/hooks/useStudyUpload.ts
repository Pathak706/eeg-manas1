import { useState, useEffect, useRef } from 'react'
import { studiesApi } from '../api/studies'
import type { Study, ProgressStatus } from '../types'

export type UploadStep = 'idle' | 'uploading' | 'preprocessing' | 'analyzing' | 'complete' | 'error'

interface UploadState {
  step: UploadStep
  study: Study | null
  uploadPercent: number
  epochProgress: number
  epochTotal: number
  error: string | null
}

export function useStudyUpload(patientId: number) {
  const [state, setState] = useState<UploadState>({
    step: 'idle',
    study: null,
    uploadPercent: 0,
    epochProgress: 0,
    epochTotal: 0,
    error: null,
  })
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const stopPolling = () => {
    if (pollRef.current) {
      clearInterval(pollRef.current)
      pollRef.current = null
    }
  }

  const startPolling = (studyId: number) => {
    stopPolling()
    pollRef.current = setInterval(async () => {
      try {
        const progress: ProgressStatus = await studiesApi.getProgress(studyId)
        const step = progress.status as UploadStep

        setState((prev) => ({
          ...prev,
          step,
          epochProgress: progress.epoch_progress,
          epochTotal: progress.epoch_total,
          error: progress.error_message || null,
        }))

        if (step === 'complete' || step === 'error') {
          stopPolling()
        }
      } catch {
        // transient network error — keep polling
      }
    }, 1500)
  }

  const upload = async (file: File) => {
    setState({ step: 'uploading', study: null, uploadPercent: 0, epochProgress: 0, epochTotal: 0, error: null })
    try {
      const study = await studiesApi.uploadFile(patientId, file, (pct) =>
        setState((prev) => ({ ...prev, uploadPercent: pct }))
      )
      setState((prev) => ({ ...prev, study, step: 'preprocessing' }))
      startPolling(study.id)
    } catch (e: any) {
      setState((prev) => ({ ...prev, step: 'error', error: e?.response?.data?.detail || 'Upload failed' }))
    }
  }

  const uploadPdf = async (file: File) => {
    setState({ step: 'uploading', study: null, uploadPercent: 0, epochProgress: 0, epochTotal: 0, error: null })
    try {
      const study = await studiesApi.uploadPdf(patientId, file, (pct) =>
        setState((prev) => ({ ...prev, uploadPercent: pct }))
      )
      setState((prev) => ({ ...prev, study, step: 'preprocessing' }))
      startPolling(study.id)
    } catch (e: any) {
      setState((prev) => ({ ...prev, step: 'error', error: e?.response?.data?.detail || 'PDF upload failed' }))
    }
  }

  const loadDemo = async (includeSeizure = true) => {
    setState({ step: 'uploading', study: null, uploadPercent: 100, epochProgress: 0, epochTotal: 0, error: null })
    try {
      const study = await studiesApi.createDemo(patientId, includeSeizure)
      setState((prev) => ({ ...prev, study, step: 'preprocessing' }))
      startPolling(study.id)
    } catch (e: any) {
      setState((prev) => ({ ...prev, step: 'error', error: e?.response?.data?.detail || 'Demo generation failed' }))
    }
  }

  const reset = () => {
    stopPolling()
    setState({ step: 'idle', study: null, uploadPercent: 0, epochProgress: 0, epochTotal: 0, error: null })
  }

  useEffect(() => () => stopPolling(), [])

  return { state, upload, uploadPdf, loadDemo, reset }
}
