import json
import uuid
from pathlib import Path

import numpy as np
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, BackgroundTasks, Query
from sqlalchemy.orm import Session

from config import settings
from db.base import get_db, SessionLocal
from models.patient import Patient
from models.study import Study
from schemas.study import StudyRead, ProgressStatus, DisplayEEGData
from services.analysis_pipeline import run_pipeline_background
from services.synthetic_eeg import SyntheticEEGGenerator

router = APIRouter(prefix="/studies", tags=["studies"])


def _study_to_read(study: Study) -> StudyRead:
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
    )


@router.post("/upload", response_model=StudyRead, status_code=201)
async def upload_study(
    background_tasks: BackgroundTasks,
    patient_id: int = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")

    if file.size and file.size > settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024:
        raise HTTPException(status_code=413, detail="File too large")

    # Save file
    upload_dir = Path(settings.UPLOAD_DIR)
    upload_dir.mkdir(parents=True, exist_ok=True)
    file_ext = Path(file.filename or "recording.edf").suffix or ".edf"
    file_name = f"{uuid.uuid4()}{file_ext}"
    file_path = upload_dir / file_name

    content = await file.read()
    file_path.write_bytes(content)

    study = Study(
        patient_id=patient_id,
        file_path=str(file_path),
        status="uploaded",
        is_synthetic=False,
    )
    db.add(study)
    db.commit()
    db.refresh(study)

    # Trigger analysis in background
    background_tasks.add_task(run_pipeline_background, study.id, SessionLocal)

    return _study_to_read(study)


@router.post("/demo", response_model=StudyRead, status_code=201)
async def create_demo_study(
    background_tasks: BackgroundTasks,
    patient_id: int = Query(...),
    include_seizure: bool = Query(True),  # kept for backwards compat
    include_depression: bool = Query(True),
    db: Session = Depends(get_db),
):
    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")

    # Generate synthetic EEG — unique seed per patient so waveforms differ
    import random as _random
    generator = SyntheticEEGGenerator()
    result = generator.generate(
        include_depression=include_depression,
        seed=_random.randint(0, 2**31),
    )

    # Save as .npz
    upload_dir = Path(settings.UPLOAD_DIR)
    upload_dir.mkdir(parents=True, exist_ok=True)
    file_name = f"synthetic_{uuid.uuid4()}.npz"
    file_path = upload_dir / file_name
    np.savez_compressed(
        str(file_path),
        data=result.data,
        channels=np.array(result.channel_names),
        sample_rate=np.array(result.sample_rate),
        duration_sec=np.array(result.duration_sec),
    )

    study = Study(
        patient_id=patient_id,
        file_path=str(file_path),
        status="uploaded",
        is_synthetic=True,
        sample_rate_hz=result.sample_rate,
        channel_count=len(result.channel_names),
        channel_names=json.dumps(result.channel_names),
        recording_duration_sec=result.duration_sec,
    )
    db.add(study)
    db.commit()
    db.refresh(study)

    # Trigger analysis in background
    background_tasks.add_task(run_pipeline_background, study.id, SessionLocal)

    return _study_to_read(study)


@router.get("/{study_id}", response_model=StudyRead)
def get_study(study_id: int, db: Session = Depends(get_db)):
    study = db.query(Study).filter(Study.id == study_id).first()
    if not study:
        raise HTTPException(status_code=404, detail="Study not found")
    return _study_to_read(study)


@router.get("/{study_id}/progress", response_model=ProgressStatus)
def get_progress(study_id: int, db: Session = Depends(get_db)):
    study = db.query(Study).filter(Study.id == study_id).first()
    if not study:
        raise HTTPException(status_code=404, detail="Study not found")
    return ProgressStatus(
        study_id=study.id,
        status=study.status,
        epoch_progress=study.epoch_progress,
        epoch_total=study.epoch_total,
        error_message=study.error_message,
    )


@router.get("/{study_id}/display-data", response_model=DisplayEEGData)
def get_display_data(
    study_id: int,
    start_sec: float = Query(0.0, ge=0),
    end_sec: float = Query(10.0, gt=0),
    db: Session = Depends(get_db),
):
    study = db.query(Study).filter(Study.id == study_id).first()
    if not study:
        raise HTTPException(status_code=404, detail="Study not found")
    if study.status not in ("analyzing", "complete"):
        raise HTTPException(status_code=400, detail=f"Display data not ready (status: {study.status})")
    if not study.display_data_path or not Path(study.display_data_path).exists():
        raise HTTPException(status_code=404, detail="Display data file not found")

    npz = np.load(study.display_data_path)
    display_data = npz["data"]           # (n_ch, n_samples)
    channels = list(npz["channels"])
    sr = int(npz["sample_rate"])
    duration_sec = float(npz["duration_sec"])

    # Clamp window
    end_sec = min(end_sec, duration_sec)
    start_sec = max(0.0, start_sec)

    start_idx = int(start_sec * sr)
    end_idx = int(end_sec * sr)

    window = display_data[:, start_idx:end_idx]
    n_window = window.shape[1]
    times = [round(start_sec + i / sr, 4) for i in range(n_window)]

    data_dict = {ch: window[i].tolist() for i, ch in enumerate(channels)}

    return DisplayEEGData(
        study_id=study_id,
        start_sec=start_sec,
        end_sec=end_sec,
        sample_rate=sr,
        channels=channels,
        times=times,
        data=data_dict,
        duration_sec=duration_sec,
    )


@router.get("/by-patient/{patient_id}", response_model=list[StudyRead])
def list_studies_for_patient(patient_id: int, db: Session = Depends(get_db)):
    studies = db.query(Study).filter(Study.patient_id == patient_id).order_by(Study.created_at.desc()).all()
    return [_study_to_read(s) for s in studies]


@router.get("/depression-trend/{patient_id}")
def get_depression_trend(patient_id: int, db: Session = Depends(get_db)):
    """Return chronological depression scores across all completed studies for a patient."""
    from models.analysis import AnalysisResult
    import json as _json

    studies = (
        db.query(Study)
        .filter(Study.patient_id == patient_id, Study.status == "complete")
        .order_by(Study.created_at.asc())
        .all()
    )

    trend = []
    for s in studies:
        analysis = db.query(AnalysisResult).filter(AnalysisResult.study_id == s.id).first()
        if not analysis:
            continue
        try:
            bm = _json.loads(analysis.biomarkers_json)
        except Exception:
            bm = {}
        trend.append({
            "study_id": s.id,
            "study_date": s.study_date.isoformat() if s.study_date else "",
            "depression_severity_score": analysis.depression_severity_score,
            "depression_risk_level": analysis.depression_risk_level,
            "frontal_alpha_asymmetry": analysis.frontal_alpha_asymmetry,
            "biomarkers": {
                "alpha_power": bm.get("alpha_power", 0),
                "beta_power": bm.get("beta_power", 0),
                "theta_power": bm.get("theta_power", 0),
                "delta_power": bm.get("delta_power", 0),
                "gamma_power": bm.get("gamma_power", 0),
                "frontal_alpha_asymmetry": bm.get("frontal_alpha_asymmetry", 0),
                "alpha_beta_ratio": bm.get("alpha_beta_ratio", 0),
                "theta_beta_ratio": bm.get("theta_beta_ratio", 0),
            },
        })

    return trend
