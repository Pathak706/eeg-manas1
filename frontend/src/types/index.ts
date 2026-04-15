export interface Patient {
  id: number
  mrn: string
  name: string
  date_of_birth: string
  gender: string
  referring_physician: string
  notes: string
  created_at: string
  study_count: number
}

export interface PatientCreate {
  mrn: string
  name: string
  date_of_birth: string
  gender: string
  referring_physician?: string
  notes?: string
}

export interface Study {
  id: number
  patient_id: number
  study_date: string
  recording_duration_sec: number
  sample_rate_hz: number
  channel_count: number
  channel_names: string[]
  status: 'uploaded' | 'preprocessing' | 'analyzing' | 'complete' | 'error'
  error_message: string
  is_synthetic: boolean
  epoch_progress: number
  epoch_total: number
  created_at: string
  source_type: 'edf' | 'synthetic' | 'pdf'
  original_filename: string
}

export interface ProgressStatus {
  study_id: number
  status: Study['status']
  epoch_progress: number
  epoch_total: number
  error_message: string
}

export interface DisplayEEGData {
  study_id: number
  start_sec: number
  end_sec: number
  sample_rate: number
  channels: string[]
  times: number[]
  data: Record<string, number[]>
  duration_sec: number
}

export interface ClinicalFlag {
  flag_type: string
  severity: 'HIGH' | 'MEDIUM' | 'LOW'
  onset_sec: number
  duration_sec: number
  channels_involved: string[]
  description: string
}

export interface BiomarkerSummary {
  alpha_power: number
  beta_power: number
  theta_power: number
  delta_power: number
  gamma_power: number
  frontal_alpha_asymmetry: number
  alpha_beta_ratio: number
  theta_beta_ratio: number
}

export interface EpochResult {
  epoch_index: number
  start_time_sec: number
  end_time_sec: number
  depression_contribution: number
  artifact_probability: number
  channel_attention: Record<string, number>
  dominant_frequency_hz: number
  band_powers: Record<string, number>
  frontal_alpha_asymmetry: number
  confidence: number
}

export interface AnalysisResult {
  id: number
  study_id: number
  model_version: string
  depression_severity_score: number
  depression_risk_level: string
  frontal_alpha_asymmetry: number
  biomarkers: BiomarkerSummary
  clinical_impression: string
  background_rhythm: string
  clinical_flags: ClinicalFlag[]
  processing_time_ms: number
  epochs: EpochResult[]
  created_at: string
}

export interface ExtractedReportText {
  study_id: number
  markdown_text: string
  source_confidence: 'HIGH' | 'MEDIUM' | 'LOW' | 'UNKNOWN'
}

export interface DepressionTrendPoint {
  study_id: number
  study_date: string
  depression_severity_score: number
  depression_risk_level: string
  frontal_alpha_asymmetry: number
  biomarkers: BiomarkerSummary
}
