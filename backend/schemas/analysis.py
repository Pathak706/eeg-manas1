from datetime import datetime
from pydantic import BaseModel


class ClinicalFlagSchema(BaseModel):
    flag_type: str
    severity: str
    onset_sec: float
    duration_sec: float
    channels_involved: list[str]
    description: str


class BiomarkerSummarySchema(BaseModel):
    alpha_power: float
    beta_power: float
    theta_power: float
    delta_power: float
    gamma_power: float
    frontal_alpha_asymmetry: float
    alpha_beta_ratio: float
    theta_beta_ratio: float


class EpochResultSchema(BaseModel):
    epoch_index: int
    start_time_sec: float
    end_time_sec: float
    depression_contribution: float
    artifact_probability: float
    channel_attention: dict[str, float]
    dominant_frequency_hz: float
    band_powers: dict[str, float]
    frontal_alpha_asymmetry: float = 0.0
    confidence: float

    model_config = {"from_attributes": True}


class AnalysisResultFull(BaseModel):
    id: int
    study_id: int
    model_version: str
    depression_severity_score: float
    depression_risk_level: str
    frontal_alpha_asymmetry: float
    biomarkers: BiomarkerSummarySchema
    clinical_impression: str
    background_rhythm: str
    clinical_flags: list[ClinicalFlagSchema]
    processing_time_ms: int
    epochs: list[EpochResultSchema]
    created_at: datetime

    model_config = {"from_attributes": True}


class DepressionTrendPoint(BaseModel):
    study_id: int
    study_date: str
    depression_severity_score: float
    depression_risk_level: str
    frontal_alpha_asymmetry: float
    biomarkers: BiomarkerSummarySchema
