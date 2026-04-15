"""
MANAS-1 Mock Inference Service.

Simulates the output contract of the real MANAS-1 400M-parameter EEG foundation model.
To swap in the real model: replace MANAS1MockService with MANAS1HTTPClient that POSTs
preprocessed epoch arrays to the actual inference endpoint and parses the same response types.
"""
import asyncio
import json
import time
from dataclasses import dataclass, field

import numpy as np

from services.eeg_preprocessor import PreprocessedEEG
from config import settings

# Channels considered as the focal temporal region for seizure attention
TEMPORAL_CHANNELS = {"T3", "T4", "F7", "F8", "T5", "T6"}


@dataclass
class EpochAnalysis:
    epoch_index: int
    start_time_sec: float
    end_time_sec: float
    seizure_probability: float
    artifact_probability: float
    channel_attention: dict[str, float]
    dominant_frequency_hz: float
    band_powers: dict[str, float]
    confidence: float


@dataclass
class ClinicalFlag:
    flag_type: str          # SEIZURE_EVENT | INTERICTAL_DISCHARGE | ARTIFACT | SLOWING
    severity: str           # HIGH | MEDIUM | LOW
    onset_sec: float
    duration_sec: float
    channels_involved: list[str]
    description: str


@dataclass
class MANAS1Response:
    model_version: str
    study_id: int
    epochs: list[EpochAnalysis]
    overall_seizure_probability: float
    clinical_flags: list[ClinicalFlag]
    background_rhythm: str
    clinical_impression: str
    processing_time_ms: int


