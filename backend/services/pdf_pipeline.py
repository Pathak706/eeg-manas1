"""
PDF Analysis Pipeline — Depression Assessment.

Mirrors analysis_pipeline.py but works on extracted text instead of raw EEG signal.
Produces the same AnalysisResult + EpochResult rows so the frontend is unchanged.
"""
import json
import time
from pathlib import Path

import numpy as np
from sqlalchemy.orm import Session

from models.study import Study
from models.analysis import AnalysisResult, EpochResult
from services.pdf_ingestion import PdfIngestionService
from services.clinical_nlp import ClinicalNLPExtractor, ClinicalExtraction, FRONTAL_CHANNELS

CHANNELS_10_20 = [
    "Fp1", "Fp2", "F3", "F4", "C3", "C4", "P3", "P4",
    "O1", "O2", "F7", "F8", "T3", "T4", "T5", "T6",
    "Fz", "Cz", "Pz",
]
MODEL_VERSION = "manas1-pdf-depression-v0.1"
N_SYNTHETIC_EPOCHS = 30


class PdfAnalysisPipeline:
    def __init__(self, db: Session):
        self.db = db
        self.ingestion = PdfIngestionService()
        self.nlp = ClinicalNLPExtractor()

    async def run(self, study_id: int) -> AnalysisResult:
        study = self.db.query(Study).filter(Study.id == study_id).first()
        if not study:
            raise ValueError(f"Study {study_id} not found")
        try:
            return await self._execute(study)
        except Exception as e:
            study.status = "error"
            study.error_message = str(e)[:500]
            self.db.commit()
            raise

    async def _execute(self, study: Study) -> AnalysisResult:
        t_start = time.time()

        study.status = "preprocessing"
        self.db.commit()

        raw_text = self.ingestion.extract_text(Path(study.file_path))
        markdown_text = self.ingestion.to_markdown(raw_text)

        study.extracted_text = markdown_text
        study.epoch_total = N_SYNTHETIC_EPOCHS
        self.db.commit()

        study.status = "analyzing"
        self.db.commit()

        extraction: ClinicalExtraction = self.nlp.extract(markdown_text)

        study.recording_duration_sec = extraction.recording_duration_sec
        study.channel_names = json.dumps(CHANNELS_10_20)
        study.channel_count = len(CHANNELS_10_20)
        study.sample_rate_hz = 0
        self.db.commit()

        epoch_dicts = self._synthesise_epochs(extraction)
        clinical_impression = self._build_clinical_impression(extraction)

        processing_time_ms = int((time.time() - t_start) * 1000)

        # Biomarkers from extraction
        bp = extraction.band_powers
        biomarkers_dict = {
            "alpha_power": bp.get("alpha", 0),
            "beta_power": bp.get("beta", 0),
            "theta_power": bp.get("theta", 0),
            "delta_power": bp.get("delta", 0),
            "gamma_power": bp.get("gamma", 0),
            "frontal_alpha_asymmetry": extraction.frontal_alpha_asymmetry,
            "alpha_beta_ratio": bp.get("alpha", 0) / max(bp.get("beta", 0.01), 0.01),
            "theta_beta_ratio": bp.get("theta", 0) / max(bp.get("beta", 0.01), 0.01),
        }

        analysis = AnalysisResult(
            study_id=study.id,
            model_version=MODEL_VERSION,
            depression_severity_score=extraction.depression_severity_score,
            depression_risk_level=extraction.depression_risk_level,
            frontal_alpha_asymmetry=extraction.frontal_alpha_asymmetry,
            biomarkers_json=json.dumps(biomarkers_dict),
            clinical_impression=clinical_impression,
            background_rhythm=extraction.background_rhythm,
            clinical_flags=json.dumps(extraction.clinical_flags),
            processing_time_ms=processing_time_ms,
        )
        self.db.add(analysis)
        self.db.flush()

        epoch_rows = [
            EpochResult(
                analysis_id=analysis.id,
                epoch_index=ep["epoch_index"],
                start_time_sec=ep["start_time_sec"],
                end_time_sec=ep["end_time_sec"],
                depression_contribution=ep["depression_contribution"],
                artifact_probability=ep["artifact_probability"],
                channel_attention=json.dumps(ep["channel_attention"]),
                dominant_frequency_hz=ep["dominant_frequency_hz"],
                band_powers=json.dumps(ep["band_powers"]),
                frontal_alpha_asymmetry=ep["frontal_alpha_asymmetry"],
                confidence=ep["confidence"],
            )
            for ep in epoch_dicts
        ]
        self.db.bulk_save_objects(epoch_rows)

        study.status = "complete"
        study.epoch_progress = N_SYNTHETIC_EPOCHS
        self.db.commit()
        self.db.refresh(analysis)

        return analysis

    def _synthesise_epochs(self, extraction: ClinicalExtraction) -> list[dict]:
        rng = np.random.default_rng(42)
        duration = extraction.recording_duration_sec
        epoch_dur = duration / N_SYNTHETIC_EPOCHS

        # Depression is sustained — base contribution from overall score
        base_contribution = extraction.depression_severity_score / 27.0

        mentioned_channels = set(extraction.extracted_fields.get("channels_mentioned", []))
        if not mentioned_channels:
            mentioned_channels = set(CHANNELS_10_20[:8])

        epochs = []
        for i in range(N_SYNTHETIC_EPOCHS):
            t_s = i * epoch_dur
            t_e = t_s + epoch_dur

            # Depression contribution with small noise
            noise = float(rng.normal(0, 0.04))
            contribution = float(np.clip(base_contribution + noise, 0.0, 1.0))

            # Band powers with noise
            bp = {}
            for band, power in extraction.band_powers.items():
                bp[band] = float(np.clip(power + rng.normal(0, 0.02), 0.0, 1.0))
            total = sum(bp.values()) or 1.0
            bp = {k: round(v / total, 4) for k, v in bp.items()}

            # Dominant frequency
            band_centers = {"delta": 2.0, "theta": 6.0, "alpha": 10.0, "beta": 20.0, "gamma": 38.0}
            dom_band = max(bp, key=bp.get)
            dom_freq = float(np.clip(rng.normal(band_centers.get(dom_band, 10), 1), 0.5, 45))

            # Channel attention (frontal-weighted for depression)
            weights = np.ones(len(CHANNELS_10_20))
            for j, ch in enumerate(CHANNELS_10_20):
                if ch in mentioned_channels:
                    weights[j] *= rng.uniform(2.0, 4.0)
                if ch in FRONTAL_CHANNELS and base_contribution > 0.3:
                    weights[j] *= rng.uniform(1.5, 3.0)
            weights = weights / (weights.sum() + 1e-8)
            channel_attention = {ch: round(float(w), 5) for ch, w in zip(CHANNELS_10_20, weights)}

            # FAA with noise
            faa = extraction.frontal_alpha_asymmetry + float(rng.normal(0, 0.05))

            confidence = float(np.clip(0.5 + abs(contribution - 0.5) * 0.8, 0.0, 1.0))
            artifact_prob = float(np.clip(rng.beta(1, 20), 0.0, 1.0))

            epochs.append({
                "epoch_index": i,
                "start_time_sec": round(t_s, 2),
                "end_time_sec": round(t_e, 2),
                "depression_contribution": round(contribution, 4),
                "artifact_probability": round(artifact_prob, 4),
                "channel_attention": channel_attention,
                "dominant_frequency_hz": round(dom_freq, 2),
                "band_powers": bp,
                "frontal_alpha_asymmetry": round(faa, 4),
                "confidence": round(confidence, 4),
            })

        return epochs

    def _build_clinical_impression(self, extraction: ClinicalExtraction) -> str:
        lines = [f"Background: {extraction.background_rhythm}."]
        score = extraction.depression_severity_score
        level = extraction.depression_risk_level

        lines.append(
            f"Depression severity score (NLP-derived): {score:.1f}/27 "
            f"(PHQ-9 equivalent: {level})."
        )

        if extraction.frontal_alpha_asymmetry < -0.1:
            lines.append(
                f"Frontal alpha asymmetry indicator detected in source report "
                f"(FAA = {extraction.frontal_alpha_asymmetry:.3f})."
            )

        if score < 5:
            lines.append("Source report indicates minimal depressive indicators.")
        elif score < 10:
            lines.append("Source report suggests mild depressive symptoms.")
        else:
            lines.append(
                "Source report indicates significant depressive indicators. "
                "Recommend clinical assessment with standardised instruments."
            )

        lines.append(
            f"Source confidence: {extraction.source_confidence}. "
            "Analysis derived from clinical report text via NLP extraction. "
            "IMPORTANT: This is an AI-assisted depression screening from a PDF source. "
            "Results require review by a qualified psychiatrist or neurologist."
        )
        return " ".join(lines)


async def run_pdf_pipeline_background(study_id: int, db_factory):
    db = db_factory()
    try:
        pipeline = PdfAnalysisPipeline(db)
        await pipeline.run(study_id)
    finally:
        db.close()
