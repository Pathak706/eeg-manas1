from datetime import date, datetime
from pydantic import BaseModel


class PatientCreate(BaseModel):
    mrn: str
    name: str
    date_of_birth: date
    gender: str
    referring_physician: str = ""
    notes: str = ""


class PatientUpdate(BaseModel):
    name: str | None = None
    date_of_birth: date | None = None
    gender: str | None = None
    referring_physician: str | None = None
    notes: str | None = None


class PatientRead(BaseModel):
    id: int
    mrn: str
    name: str
    date_of_birth: date
    gender: str
    referring_physician: str
    notes: str
    created_at: datetime
    study_count: int = 0

    model_config = {"from_attributes": True}
