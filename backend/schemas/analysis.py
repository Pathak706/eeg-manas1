from datetime import datetime
from pydantic import BaseModel


class ClinicalFlagSchema(BaseModel):
    flag_type: str
    severity: str
    onset_sec: float
    duration_sec: float
    channels_involved: list[str]
    description: str


class EpochResultSchema(BaseModel):
    epoch_index: int
    start_time_sec: float
    end_time_sec: float
    seizure_probability: float
    artifact_probability: float
    channel_attention: dict[str, float]
    dominant_frequency_hz: float
    band_powers: dict[str, float]
    confidence: float

    model_config = {"from_attributes": True}


class AnalysisResultFull(BaseModel):
    id: int
    study_id: int
    model_version: str
    overall_seizure_probability: float
    clinical_impression: str
    background_rhythm: str
    clinical_flags: list[ClinicalFlagSchema]
    processing_time_ms: int
    epochs: list[EpochResultSchema]
    created_at: datetime

    model_config = {"from_attributes": True}
