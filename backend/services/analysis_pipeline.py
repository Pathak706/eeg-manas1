import asyncio
import json
import time
from pathlib import Path

import numpy as np
from sqlalchemy.orm import Session

from config import settings
from models.study import Study
from models.analysis import AnalysisResult, EpochResult
from services.eeg_preprocessor import EEGPreprocessor
from services.manas1_mock import MANAS1MockService, MANAS1Response
from utils.edf_reader import EDFReader


class AnalysisPipeline:
    def __init__(self, db: Session):
        self.db = db
        self.manas1 = MANAS1MockService()

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
        # Step 1: Load raw data
        study.status = "preprocessing"
        self.db.commit()

        channel_names = json.loads(study.channel_names)

        if study.is_synthetic:
            # Load from .npz (saved during demo generation)
            npz = np.load(study.file_path)
            raw_data = npz["data"]
            sample_rate = int(npz["sample_rate"])
            channel_names = list(npz["channels"])
        else:
            reader = EDFReader()
            eeg = reader.read(study.file_path)
            raw_data = eeg.data
            sample_rate = eeg.sample_rate
            channel_names = eeg.channel_names

        # Step 2: Preprocess
        preprocessor = EEGPreprocessor(sample_rate, channel_names)
        preprocessed = preprocessor.preprocess(raw_data, target_display_rate=settings.EEG_DISPLAY_SAMPLE_RATE)

        # Step 3: Save display data
        display_path = Path(settings.PROCESSED_DIR) / f"{study.id}_display.npz"
        np.savez_compressed(
            str(display_path),
            data=preprocessed.display_data,
            channels=np.array(preprocessed.channel_names),
            sample_rate=np.array(preprocessed.display_sample_rate),
            duration_sec=np.array(preprocessed.duration_sec),
        )
        study.display_data_path = str(display_path)
        study.recording_duration_sec = preprocessed.duration_sec
        study.sample_rate_hz = sample_rate
        study.channel_count = len(channel_names)
        study.channel_names = json.dumps(channel_names)
        study.epoch_total = len(preprocessed.epochs)
        study.status = "analyzing"
        self.db.commit()

        # Step 4: MANAS-1 inference
        async def on_progress(current: int, total: int):
            study.epoch_progress = current
            self.db.commit()

        response: MANAS1Response = await self.manas1.analyze_study(
            preprocessed, study.id, progress_callback=on_progress
        )

        # Step 5: Persist results
        analysis = AnalysisResult(
            study_id=study.id,
            model_version=response.model_version,
            overall_seizure_probability=response.overall_seizure_probability,
            clinical_impression=response.clinical_impression,
            background_rhythm=response.background_rhythm,
            clinical_flags=json.dumps([
                {
                    "flag_type": f.flag_type,
                    "severity": f.severity,
                    "onset_sec": f.onset_sec,
                    "duration_sec": f.duration_sec,
                    "channels_involved": f.channels_involved,
                    "description": f.description,
                }
                for f in response.clinical_flags
            ]),
            processing_time_ms=response.processing_time_ms,
        )
        self.db.add(analysis)
        self.db.flush()  # get analysis.id

        epoch_rows = [
            EpochResult(
                analysis_id=analysis.id,
                epoch_index=ep.epoch_index,
                start_time_sec=ep.start_time_sec,
                end_time_sec=ep.end_time_sec,
                seizure_probability=ep.seizure_probability,
                artifact_probability=ep.artifact_probability,
                channel_attention=json.dumps(ep.channel_attention),
                dominant_frequency_hz=ep.dominant_frequency_hz,
                band_powers=json.dumps(ep.band_powers),
                confidence=ep.confidence,
            )
            for ep in response.epochs
        ]
        self.db.bulk_save_objects(epoch_rows)

        study.status = "complete"
        study.epoch_progress = study.epoch_total
        self.db.commit()
        self.db.refresh(analysis)

        return analysis


async def run_pipeline_background(study_id: int, db_factory):
    """Entry point for BackgroundTasks. Creates its own DB session."""
    db = db_factory()
    try:
        pipeline = AnalysisPipeline(db)
        await pipeline.run(study_id)
    finally:
        db.close()
