from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func

from db.base import get_db
from models.patient import Patient
from models.study import Study
from schemas.patient import PatientCreate, PatientUpdate, PatientRead

router = APIRouter(prefix="/patients", tags=["patients"])


def _to_read(patient: Patient, db: Session) -> PatientRead:
    count = db.query(func.count(Study.id)).filter(Study.patient_id == patient.id).scalar()
    data = PatientRead.model_validate(patient)
    data.study_count = count or 0
    return data


@router.post("", response_model=PatientRead, status_code=201)
def create_patient(body: PatientCreate, db: Session = Depends(get_db)):
    existing = db.query(Patient).filter(Patient.mrn == body.mrn).first()
    if existing:
        raise HTTPException(status_code=409, detail=f"MRN '{body.mrn}' already exists")
    patient = Patient(**body.model_dump())
    db.add(patient)
    db.commit()
    db.refresh(patient)
    return _to_read(patient, db)


@router.get("", response_model=list[PatientRead])
def list_patients(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    search: str = Query(""),
    db: Session = Depends(get_db),
):
    q = db.query(Patient)
    if search:
        term = f"%{search}%"
        q = q.filter(
            Patient.name.ilike(term) | Patient.mrn.ilike(term)
        )
    patients = q.offset(skip).limit(limit).all()
    return [_to_read(p, db) for p in patients]


@router.get("/{patient_id}", response_model=PatientRead)
def get_patient(patient_id: int, db: Session = Depends(get_db)):
    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    return _to_read(patient, db)


@router.put("/{patient_id}", response_model=PatientRead)
def update_patient(patient_id: int, body: PatientUpdate, db: Session = Depends(get_db)):
    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(patient, field, value)
    db.commit()
    db.refresh(patient)
    return _to_read(patient, db)


@router.delete("/{patient_id}", status_code=204)
def delete_patient(patient_id: int, db: Session = Depends(get_db)):
    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    db.delete(patient)
    db.commit()