class MANAS1MockService:
    MODEL_VERSION = "manas1-mock-v0.1"

    def __init__(self):
        self.latency_ms = settings.MANAS1_MOCK_LATENCY_MS

    async def analyze_study(
        self,
        preprocessed: PreprocessedEEG,
        study_id: int,
        progress_callback=None,
    ) -> MANAS1Response:
        t_start = time.time()
        n_epochs = len(preprocessed.epochs)

        # Decide on a seizure window — one contiguous block
        rng = np.random.default_rng(study_id % 9999)
        has_seizure = preprocessed.duration_sec > 30
        seizure_epoch_start = None
        seizure_epoch_end = None

        if has_seizure:
            # Place seizure roughly 40% into the recording
            mid_epoch = int(n_epochs * 0.40)
            seizure_epoch_start = max(0, mid_epoch - 1)
            seizure_epoch_end = min(n_epochs - 1, mid_epoch + 4)

        epoch_results: list[EpochAnalysis] = []

        for i, epoch in enumerate(preprocessed.epochs):
            in_seizure = (
                seizure_epoch_start is not None
                and seizure_epoch_start <= i <= seizure_epoch_end
            )

            result = self._analyze_epoch(
                epoch_data=epoch,
                epoch_index=i,
                start_time_sec=preprocessed.epoch_start_times[i],
                epoch_duration_sec=preprocessed.epoch_duration_sec,
                band_powers=preprocessed.band_powers_per_epoch[i],
                dominant_freq=preprocessed.dominant_freqs_per_epoch[i],
                channel_names=preprocessed.channel_names,
                is_seizure=in_seizure,
                rng=rng,
            )
            epoch_results.append(result)

            if progress_callback:
                await progress_callback(i + 1, n_epochs)

            # Simulate inference latency
            await asyncio.sleep(self.latency_ms / 1000.0)

        # Aggregate
        seizure_probs = [e.seizure_probability for e in epoch_results]
        # Smooth with a 3-epoch rolling max
        smoothed = [
            max(seizure_probs[max(0, i - 1): i + 2])
            for i in range(len(seizure_probs))
        ]
        overall_prob = float(np.percentile(smoothed, 95))

        avg_band_powers = self._average_band_powers(preprocessed.band_powers_per_epoch)
        background_rhythm = self._infer_background_rhythm(avg_band_powers)
        clinical_flags = self._generate_clinical_flags(epoch_results, preprocessed.channel_names)
        clinical_impression = self._generate_clinical_impression(clinical_flags, overall_prob, background_rhythm)

        processing_time_ms = int((time.time() - t_start) * 1000)

        return MANAS1Response(
            model_version=self.MODEL_VERSION,
            study_id=study_id,
            epochs=epoch_results,
            overall_seizure_probability=overall_prob,
            clinical_flags=clinical_flags,
            background_rhythm=background_rhythm,
            clinical_impression=clinical_impression,
            processing_time_ms=processing_time_ms,
        )

    def _analyze_epoch(
        self,
        epoch_data: np.ndarray,
        epoch_index: int,
        start_time_sec: float,
        epoch_duration_sec: float,
        band_powers: dict,
        dominant_freq: float,
        channel_names: list[str],
        is_seizure: bool,
        rng: np.random.Generator,
    ) -> EpochAnalysis:
        # Seizure probability via Beta distribution
        if is_seizure:
            base_prob = rng.beta(8, 2)  # skewed high: mean ~0.80
        else:
            base_prob = rng.beta(2, 8)  # skewed low: mean ~0.20

        # Artifact detection: look for single-sample transient spikes (electrode pops)
        # Use normalized diff rather than amplitude — seizure has sustained high amplitude,
        # artefacts have abrupt single-sample jumps
        diff = np.abs(np.diff(epoch_data, axis=1))
        max_jump = float(np.max(diff)) if diff.size > 0 else 0.0
        # A genuine artefact pop exceeds 50× median jump
        median_jump = float(np.median(diff)) + 1e-8
        artifact_prob = float(np.clip((max_jump / median_jump - 50) / 200, 0.0, 1.0))
        # Only suppress seizure prob for clearly artefactual epochs, not high-amplitude seizures
        if artifact_prob > 0.8 and not is_seizure:
            base_prob *= 0.4

        seizure_prob = float(np.clip(base_prob, 0.0, 1.0))

        channel_attention = self._generate_channel_attention(
            epoch_data, channel_names, is_seizure, rng
        )

        # Confidence: lower during artifacts or borderline probabilities
        dist_from_boundary = abs(seizure_prob - 0.5)
        confidence = float(np.clip(0.6 + dist_from_boundary * 0.7, 0.0, 1.0))

        return EpochAnalysis(
            epoch_index=epoch_index,
            start_time_sec=start_time_sec,
            end_time_sec=start_time_sec + epoch_duration_sec,
            seizure_probability=seizure_prob,
            artifact_probability=artifact_prob,
            channel_attention=channel_attention,
            dominant_frequency_hz=dominant_freq,
            band_powers=band_powers,
            confidence=confidence,
        )

    def _generate_channel_attention(
        self,
        epoch_data: np.ndarray,
        channel_names: list[str],
        is_seizure: bool,
        rng: np.random.Generator,
    ) -> dict[str, float]:
        # Base: channel variance as proxy for "interestingness"
        variance = np.var(epoch_data, axis=1)
        weights = variance / (variance.sum() + 1e-8)

        if is_seizure:
            # Boost temporal channels to simulate focal detection
            for i, ch in enumerate(channel_names):
                if ch in TEMPORAL_CHANNELS:
                    weights[i] *= rng.uniform(3.0, 6.0)

        # Normalize to sum=1
        weights = weights / (weights.sum() + 1e-8)
        return {ch: float(w) for ch, w in zip(channel_names, weights)}

    def _generate_clinical_flags(
        self,
        epochs: list[EpochAnalysis],
        channel_names: list[str],
    ) -> list[ClinicalFlag]:
        flags: list[ClinicalFlag] = []

        # Find contiguous high-probability seizure epochs (>= 0.55)
        in_event = False
        event_start = 0.0
        event_epochs: list[EpochAnalysis] = []

        for ep in epochs:
            if ep.seizure_probability >= 0.55:
                if not in_event:
                    in_event = True
                    event_start = ep.start_time_sec
                    event_epochs = []
                event_epochs.append(ep)
            else:
                if in_event and len(event_epochs) >= 2:
                    flags.append(self._build_seizure_flag(event_epochs, channel_names))
                in_event = False
                event_epochs = []

        if in_event and len(event_epochs) >= 2:
            flags.append(self._build_seizure_flag(event_epochs, channel_names))

        # Interictal discharges: single high-probability epochs
        for ep in epochs:
            if 0.45 <= ep.seizure_probability < 0.55:
                top_channels = sorted(
                    ep.channel_attention.items(), key=lambda x: x[1], reverse=True
                )[:3]
                flags.append(ClinicalFlag(
                    flag_type="INTERICTAL_DISCHARGE",
                    severity="MEDIUM",
                    onset_sec=ep.start_time_sec,
                    duration_sec=ep.end_time_sec - ep.start_time_sec,
                    channels_involved=[c for c, _ in top_channels],
                    description=f"Possible interictal epileptiform discharge at {ep.start_time_sec:.1f}s",
                ))

        # Background slowing
        avg_delta = np.mean([e.band_powers.get("delta", 0) for e in epochs])
        if avg_delta > 0.35:
            flags.append(ClinicalFlag(
                flag_type="SLOWING",
                severity="MEDIUM",
                onset_sec=0.0,
                duration_sec=epochs[-1].end_time_sec if epochs else 0.0,
                channels_involved=[],
                description="Diffuse background slowing with excess delta activity",
            ))

        return flags

    def _build_seizure_flag(
        self, event_epochs: list[EpochAnalysis], channel_names: list[str]
    ) -> ClinicalFlag:
        onset = event_epochs[0].start_time_sec
        offset = event_epochs[-1].end_time_sec
        duration = offset - onset

        # Aggregate attention across seizure epochs
        combined_attention: dict[str, float] = {}
        for ep in event_epochs:
            for ch, w in ep.channel_attention.items():
                combined_attention[ch] = combined_attention.get(ch, 0) + w
        top_channels = sorted(combined_attention.items(), key=lambda x: x[1], reverse=True)[:4]
        involved = [c for c, _ in top_channels]

        is_temporal = any(c in TEMPORAL_CHANNELS for c in involved)
        laterality = "left" if any(c.endswith(("3", "7")) for c in involved) else "right"

        return ClinicalFlag(
            flag_type="SEIZURE_EVENT",
            severity="HIGH",
            onset_sec=onset,
            duration_sec=duration,
            channels_involved=involved,
            description=(
                f"Focal ictal discharge with {laterality} {'temporal' if is_temporal else 'fronto-temporal'} "
                f"predominance. Onset at {onset:.1f}s, duration {duration:.0f}s. "
                f"Maximum amplitude in channels: {', '.join(involved[:2])}."
            ),
        )

    def _average_band_powers(self, band_powers_list: list[dict]) -> dict[str, float]:
        if not band_powers_list:
            return {}
        keys = band_powers_list[0].keys()
        return {k: float(np.mean([bp.get(k, 0) for bp in band_powers_list])) for k in keys}

    def _infer_background_rhythm(self, avg_band_powers: dict) -> str:
        alpha = avg_band_powers.get("alpha", 0)
        delta = avg_band_powers.get("delta", 0)
        theta = avg_band_powers.get("theta", 0)

        if alpha > 0.30:
            return "Well-organised posterior alpha rhythm (9–11 Hz)"
        elif delta > 0.30:
            return "Diffuse cerebral slowing with excess delta activity"
        elif theta > 0.30:
            return "Mild diffuse slowing with excess theta activity"
        else:
            return "Low-voltage fast activity; background mildly disorganised"

    def _generate_clinical_impression(
        self,
        flags: list[ClinicalFlag],
        overall_prob: float,
        background_rhythm: str,
    ) -> str:
        seizure_flags = [f for f in flags if f.flag_type == "SEIZURE_EVENT"]
        interictal_flags = [f for f in flags if f.flag_type == "INTERICTAL_DISCHARGE"]

        lines = [f"Background: {background_rhythm}."]

        if seizure_flags:
            sf = seizure_flags[0]
            lines.append(
                f"The EEG demonstrates focal epileptiform activity arising from the "
                f"{sf.channels_involved[0] if sf.channels_involved else 'temporal'} region. "
                f"A seizure event was identified at {sf.onset_sec:.1f}s with a duration of "
                f"{sf.duration_sec:.0f}s."
            )
            lines.append(
                f"Overall seizure probability: {overall_prob:.0%} (MANAS-1 model score)."
            )
        elif interictal_flags:
            lines.append(
                f"Interictal epileptiform discharges noted at {len(interictal_flags)} timepoint(s). "
                f"No definite ictal pattern identified in this recording."
            )
            lines.append(
                f"Overall seizure probability: {overall_prob:.0%} (MANAS-1 model score). "
                "Clinical correlation recommended."
            )
        else:
            lines.append(
                f"No definite epileptiform activity identified. "
                f"Overall seizure probability: {overall_prob:.0%} (MANAS-1 model score)."
            )

        lines.append(
            "IMPORTANT: This is an AI-assisted pre-read. All findings require review "
            "and confirmation by a qualified neurologist before clinical use."
        )

        return " ".join(lines)
