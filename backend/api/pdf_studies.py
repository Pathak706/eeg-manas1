"""
PDF Study Upload API.

POST /studies/pdf-upload — accepts a clinical report PDF, creates a Study record,
and triggers the PDF analysis pipeline in the background.
"""
import uuid
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, Form, HTTPException, UploadFile, File
from sqlalchemy.orm import Session

from config import settings
from db.base import get_db, SessionLocal
from models.patient import Patient
from models.study import Study
from schemas.study import StudyRead
from services.pdf_pipeline import run_pdf_pipeline_background

router = APIRouter(prefix="/studies/pdf", tags=["studies-pdf"])


def _study_to_read(study: Study) -> StudyRead:
    import json
    try:
        channels = json.loads(study.channel_names)
    except Exception:
        channels = []
    return StudyRead(
        id=study.id,
        patient_id=study.patient_id,
        study_date=study.study_date,
        recording_duration_sec=study.recording_duration_sec,
        sample_rate_hz=study.sample_rate_hz,
        channel_count=study.channel_count,
        channel_names=channels,
        status=study.status,
        error_message=study.error_message,
        is_synthetic=study.is_synthetic,
        epoch_progress=study.epoch_progress,
        epoch_total=study.epoch_total,
        created_at=study.created_at,
        source_type=study.source_type,
        original_filename=study.original_filename,
    )


@router.post("/upload", response_model=StudyRead, status_code=201)
async def upload_pdf_study(
    background_tasks: BackgroundTasks,
    patient_id: int = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """
    Upload a clinical EEG report PDF.

    The file is saved, a Study record is created with source_type='pdf',
    and the PDF analysis pipeline (text extraction → NLP → epoch synthesis)
    runs in the background.
    """
    # Validate patient
    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")

    # Validate file type
    original_name = file.filename or "report.pdf"
    if not original_name.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted for this endpoint")

    # Validate size
    content = await file.read()
    max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    if len(content) > max_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"File too large (max {settings.MAX_UPLOAD_SIZE_MB} MB)",
        )

    # Save to uploads directory
    upload_dir = Path(settings.UPLOAD_DIR)
    upload_dir.mkdir(parents=True, exist_ok=True)
    file_name = f"pdf_{uuid.uuid4()}.pdf"
    file_path = upload_dir / file_name
    file_path.write_bytes(content)

    # Create study record
    study = Study(
        patient_id=patient_id,
        file_path=str(file_path),
        status="uploaded",
        is_synthetic=False,
        source_type="pdf",
        original_filename=original_name,
    )
    db.add(study)
    db.commit()
    db.refresh(study)

    # Trigger PDF pipeline in background
    background_tasks.add_task(run_pdf_pipeline_background, study.id, SessionLocal)

    return _study_to_read(study)
