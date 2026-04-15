from datetime import datetime
from pydantic import BaseModel


class StudyRead(BaseModel):
    id: int
    patient_id: int
    study_date: datetime
    recording_duration_sec: float
    sample_rate_hz: int
    channel_count: int
    channel_names: list[str]
    status: str
    error_message: str
    is_synthetic: bool
    epoch_progress: int
    epoch_total: int
    created_at: datetime
    source_type: str = "edf"
    original_filename: str = ""

    model_config = {"from_attributes": True}


class ExtractedReportText(BaseModel):
    study_id: int
    markdown_text: str
    source_confidence: str


class ProgressStatus(BaseModel):
    study_id: int
    status: str
    epoch_progress: int
    epoch_total: int
    error_message: str


class DisplayEEGData(BaseModel):
    study_id: int
    start_sec: float
    end_sec: float
    sample_rate: int
    channels: list[str]
    times: list[float]
    data: dict[str, list[float]]
    duration_sec: float
