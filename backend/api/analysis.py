import json
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from db.base import get_db
from models.study import Study
from models.analysis import AnalysisResult, EpochResult
from schemas.analysis import (
    AnalysisResultFull, EpochResultSchema, ClinicalFlagSchema,
    BiomarkerSummarySchema, DepressionTrendPoint,
)
from schemas.study import ExtractedReportText
from services.report_generator import ReportGenerator

router = APIRouter(prefix="/analysis", tags=["analysis"])


def _parse_biomarkers(analysis: AnalysisResult) -> BiomarkerSummarySchema:
    try:
        bm = json.loads(analysis.biomarkers_json)
    except Exception:
        bm = {}
    return BiomarkerSummarySchema(
        alpha_power=bm.get("alpha_power", 0),
        beta_power=bm.get("beta_power", 0),
        theta_power=bm.get("theta_power", 0),
        delta_power=bm.get("delta_power", 0),
        gamma_power=bm.get("gamma_power", 0),
        frontal_alpha_asymmetry=bm.get("frontal_alpha_asymmetry", 0),
        alpha_beta_ratio=bm.get("alpha_beta_ratio", 0),
        theta_beta_ratio=bm.get("theta_beta_ratio", 0),
    )


def _parse_analysis(analysis: AnalysisResult) -> AnalysisResultFull:
    epochs = []
    for ep in analysis.epochs:
        epochs.append(EpochResultSchema(
            epoch_index=ep.epoch_index,
            start_time_sec=ep.start_time_sec,
            end_time_sec=ep.end_time_sec,
            depression_contribution=ep.depression_contribution,
            artifact_probability=ep.artifact_probability,
            channel_attention=json.loads(ep.channel_attention),
            dominant_frequency_hz=ep.dominant_frequency_hz,
            band_powers=json.loads(ep.band_powers),
            frontal_alpha_asymmetry=ep.frontal_alpha_asymmetry,
            confidence=ep.confidence,
        ))

    flags = [
        ClinicalFlagSchema(**f)
        for f in json.loads(analysis.clinical_flags)
    ]

    return AnalysisResultFull(
        id=analysis.id,
        study_id=analysis.study_id,
        model_version=analysis.model_version,
        depression_severity_score=analysis.depression_severity_score,
        depression_risk_level=analysis.depression_risk_level,
        frontal_alpha_asymmetry=analysis.frontal_alpha_asymmetry,
        biomarkers=_parse_biomarkers(analysis),
        clinical_impression=analysis.clinical_impression,
        background_rhythm=analysis.background_rhythm,
        clinical_flags=flags,
        processing_time_ms=analysis.processing_time_ms,
        epochs=epochs,
        created_at=analysis.created_at,
    )


@router.get("/{study_id}", response_model=AnalysisResultFull)
def get_analysis(study_id: int, db: Session = Depends(get_db)):
    analysis = db.query(AnalysisResult).filter(AnalysisResult.study_id == study_id).first()
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found or not yet complete")
    return _parse_analysis(analysis)


@router.get("/{study_id}/extracted-text", response_model=ExtractedReportText)
def get_extracted_text(study_id: int, db: Session = Depends(get_db)):
    """Return the markdown text extracted from a PDF-sourced study."""
    study = db.query(Study).filter(Study.id == study_id).first()
    if not study:
        raise HTTPException(status_code=404, detail="Study not found")
    if study.source_type != "pdf":
        raise HTTPException(status_code=400, detail="This endpoint is only for PDF-sourced studies")

    analysis = db.query(AnalysisResult).filter(AnalysisResult.study_id == study_id).first()
    source_confidence = "UNKNOWN"
    if analysis:
        impression = analysis.clinical_impression or ""
        for level in ("HIGH", "MEDIUM", "LOW"):
            if f"Source confidence: {level}" in impression:
                source_confidence = level
                break

    return ExtractedReportText(
        study_id=study_id,
        markdown_text=study.extracted_text or "",
        source_confidence=source_confidence,
    )


@router.get("/{study_id}/report/html", response_class=HTMLResponse)
def get_report_html(study_id: int, db: Session = Depends(get_db)):
    analysis = db.query(AnalysisResult).filter(AnalysisResult.study_id == study_id).first()
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")

    study = db.query(Study).filter(Study.id == study_id).first()
    from models.patient import Patient
    patient = db.query(Patient).filter(Patient.id == study.patient_id).first()

    generator = ReportGenerator()
    report_data = generator.generate_json_report(
        _parse_analysis(analysis), study, patient
    )
    html = generator.generate_html_report(report_data)
    return HTMLResponse(content=html)
