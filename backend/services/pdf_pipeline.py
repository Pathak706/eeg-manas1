"""
PDF Analysis Pipeline.

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
from services.clinical_nlp import ClinicalNLPExtractor, ClinicalExtraction, TEMPORAL_CHANNELS

CHANNELS_10_20 = [
    "Fp1", "Fp2", "F3", "F4", "C3", "C4", "P3", "P4",
    "O1", "O2", "F7", "F8", "T3", "T4", "T5", "T6",
    "Fz", "Cz", "Pz",
]
MODEL_VERSION = "manas1-pdf-nlp-v0.1"
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

        # Step 1: Extract text
        study.status = "preprocessing"
        self.db.commit()

        raw_text = self.ingestion.extract_text(Path(study.file_path))
        markdown_text = self.ingestion.to_markdown(raw_text)

        study.extracted_text = markdown_text
        study.epoch_total = N_SYNTHETIC_EPOCHS
        self.db.commit()

        # Step 2: NLP extraction
        study.status = "analyzing"
        self.db.commit()

        extraction: ClinicalExtraction = self.nlp.extract(markdown_text)

        # Update study metadata from extracted fields
        study.recording_duration_sec = extraction.recording_duration_sec
        study.channel_names = json.dumps(CHANNELS_10_20)
        study.channel_count = len(CHANNELS_10_20)
        study.sample_rate_hz = 0  # no signal
        self.db.commit()

        # Step 3: Synthesise epochs
        epoch_dicts = self._synthesise_epochs(extraction)

        # Step 4: Build clinical impression
        clinical_impression = self._build_clinical_impression(extraction)

        # Step 5: Persist
        processing_time_ms = int((time.time() - t_start) * 1000)

        analysis = AnalysisResult(
            study_id=study.id,
            model_version=MODEL_VERSION,
            overall_seizure_probability=extraction.overall_seizure_probability,
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
                seizure_probability=ep["seizure_probability"],
                artifact_probability=ep["artifact_probability"],
                channel_attention=json.dumps(ep["channel_attention"]),
                dominant_frequency_hz=ep["dominant_frequency_hz"],
                band_powers=json.dumps(ep["band_powers"]),
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

    # ── Epoch synthesis ────────────────────────────────────────────────────

    def _synthesise_epochs(self, extraction: ClinicalExtraction) -> list[dict]:
        """
        Generate N_SYNTHETIC_EPOCHS synthetic epoch dicts consistent with
        the extracted clinical findings.
        """
        rng = np.random.default_rng(42)
        duration = extraction.recording_duration_sec
        epoch_dur = duration / N_SYNTHETIC_EPOCHS

        # Determine which epoch indices fall inside detected seizure windows
        seizure_epoch_set: set[int] = set()
        for flag in extraction.clinical_flags:
            if flag["flag_type"] == "SEIZURE_EVENT":
                onset = flag["onset_sec"]
                offset = onset + flag["duration_sec"]
                for i in range(N_SYNTHETIC_EPOCHS):
                    t_start = i * epoch_dur
                    t_end = t_start + epoch_dur
                    if t_end > onset and t_start < offset:
                        seizure_epoch_set.add(i)

        # Determine channel attention pattern
        mentioned_channels = set(extraction.extracted_fields.get("channels_mentioned", []))
        if not mentioned_channels:
            mentioned_channels = set(CHANNELS_10_20[:8])  # default front channels

        temporal_present = bool(mentioned_channels & TEMPORAL_CHANNELS)

        epochs = []
        for i in range(N_SYNTHETIC_EPOCHS):
            in_seizure = i in seizure_epoch_set
            t_s = i * epoch_dur
            t_e = t_s + epoch_dur

            # Seizure probability
            if in_seizure:
                prob = float(np.clip(rng.beta(8, 2), 0.0, 1.0))
            else:
                # Background — scale toward overall prob
                base = extraction.overall_seizure_probability * 0.4
                noise = rng.beta(2, 8) * 0.2
                prob = float(np.clip(base + noise, 0.0, 1.0))

            # Band powers with small per-epoch noise
            bp = {}
            for band, power in extraction.band_powers.items():
                noise = float(rng.normal(0, 0.02))
                bp[band] = float(np.clip(power + noise, 0.0, 1.0))
            total = sum(bp.values()) or 1.0
            bp = {k: round(v / total, 4) for k, v in bp.items()}

            # Dominant frequency from band powers
            dom_freq = self._dominant_freq_from_bands(bp, rng)

            # Channel attention
            channel_attention = self._channel_attention(
                CHANNELS_10_20, mentioned_channels, in_seizure and temporal_present, rng
            )

            # Confidence
            dist = abs(prob - 0.5)
            confidence = float(np.clip(0.5 + dist * 0.8, 0.0, 1.0))

            # Artifact: very rare for PDF-sourced studies
            artifact_prob = float(np.clip(rng.beta(1, 20), 0.0, 1.0))

            epochs.append({
                "epoch_index": i,
                "start_time_sec": round(t_s, 2),
                "end_time_sec": round(t_e, 2),
                "seizure_probability": round(prob, 4),
                "artifact_probability": round(artifact_prob, 4),
                "channel_attention": channel_attention,
                "dominant_frequency_hz": round(dom_freq, 2),
                "band_powers": bp,
                "confidence": round(confidence, 4),
            })

        return epochs

    def _dominant_freq_from_bands(
        self, band_powers: dict[str, float], rng: np.random.Generator
    ) -> float:
        band_centers = {"delta": 2.0, "theta": 6.0, "alpha": 10.0, "beta": 20.0, "gamma": 38.0}
        dominant_band = max(band_powers, key=band_powers.get)
        center = band_centers.get(dominant_band, 10.0)
        return float(np.clip(rng.normal(center, 1.0), 0.5, 45.0))

    def _channel_attention(
        self,
        all_channels: list[str],
        mentioned: set[str],
        boost_temporal: bool,
        rng: np.random.Generator,
    ) -> dict[str, float]:
        weights = np.ones(len(all_channels))
        for i, ch in enumerate(all_channels):
            if ch in mentioned:
                weights[i] *= rng.uniform(2.0, 4.0)
            if boost_temporal and ch in TEMPORAL_CHANNELS:
                weights[i] *= rng.uniform(2.0, 5.0)
        weights = weights / (weights.sum() + 1e-8)
        return {ch: round(float(w), 5) for ch, w in zip(all_channels, weights)}

    # ── Clinical impression ────────────────────────────────────────────────

    def _build_clinical_impression(self, extraction: ClinicalExtraction) -> str:
        lines = [f"Background: {extraction.background_rhythm}."]
        prob = extraction.overall_seizure_probability

        seizure_flags = [f for f in extraction.clinical_flags if f["flag_type"] == "SEIZURE_EVENT"]
        interictal_flags = [f for f in extraction.clinical_flags if f["flag_type"] == "INTERICTAL_DISCHARGE"]

        if seizure_flags:
            sf = seizure_flags[0]
            ch = sf["channels_involved"][0] if sf["channels_involved"] else "temporal"
            lines.append(
                f"The source report describes focal epileptiform activity. "
                f"A seizure event was identified at {sf['onset_sec']:.1f}s with a duration of "
                f"{sf['duration_sec']:.0f}s (channel: {ch})."
            )
            lines.append(f"Overall seizure probability (NLP-derived): {prob:.0%}.")
        elif interictal_flags:
            lines.append(
                f"Interictal epileptiform discharges described in source report. "
                f"No definite ictal pattern. Overall probability: {prob:.0%}."
            )
        else:
            lines.append(
                f"No definite epileptiform activity identified in source report. "
                f"Overall seizure probability (NLP-derived): {prob:.0%}."
            )

        lines.append(
            f"Source confidence: {extraction.source_confidence}. "
            "Analysis derived from clinical report text via NLP extraction. "
            "IMPORTANT: This is an AI-assisted pre-read from a PDF source. "
            "Results require review and confirmation by a qualified neurologist."
        )
        return " ".join(lines)


async def run_pdf_pipeline_background(study_id: int, db_factory):
    """Entry point for BackgroundTasks. Creates its own DB session."""
    db = db_factory()
    try:
        pipeline = PdfAnalysisPipeline(db)
        await pipeline.run(study_id)
    finally:
        db.close()
